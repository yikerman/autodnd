"""Renderers — the firewall layer.

Each renderer is a pure function of ``(world, ...)`` returning prompt text.
The player is rendered separately from NPCs so the arbiter cannot confuse the
player's display name with an NPC id. NPC character renders see only history
records where that NPC is a participant.
"""

from __future__ import annotations

from autodnd.engine.world import (
    PLAYER,
    ActorState,
    AtLocation,
    Character,
    HeldBy,
    History,
    Item,
    Location,
    Player,
    World,
)


def render_for_player(world: World) -> str:
    """Read-only mechanical view of the player's state."""
    player = world.player
    if player is None:
        return "(no player exists)"
    location = world.locations.get(player.location_id)

    parts: list[str] = []
    parts.append(f"# Player\n{player.name} — {player.description}")
    parts.append(_render_mechanical_state(player))
    parts.append(_render_abilities(player))
    if player.skill_mods:
        parts.append(_render_skill_mods(player.skill_mods))
    inventory = _items_held_by(world, PLAYER)
    parts.append(
        "# Inventory\n" + (_render_items(inventory) if inventory else "(empty)")
    )
    memory = [h for h in world.history if PLAYER in h.participants]
    if memory:
        parts.append("# Recent memory\n" + _render_history(memory))
    parts.append(
        "# Current location\n" + _render_location(location, player.location_id)
    )
    present = _npcs_at(world, player.location_id)
    if present:
        parts.append("# Present nearby\n" + "\n".join(_npc_line(c) for c in present))
    return "\n\n".join(parts)


def render_for_character(
    world: World,
    character_id: str,
    *,
    cycle_history_ids: list[str] | None = None,
    arbiter_hint: str | None = None,
) -> tuple[str, str]:
    """``(system_prompt, user_prompt)`` for an NPC character call."""
    if character_id == PLAYER:
        raise KeyError("the player is not an NPC actor")
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
    """``(system_prompt, user_prompt)`` for the narrator.

    Narrator sees only player-visible state: the player's current location,
    public NPC descriptions nearby, items nearby, and history records where
    ``"player"`` is a participant.
    """
    player = world.player
    if player is None:
        raise ValueError("narrator render requires world.player")
    location = world.locations.get(player.location_id)
    cycle_set = set(cycle_history_ids or [])
    user = _render_narrator_user(world, player, location, cycle_set, arbiter_hint)
    return NARRATOR_SYSTEM, user


def render_arbiter(world: World, trigger: str | None) -> tuple[str, str]:
    """``(system_prompt, user_prompt)`` for the arbiter's multi-round session."""
    return ARBITER_SYSTEM, _render_arbiter_user(world, trigger)


_CHARACTER_SYSTEM_TEMPLATE = """\
You are {name}.

{description}

## How to act
Speak in your voice. Describe only what you say, do, or notice outwardly. \
Never narrate other characters' interior thoughts. Speak only from what you \
remember below. Stay in character.

## Tools
- `say(content)` — speak aloud; the simulator mints a record with you, the \
player if present, and present NPCs as participants.
- `act(intent)` — declare a non-speech action that affects others; the \
arbiter resolves it.
- `request_dice_check`, `request_dice_attack`, `request_dice_save` — roll \
self-contained uncertainty.
- `move_self(location_id)` — go elsewhere.
- `transfer_item(item_id, recipient_character_id)` — give something you hold.

Respond with one short beat. What do you say or do?
"""


NARRATOR_SYSTEM = """\
You are the narrator of a fictional world simulator. You describe only what \
the player perceives: environment, movement, expressions, speech, and visible \
consequences. You write in second person addressing the player. Never narrate \
any character's interior thoughts. Do not decide what the player does next. \
Respond with one short beat.
"""


