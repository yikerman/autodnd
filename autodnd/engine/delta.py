"""Closed mutation API for WorldDB.

Every state change goes through one of these. Each is a pure function
``(world, **args) -> "ok: ..." | "error: ..."``. On error, world is unchanged.
On success, world mutates in place. No partial commits.

LLM tool calls wrap these (see ``autodnd/llm/``); the wrapper feeds error
strings back to the LLM as the tool result so it can self-correct.
"""

from __future__ import annotations

from autodnd.engine.world import (
    Abilities,
    AtLocation,
    Character,
    HeldBy,
    History,
    Item,
    ItemPosition,
    Location,
    PLAYER,
    Player,
    World,
)


# ---------- Creation ----------


def create_location(
    world: World, *, location_id: str, name: str, description: str
) -> str:
    if location_id in world.locations:
        return f"error: location {location_id!r} already exists"
    world.locations[location_id] = Location(
        id=location_id, name=name, description=description
    )
    return f"ok: created location {location_id}"


def create_character(
    world: World,
    *,
    character_id: str,
    name: str,
    description: str,
    location_id: str,
    hp: int,
    hp_max: int,
    ac: int,
    abilities: Abilities | None = None,
    skill_mods: dict[str, int] | None = None,
    gold: int = 0,
) -> str:
    if character_id == PLAYER:
        return "error: 'player' is reserved; use create_player"
    if character_id in world.characters:
        return f"error: character {character_id!r} already exists"
    if location_id not in world.locations:
        return f"error: location {location_id!r} does not exist"
    if hp_max <= 0:
        return f"error: hp_max must be positive (got {hp_max})"
    if hp < 0 or hp > hp_max:
        return f"error: hp {hp} out of range [0, {hp_max}]"
    if ac < 0:
        return f"error: ac cannot be negative (got {ac})"
    if gold < 0:
        return f"error: gold cannot be negative (got {gold})"
    world.characters[character_id] = Character(
        id=character_id,
        name=name,
        description=description,
        location_id=location_id,
        hp=hp,
        hp_max=hp_max,
        ac=ac,
        abilities=abilities or Abilities(),
        skill_mods=dict(skill_mods or {}),
        gold=gold,
    )
    return f"ok: created character {character_id}"


def create_player(
    world: World,
    *,
    name: str,
    description: str,
    location_id: str,
    hp: int,
    hp_max: int,
    ac: int,
    abilities: Abilities | None = None,
    skill_mods: dict[str, int] | None = None,
    gold: int = 0,
) -> str:
    if world.player is not None:
        return "error: player already exists"
    validation = _validate_actor_state(
        world,
        location_id=location_id,
        hp=hp,
        hp_max=hp_max,
        ac=ac,
        gold=gold,
    )
    if validation is not None:
        return validation
    world.player = Player(
        name=name,
        description=description,
        location_id=location_id,
        hp=hp,
        hp_max=hp_max,
        ac=ac,
        abilities=abilities or Abilities(),
        skill_mods=dict(skill_mods or {}),
        gold=gold,
    )
    return "ok: created player"


def create_item(
    world: World,
    *,
    item_id: str,
    name: str,
    description: str,
    position: ItemPosition,
    effects: dict[str, int] | None = None,
) -> str:
    if item_id in world.items:
        return f"error: item {item_id!r} already exists"
    if isinstance(position, AtLocation) and position.location_id not in world.locations:
        return f"error: location {position.location_id!r} does not exist"
    if isinstance(position, HeldBy) and not _holder_exists(
        world, position.character_id
    ):
        return f"error: character {position.character_id!r} does not exist"
    world.items[item_id] = Item(
        id=item_id,
        name=name,
        description=description,
        effects=dict(effects or {}),
        position=position,
    )
    return f"ok: created item {item_id}"


# ---------- History minting ----------


def mint_history(
    world: World,
    *,
    participants: list[str],
    description: str,
    location_id: str | None = None,
    narrative_time: str | None = None,
) -> str:
    """Append a History record. Engine assigns ``id`` and monotonic ``t``.

    Empty ``participants`` = cosmic happening that no character knows.
    The reserved participant ``"player"`` means ``world.player``.
    ``narrative_time`` defaults to ``world.narrative_time``.
    """
    for p in participants:
        if not _participant_exists(world, p):
            return f"error: participant {p!r} does not exist"
    if location_id is not None and location_id not in world.locations:
        return f"error: location {location_id!r} does not exist"
    record = History(
        id=f"h{world.next_t}",
        t=world.next_t,
        narrative_time=narrative_time or world.narrative_time,
        location_id=location_id,
        participants=list(participants),
        description=description,
    )
    world.history.append(record)
    world.next_t += 1
    return f"ok: minted {record.id}"


# ---------- State mutation ----------


def move(world: World, *, character_id: str, location_id: str) -> str:
    if character_id == PLAYER:
        return "error: use move_player for the player"
    if character_id not in world.characters:
        return f"error: character {character_id!r} does not exist"
    if location_id not in world.locations:
        return f"error: location {location_id!r} does not exist"
    world.characters[character_id].location_id = location_id
    return f"ok: moved {character_id} to {location_id}"


