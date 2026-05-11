"""Renderers — the firewall layer.

Each renderer is a pure function of ``(world, ...)`` returning prompt text.
Determinism enables prefix caching: same world → same render byte-for-byte.

Bias philosophy (see ``first_principles.md``):
- The minimum input that scopes the LLM to its task.
- Section labels and ordering are themselves bias mechanisms.
- ``render_for_character`` is the firewall — only history entries with the
  character in ``participants`` are included. Engine guarantees this by
  construction; never a soft prompt instruction.
"""

from __future__ import annotations

from autodnd.engine.world import (
    AtLocation,
    Character,
    HeldBy,
    History,
    Item,
    Location,
    World,
)


# ---------- Public entry points ----------


def render_for_player(world: World) -> str:
    """Read-only mechanical view of the player's state. Third-person framing.

    For sidebar / `/hp` / `/inv` / `/log`. The sidebar LLM gets this plus the
    player's question — no state mutation, no time advance.
    """
    player = world.characters.get("player")
    if player is None:
        return "(no player exists)"
    location = world.locations.get(player.location_id)

    parts: list[str] = []
    parts.append(f"# Player character\n{player.name} — {player.description}")
    parts.append(_render_mechanical_state(player))
    parts.append(_render_abilities(player))
    if player.skill_mods:
        parts.append(_render_skill_mods(player.skill_mods))
    inventory = _items_held_by(world, player.id)
    if inventory:
        parts.append("# Inventory\n" + _render_items(inventory))
    else:
        parts.append("# Inventory\n(empty)")
    memory = [h for h in world.history if "player" in h.participants]
    if memory:
        parts.append("# Recent memory\n" + _render_history(memory))
    parts.append(
        "# Current location\n"
        + (
            f"{location.name} — {location.description}"
            if location is not None
            else f"({player.location_id})"
        )
    )
    return "\n\n".join(parts)


def render_for_character(
    world: World,
    character_id: str,
    *,
    cycle_history_ids: list[str] | None = None,
    arbiter_hint: str | None = None,
) -> tuple[str, str]:
    """``(system_prompt, user_prompt)`` for a character LLM call.

    Strict perception firewall: only history entries with ``character_id in
    participants`` are included. Other characters' descriptions are public-only
    by commitment, so safe to render in full when present in scene.
    """
    if character_id not in world.characters:
        raise KeyError(f"no character {character_id!r}")
    character = world.characters[character_id]
    location = world.locations.get(character.location_id)
    cycle_set = set(cycle_history_ids or [])

    system = _CHARACTER_SYSTEM_TEMPLATE.format(
        name=character.name,
        description=character.description,
    )
    user = _render_character_user(world, character, location, cycle_set, arbiter_hint)
    return system, user


def render_for_narrator(
    world: World,
    *,
    cycle_history_ids: list[str] | None = None,
    arbiter_hint: str | None = None,
) -> tuple[str, str]:
    """``(system_prompt, user_prompt)`` for the narrator pseudo-character.

    Narrator has no tools — produces prose only. View is restricted to
    player-visible state (current location + history with player participant).
    System prompt is global (not per-character) so it's the heaviest cache hit.
    """
    player = world.characters.get("player")
    if player is None:
        raise ValueError("narrator render requires characters['player']")
    location = world.locations.get(player.location_id)
    cycle_set = set(cycle_history_ids or [])

    user = _render_narrator_user(world, player, location, cycle_set, arbiter_hint)
    return NARRATOR_SYSTEM, user


def render_arbiter(world: World, trigger: str) -> tuple[str, str]:
    """``(system_prompt, user_prompt)`` for the arbiter's multi-round session.

    Arbiter sees everything. Frames the world as a continuous simulation — its
    job is to conduct the next moment, not respond to the player.
    """
    user = _render_arbiter_user(world, trigger)
    return ARBITER_SYSTEM, user


# ---------- System prompts ----------


_CHARACTER_SYSTEM_TEMPLATE = """\
You are {name}.

{description}

## How to act
Speak in your voice. Describe only what you say, do, or notice outwardly — \
never narrate other characters' interior thoughts. Speak only from what you \
remember below. Stay in character.

## Tools
- `say(content)` — speak; the simulator mints a record with you and present \
perceivers as participants.
- `act(intent)` — declare a non-speech action that affects others; the \
simulator resolves it on its next round.
- `request_dice(...)` — roll a self-check (perception, stealth, insight).
- `move_self(location_id)` — go elsewhere.
- `transfer_item(item_id, recipient)` — give something you hold.

Respond with one short beat. What do you say or do?
"""


NARRATOR_SYSTEM = """\
You are the narrator of a fictional world simulator. You voice the \
environment, weather, the textures of locations, and the transitions \
between moments. You write in second person addressing the player. You \
never narrate any character's interior thoughts — you can describe outward \
signs (a hand tightens, a glance flicks), not what they mean. Respond \
with one short beat. What does the player perceive next?
"""