ARBITER_SYSTEM = """\
You are the arbiter of a fictional world simulator.

## Your job
Conduct the next moment. The player is not an NPC and must never be invoked \
as an actor. Treat the trigger as the player's input already chosen by the \
human. Resolve consequences, roll dice for uncertainty, mutate state, invoke \
NPCs and the narrator in dramatic order, then end the cycle at a stable beat.

## Participants
The reserved participant `player` means the human player's character stored \
in `world.player`. NPC ids are listed under NPCs. Never create an NPC to \
represent the player.

Each history record's `participants` field defines who knows it happened:
- Public action in the player's scene: `player` plus every present NPC.
- NPC private thought/plan/resolution: that NPC only.
- Player-visible narration: `player`.
- Cosmic/offstage fact no one knows: [].
Never name an NPC in a description if they are not in `participants`.

## Hints
When calling `invoke_actor(actor_id, hint)`, use an NPC id only. Hints must be \
behavioral, not causal; the NPC will see the hint.

## Tools
Creation: `create_location`, `create_npc`, `create_item`.
Player state: `move_player`, `update_player_stats`.
History: `mint_history`.
NPC state: `move_npc`, `update_npc_stats`, `transfer_item`, \
`update_item_description`, `advance_narrative_time`.
Dice: `roll`, `check`, `attack`, `save`.
Control: `invoke_actor(actor_id, hint)`, `end_cycle()`.

The engine has already recorded the player's input as a history record \
visible to the player and every NPC present. Mint additional records only \
for distinct events (NPC reactions, offstage consequences, etc.).
"""


def _render_character_user(
    world: World,
    character: Character,
    location: Location | None,
    cycle_set: set[str],
    arbiter_hint: str | None,
) -> str:
    parts: list[str] = []
    memory = [
        h
        for h in world.history
        if character.id in h.participants and h.id not in cycle_set
    ]
    parts.append(
        "## What you remember\n"
        + (_render_history(memory) if memory else "(nothing yet)")
    )
    parts.append(
        "## Your location\n" + _render_location(location, character.location_id)
    )
    parts.append(
        "## Your state\n" + _render_actor_state(world, character.id, character)
    )

    present: list[str] = []
    if world.player is not None and world.player.location_id == character.location_id:
        present.append(f"- {world.player.name} (player) — {world.player.description}")
    present.extend(
        _npc_line(c)
        for c in _npcs_at(world, character.location_id)
        if c.id != character.id
    )
    parts.append(
        "## Present in this scene\n"
        + ("\n".join(present) if present else "(no one else)")
    )

    cycle_perceived = [
        h for h in world.history if h.id in cycle_set and character.id in h.participants
    ]
    if cycle_perceived:
        parts.append("## Just happened\n" + _render_history(cycle_perceived))
    if arbiter_hint:
        parts.append(f"## Hint\n{arbiter_hint}")
    return "\n\n".join(parts)


def _render_narrator_user(
    world: World,
    player: Player,
    location: Location | None,
    cycle_set: set[str],
    arbiter_hint: str | None,
) -> str:
    parts: list[str] = []
    parts.append(f"## Player\n{player.name} — {player.description}")
    parts.append(
        "## Current location\n" + _render_location(location, player.location_id)
    )

    present = _npcs_at(world, player.location_id)
    if present:
        parts.append("## Present here\n" + "\n".join(_npc_line(c) for c in present))
    items_here = _items_at(world, player.location_id)
    if items_here:
        parts.append("## Items here\n" + _render_items(items_here))

    perceived_recent = [
        h
        for h in world.history
        if PLAYER in h.participants
        and h.location_id == player.location_id
        and h.id not in cycle_set
    ]
    if perceived_recent:
        parts.append(
            "## What the player perceived recently\n"
            + _render_history(perceived_recent[-15:])
        )

    cycle_perceived = [
        h for h in world.history if h.id in cycle_set and PLAYER in h.participants
    ]
    if cycle_perceived:
        parts.append("## Just happened\n" + _render_history(cycle_perceived))
    if arbiter_hint:
        parts.append(f"## Hint\n{arbiter_hint}")
    return "\n\n".join(parts)