def move_player(world: World, *, location_id: str) -> str:
    if world.player is None:
        return "error: player does not exist"
    if location_id not in world.locations:
        return f"error: location {location_id!r} does not exist"
    world.player.location_id = location_id
    return f"ok: moved player to {location_id}"


def update_stats(
    world: World,
    *,
    character_id: str,
    hp: int | None = None,
    hp_max: int | None = None,
    ac: int | None = None,
    gold: int | None = None,
    abilities: Abilities | None = None,
    skill_mods: dict[str, int] | None = None,
) -> str:
    if character_id == PLAYER:
        return "error: use update_player_stats for the player"
    if character_id not in world.characters:
        return f"error: character {character_id!r} does not exist"
    char = world.characters[character_id]

    result = _update_actor_state(
        char,
        hp=hp,
        hp_max=hp_max,
        ac=ac,
        gold=gold,
        abilities=abilities,
        skill_mods=skill_mods,
    )
    return result if result is not None else f"ok: updated {character_id}"


def update_player_stats(
    world: World,
    *,
    hp: int | None = None,
    hp_max: int | None = None,
    ac: int | None = None,
    gold: int | None = None,
    abilities: Abilities | None = None,
    skill_mods: dict[str, int] | None = None,
) -> str:
    if world.player is None:
        return "error: player does not exist"
    result = _update_actor_state(
        world.player,
        hp=hp,
        hp_max=hp_max,
        ac=ac,
        gold=gold,
        abilities=abilities,
        skill_mods=skill_mods,
    )
    return result if result is not None else "ok: updated player"


def transfer_item(world: World, *, item_id: str, to: ItemPosition) -> str:
    if item_id not in world.items:
        return f"error: item {item_id!r} does not exist"
    if isinstance(to, AtLocation) and to.location_id not in world.locations:
        return f"error: location {to.location_id!r} does not exist"
    if isinstance(to, HeldBy) and not _holder_exists(world, to.character_id):
        return f"error: character {to.character_id!r} does not exist"
    world.items[item_id].position = to
    return f"ok: transferred {item_id}"


def update_item_description(world: World, *, item_id: str, description: str) -> str:
    if item_id not in world.items:
        return f"error: item {item_id!r} does not exist"
    world.items[item_id].description = description
    return f"ok: updated {item_id} description"


def advance_narrative_time(world: World, *, new_time: str) -> str:
    if not new_time.strip():
        return "error: narrative time cannot be empty"
    world.narrative_time = new_time
    return f"ok: time is now {new_time}"


def record_player_input(
    world: World,
    *,
    content: str,
    participants: list[str] | None = None,
    location_id: str | None = None,
    narrative_time: str | None = None,
) -> str:
    if world.player is None:
        return "error: player does not exist"
    loc = location_id if location_id is not None else world.player.location_id
    visible_to = (
        participants
        if participants is not None
        else [PLAYER, *who_is_with_player(world)]
    )
    return mint_history(
        world,
        participants=visible_to,
        description=f"{world.player.name}: {content}",
        location_id=loc,
        narrative_time=narrative_time,
    )


def who_is_with_player(world: World) -> list[str]:
    if world.player is None:
        return []
    return sorted(
        cid
        for cid, char in world.characters.items()
        if char.location_id == world.player.location_id
    )


def _participant_exists(world: World, participant: str) -> bool:
    if participant == PLAYER:
        return world.player is not None
    return participant in world.characters


def _holder_exists(world: World, holder: str) -> bool:
    return _participant_exists(world, holder)


def _validate_actor_state(
    world: World,
    *,
    location_id: str,
    hp: int,
    hp_max: int,
    ac: int,
    gold: int,
) -> str | None:
    if location_id not in world.locations:
        return f"error: location {location_id!r} does not exist"
    if hp_max <= 0:
        return f"error: hp_max must be positive (got {hp_max})"
    if hp < 0 or hp > hp_max:
        return f"error: hp {hp} out of range [0, {hp_max}]"
    if ac < 0:
        return f"error: ac cannot be negative (got {ac})"
    if gold < 0:
        return f"error: gold cannot be negative (got {gold})"
    return None


def _update_actor_state(
    actor: Player | Character,
    *,
    hp: int | None = None,
    hp_max: int | None = None,
    ac: int | None = None,
    gold: int | None = None,
    abilities: Abilities | None = None,
    skill_mods: dict[str, int] | None = None,
) -> str | None:
    if hp_max is not None and hp_max <= 0:
        return f"error: hp_max must be positive (got {hp_max})"
    if hp is not None and hp < 0:
        return "error: hp cannot be negative"
    if ac is not None and ac < 0:
        return f"error: ac cannot be negative (got {ac})"
    if gold is not None and gold < 0:
        return f"error: gold cannot be negative (got {gold})"

    new_hp_max = actor.hp_max if hp_max is None else hp_max
    if hp is not None and hp > new_hp_max:
        return f"error: hp {hp} > hp_max {new_hp_max}"

    if hp_max is not None:
        actor.hp_max = hp_max
    if hp is not None:
        actor.hp = hp
    elif hp_max is not None and actor.hp > actor.hp_max:
        actor.hp = actor.hp_max
    if ac is not None:
        actor.ac = ac
    if gold is not None:
        actor.gold = gold
    if abilities is not None:
        actor.abilities = abilities
    if skill_mods is not None:
        actor.skill_mods = dict(skill_mods)
    return None