ARBITER_SYSTEM = """\
You are the arbiter of a fictional world simulator.

## Your job
Conduct the next moment of the simulation. Mint history records for what \
happens — including off-stage if relevant. Roll dice for uncertainty. Apply \
state changes. Invoke characters who should act, in dramatic order. Advance \
narrative time when the scene reaches a natural pause. End the cycle when \
the scene reaches a stable beat.

## Choosing participants when minting history
Each record's `participants` field defines who knows it happened. Be \
deliberate:
- A whisper has only the speaker and the addressee — unless a bystander \
beats a perception check; then mint a *separate* record for the bystander.
- A public action has everyone present.
- A private thought, plan, or resolution has only the thinker.
**Never name a character in a description if they aren't in `participants`.** \
That leaks knowledge into renders the engine can't filter.

## Writing hints to characters
When you call `invoke_actor(actor_id, hint)`, the hint must be **behavioral**, \
not causal.
- Good: "Answer briefly, then change subject."
- Bad: "Answer evasively because she's hiding her allegiance to Korel."
The character's LLM sees the hint; revealing the *cause* leaks it into prose.

## When to advance narrative time
When the scene reaches a natural pause and time should move on. \
`advance_narrative_time(new_time)` takes free-text NL like "Day 4, dawn".

## Tools
Creation: `create_location`, `create_character`, `create_item`.
History: `mint_history`.
State: `move`, `update_stats`, `transfer_item`, `update_item_description`, \
`advance_narrative_time`.
Dice: `roll`, `check`, `attack`, `save`.
Control: `invoke_actor(actor_id, hint)`, `end_cycle()`.
"""


# ---------- User-prompt builders ----------


def _render_character_user(
    world: World,
    character: Character,
    location: Location | None,
    cycle_set: set[str],
    arbiter_hint: str | None,
) -> str:
    parts: list[str] = []

    # 1. What you remember (memory; append-only) — at top so prefix caches.
    memory = [
        h
        for h in world.history
        if character.id in h.participants and h.id not in cycle_set
    ]
    if memory:
        parts.append("## What you remember\n" + _render_history(memory))
    else:
        parts.append("## What you remember\n(nothing yet)")

    # 2. Your location
    parts.append(
        "## Your location\n"
        + (
            f"{location.name} — {location.description}"
            if location is not None
            else f"({character.location_id})"
        )
    )

    # 3. Your state
    state_lines: list[str] = [
        f"HP: {character.hp}/{character.hp_max}. AC: {character.ac}. "
        f"Gold: {character.gold}.",
    ]
    inventory = _items_held_by(world, character.id)
    if inventory:
        state_lines.append("Inventory:")
        state_lines.extend(f"  {_render_item_line(it)}" for it in inventory)
    else:
        state_lines.append("Inventory: (empty)")
    if character.skill_mods:
        state_lines.append(_render_skill_mods(character.skill_mods))
    parts.append("## Your state\n" + "\n".join(state_lines))

    # 4. Present in this scene (other characters at same location)
    others = sorted(
        (
            c
            for cid, c in world.characters.items()
            if c.location_id == character.location_id and cid != character.id
        ),
        key=lambda c: c.id,
    )
    if others:
        present_lines = [f"- {c.name}: {c.description}" for c in others]
        parts.append("## Present in this scene\n" + "\n".join(present_lines))
    else:
        parts.append("## Present in this scene\n(no one else)")

    # 5. Just happened (this cycle, filtered to this character's perception)
    cycle_perceived = [
        h for h in world.history if h.id in cycle_set and character.id in h.participants
    ]
    if cycle_perceived:
        parts.append(
            "## Just happened (this cycle)\n" + _render_history(cycle_perceived)
        )

    # 6. Hint
    if arbiter_hint:
        parts.append(f"## Hint\n{arbiter_hint}")

    return "\n\n".join(parts)


def _render_narrator_user(
    world: World,
    player: Character,
    location: Location | None,
    cycle_set: set[str],
    arbiter_hint: str | None,
) -> str:
    parts: list[str] = []

    if location is not None:
        parts.append(f"## Current location\n{location.name} — {location.description}")
    else:
        parts.append(f"## Current location\n({player.location_id})")

    others = sorted(
        (
            c
            for cid, c in world.characters.items()
            if c.location_id == player.location_id and cid != "player"
        ),
        key=lambda c: c.id,
    )
    if others:
        present_lines = [f"- {c.name}: {c.description}" for c in others]
        parts.append("## Present here\n" + "\n".join(present_lines))

    items_here = _items_at(world, player.location_id)
    if items_here:
        parts.append("## Items here\n" + _render_items(items_here))

    perceived_recent = [
        h
        for h in world.history
        if "player" in h.participants
        and h.location_id == player.location_id
        and h.id not in cycle_set
    ]
    if perceived_recent:
        parts.append(
            "## What you have perceived recently\n"
            + _render_history(perceived_recent[-15:])
        )

    cycle_perceived = [
        h for h in world.history if h.id in cycle_set and "player" in h.participants
    ]
    if cycle_perceived:
        parts.append("## Just happened\n" + _render_history(cycle_perceived))

    if arbiter_hint:
        parts.append(f"## Hint\n{arbiter_hint}")

    return "\n\n".join(parts)