def _render_arbiter_user(world: World, trigger: str | None) -> str:
    parts: list[str] = [
        f"# Simulator state at {world.narrative_time} (t={world.next_t})\nConduct the next moment."
    ]

    if world.player is None:
        parts.append("## Player\n(no player exists)")
        player_loc = None
    else:
        player = world.player
        parts.append(
            "## Player (reserved participant: player)\n"
            f"{player.name} @ {player.location_id} — {player.description}\n"
            + _render_actor_state(world, PLAYER, player)
        )
        player_loc = player.location_id

    parts.append("## NPCs and Locations\n" + _render_background(world))

    offstage = [h for h in world.history if h.location_id != player_loc]
    if offstage:
        parts.append("## Recent offstage history\n" + _render_history(offstage[-30:]))

    if player_loc is not None:
        location = world.locations.get(player_loc)
        scene_lines = [f"Location: {_render_location(location, player_loc)}"]
        present = _npcs_at(world, player_loc)
        if present:
            scene_lines.append("NPCs present:")
            scene_lines.extend(_npc_line(c) for c in present)
        else:
            scene_lines.append("NPCs present: (none)")
        parts.append("## Current player scene\n" + "\n".join(scene_lines))

        in_scene = [h for h in world.history if h.location_id == player_loc]
        if in_scene:
            parts.append(
                "## Recent in-scene history\n" + _render_history(in_scene[-30:])
            )

    if trigger is None:
        parts.append("## Player input\n(no new player input this cycle)")
    else:
        parts.append(f"## Player input\n{trigger}")
    return "\n\n".join(parts)


def _render_background(world: World) -> str:
    sections: list[str] = []
    npc_lines = [
        f"- {c.name} ({c.id}) @ {c.location_id} — {_first_sentence(c.description)}"
        for c in (world.characters[cid] for cid in sorted(world.characters))
    ]
    if npc_lines:
        sections.append("### NPCs\n" + "\n".join(npc_lines))
    loc_lines = [
        f"- {world.locations[lid].name} ({lid}) — {_first_sentence(world.locations[lid].description)}"
        for lid in sorted(world.locations)
    ]
    if loc_lines:
        sections.append("### Locations\n" + "\n".join(loc_lines))
    return "\n\n".join(sections) if sections else "(empty)"


def _render_actor_state(world: World, holder_id: str, actor: ActorState) -> str:
    lines = [f"HP: {actor.hp}/{actor.hp_max}. AC: {actor.ac}. Gold: {actor.gold}."]
    inventory = _items_held_by(world, holder_id)
    if inventory:
        lines.append("Inventory:")
        lines.extend(f"  {_render_item_line(item)}" for item in inventory)
    else:
        lines.append("Inventory: (empty)")
    if actor.skill_mods:
        lines.append(_render_skill_mods(actor.skill_mods))
    return "\n".join(lines)


def _render_mechanical_state(c: ActorState) -> str:
    return f"HP: {c.hp}/{c.hp_max}. AC: {c.ac}. Gold: {c.gold}."


def _render_abilities(c: ActorState) -> str:
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
    return "Skill mods: " + ", ".join(
        f"{name} {mod:+d}" for name, mod in sorted(mods.items())
    )


def _render_items(items: list[Item]) -> str:
    return "\n".join(_render_item_line(item) for item in items)


def _render_item_line(item: Item) -> str:
    effects_str = ""
    if item.effects:
        effects_str = (
            " ("
            + ", ".join(f"{k} {v:+d}" for k, v in sorted(item.effects.items()))
            + ")"
        )
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


def _npcs_at(world: World, location_id: str) -> list[Character]:
    return sorted(
        (c for c in world.characters.values() if c.location_id == location_id),
        key=lambda c: c.id,
    )


def _npc_line(character: Character) -> str:
    return f"- {character.name} ({character.id}) @ {character.location_id} — {character.description}"


def _render_location(location: Location | None, fallback_id: str) -> str:
    if location is None:
        return f"({fallback_id})"
    return f"{location.name} — {location.description}"


def _first_sentence(text: str) -> str:
    text = text.strip()
    for stop in (". ", "! ", "? ", "\n"):
        idx = text.find(stop)
        if idx > 0 and idx < 100:
            return text[: idx + 1].strip()
    if len(text) > 80:
        return text[:77].rstrip() + "..."
    return text