def _render_arbiter_user(world: World, trigger: str) -> str:
    parts: list[str] = []

    parts.append(
        f"# Simulator state at {world.narrative_time} (t={world.next_t})\n"
        "Conduct the next moment."
    )

    # Background: collapsed roster (stable across cycles)
    parts.append("## Background\n" + _render_background(world))

    player = world.characters.get("player")
    player_loc = player.location_id if player is not None else None

    # Offstage / cosmic history: anything not at the current player location.
    # Includes both events at other locations AND location-less events
    # (cosmic happenings, private knowledge with no specific place). The
    # arbiter is god-mode — it needs all of this to conduct.
    offstage = [h for h in world.history if h.location_id != player_loc]
    if offstage:
        parts.append("## Recent offstage history\n" + _render_history(offstage[-30:]))

    # Current scene
    if player is not None and player_loc is not None:
        location = world.locations.get(player_loc)
        present = sorted(
            (c for c in world.characters.values() if c.location_id == player_loc),
            key=lambda c: c.id,
        )
        scene_lines: list[str] = []
        if location is not None:
            scene_lines.append(f"Location: {location.name} — {location.description}")
        if present:
            scene_lines.append("Present:")
            for c in present:
                scene_lines.append(f"- {c.name} ({c.id}) — {c.description}")
        parts.append("## Current scene\n" + "\n".join(scene_lines))

        in_scene = [h for h in world.history if h.location_id == player_loc]
        if in_scene:
            parts.append(
                "## Recent in-scene history\n" + _render_history(in_scene[-30:])
            )

    parts.append(f"## Trigger\n{trigger}")
    return "\n\n".join(parts)


def _render_background(world: World) -> str:
    char_lines = [
        f"- {world.characters[cid].name} ({cid}) @ "
        f"{world.characters[cid].location_id} — "
        f"{_first_sentence(world.characters[cid].description)}"
        for cid in sorted(world.characters)
    ]
    loc_lines = [
        f"- {world.locations[lid].name} ({lid}) — "
        f"{_first_sentence(world.locations[lid].description)}"
        for lid in sorted(world.locations)
    ]
    sections: list[str] = []
    if char_lines:
        sections.append("### Characters\n" + "\n".join(char_lines))
    if loc_lines:
        sections.append("### Locations\n" + "\n".join(loc_lines))
    return "\n\n".join(sections)


# ---------- Formatting helpers ----------


def _render_mechanical_state(c: Character) -> str:
    return f"# Mechanical state\nHP: {c.hp}/{c.hp_max}. AC: {c.ac}. Gold: {c.gold}."


def _render_abilities(c: Character) -> str:
    a = c.abilities
    return (
        "# Abilities\n"
        f"STR {a.strength} ({_ability_mod(a.strength):+d}). "
        f"DEX {a.dexterity} ({_ability_mod(a.dexterity):+d}). "
        f"CON {a.constitution} ({_ability_mod(a.constitution):+d}). "
        f"INT {a.intelligence} ({_ability_mod(a.intelligence):+d}). "
        f"WIS {a.wisdom} ({_ability_mod(a.wisdom):+d}). "
        f"CHA {a.charisma} ({_ability_mod(a.charisma):+d})."
    )


def _ability_mod(score: int) -> int:
    return (score - 10) // 2


def _render_skill_mods(mods: dict[str, int]) -> str:
    items = sorted(mods.items())
    return "Skill mods: " + ", ".join(f"{name} {mod:+d}" for name, mod in items)


def _render_items(items: list[Item]) -> str:
    return "\n".join(_render_item_line(item) for item in items)


def _render_item_line(item: Item) -> str:
    effects_str = ""
    if item.effects:
        effects_list = sorted(item.effects.items())
        effects_str = " (" + ", ".join(f"{k} {v:+d}" for k, v in effects_list) + ")"
    return f"- {item.name}{effects_str} — {item.description}"


def _render_history(records: list[History]) -> str:
    return "\n".join(f"- [{r.narrative_time}] {r.description}" for r in records)


def _items_held_by(world: World, character_id: str) -> list[Item]:
    return sorted(
        (
            item
            for item in world.items.values()
            if isinstance(item.position, HeldBy)
            and item.position.character_id == character_id
        ),
        key=lambda it: it.id,
    )


def _items_at(world: World, location_id: str) -> list[Item]:
    return sorted(
        (
            item
            for item in world.items.values()
            if isinstance(item.position, AtLocation)
            and item.position.location_id == location_id
        ),
        key=lambda it: it.id,
    )


def _first_sentence(text: str) -> str:
    """First sentence of ``text``, capped at ~80 chars. For background terseness."""
    text = text.strip()
    for stop in (". ", "! ", "? ", "\n"):
        idx = text.find(stop)
        if idx > 0 and idx < 100:
            return text[: idx + 1].strip()
    if len(text) > 80:
        return text[:77].rstrip() + "..."
    return text
