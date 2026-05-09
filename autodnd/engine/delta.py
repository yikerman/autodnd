"""Per-mutation validators + appliers for AutoDND.

Each ``apply_*`` function validates a single mutation and either applies it
to ``world`` in place (returning ``None``) or rejects it (returning a
:class:`ValidationError` describing why). The Director's LLM tools wrap these
and surface the error string back to the model on failure — no all-or-nothing
turn-level rollback; the model self-corrects from inline errors.

``apply_mint_event`` auto-assigns ``Event.t`` from ``world.next_event_t``.
"""

from typing import Literal

from pydantic import BaseModel

from autodnd.engine.world import (
    Character,
    CharacterStats,
    Event,
    Item,
    Location,
    Thread,
    WorldModel,
)


class ValidationError(BaseModel):
    code: Literal[
        "immutable_write",
        "unknown_ref",
        "duplicate_id",
        "schema_invalid",
        "invalid_amount",
        "insufficient_funds",
    ]
    field_path: str
    detail: str


def _duplicate(kind: str, id: str) -> ValidationError:
    return ValidationError(
        code="duplicate_id",
        field_path=f"{kind}.id",
        detail=f"{kind.capitalize()} {id!r} already exists; canon is immutable.",
    )


def _unknown(field_path: str, detail: str) -> ValidationError:
    return ValidationError(code="unknown_ref", field_path=field_path, detail=detail)


# ---------- Creation ----------


def apply_create_location(
    world: WorldModel, *, id: str, name: str, description: str
) -> ValidationError | None:
    if id in world.locations:
        return _duplicate("location", id)
    world.locations[id] = Location(id=id, name=name, description=description)
    return None


def apply_create_character(
    world: WorldModel,
    *,
    id: str,
    name: str,
    description: str,
    location_id: str,
    stats: CharacterStats,
) -> ValidationError | None:
    if id in world.characters:
        return _duplicate("character", id)
    if location_id not in world.locations:
        return _unknown(
            "character.location_id",
            f"Character {id!r} references unknown location {location_id!r}.",
        )
    world.characters[id] = Character(
        id=id,
        name=name,
        description=description,
        location_id=location_id,
        stats=stats,
    )
    return None


def apply_create_item(
    world: WorldModel,
    *,
    id: str,
    name: str,
    description: str,
    effects: dict[str, int] | None = None,
) -> ValidationError | None:
    if id in world.items:
        return _duplicate("item", id)
    world.items[id] = Item(
        id=id, name=name, description=description, effects=effects or {}
    )
    return None


def apply_create_thread(
    world: WorldModel,
    *,
    id: str,
    name: str,
    parent_id: str | None,
    description: str,
) -> ValidationError | None:
    if id in world.threads:
        return _duplicate("thread", id)
    if parent_id is not None and parent_id not in world.threads:
        return _unknown(
            "thread.parent_id",
            f"Thread {id!r} references unknown parent thread {parent_id!r}.",
        )
    world.threads[id] = Thread(
        id=id, name=name, parent_id=parent_id, description=description
    )
    return None


def apply_mint_event(
    world: WorldModel,
    *,
    id: str,
    narrative_time: str,
    location_id: str,
    participants: list[str],
    description: str,
    thread_id: str,
) -> ValidationError | None:
    """Mint a canonical Event. Engine assigns ``Event.t`` from ``world.next_event_t``."""
    if id in world.events:
        return _duplicate("event", id)
    if location_id not in world.locations:
        return _unknown(
            "event.location_id",
            f"Event {id!r} references unknown location {location_id!r}.",
        )
    if thread_id not in world.threads:
        return _unknown(
            "event.thread_id",
            f"Event {id!r} references unknown thread {thread_id!r}.",
        )
    for p in participants:
        if p not in world.characters:
            return _unknown(
                "event.participants",
                f"Event {id!r} references unknown character {p!r}.",
            )
    world.events[id] = Event(
        id=id,
        t=world.next_event_t,
        narrative_time=narrative_time,
        location_id=location_id,
        participants=list(participants),
        description=description,
        thread_id=thread_id,
    )
    world.next_event_t += 1
    return None


# ---------- Mutation ----------


def apply_update_thread_description(
    world: WorldModel, *, id: str, description: str
) -> ValidationError | None:
    if id not in world.threads:
        return _unknown("thread.id", f"Cannot update unknown thread {id!r}.")
    world.threads[id].description = description
    return None


def apply_update_item_description(
    world: WorldModel, *, id: str, description: str
) -> ValidationError | None:
    if id not in world.items:
        return _unknown("item.id", f"Cannot update unknown item {id!r}.")
    world.items[id].description = description
    return None


def apply_move_character(
    world: WorldModel, *, id: str, location_id: str
) -> ValidationError | None:
    if id not in world.characters:
        return _unknown("character.id", f"Cannot move unknown character {id!r}.")
    if location_id not in world.locations:
        return _unknown(
            "character.location_id",
            f"Character {id!r} cannot move to unknown location {location_id!r}.",
        )
    world.characters[id].location_id = location_id
    return None


def apply_update_character_stats(
    world: WorldModel, *, id: str, stats: CharacterStats
) -> ValidationError | None:
    if id not in world.characters:
        return _unknown(
            "character.id", f"Cannot update stats of unknown character {id!r}."
        )
    world.characters[id].stats = stats
    return None


def apply_move_player(world: WorldModel, *, location_id: str) -> ValidationError | None:
    if location_id not in world.locations:
        return _unknown(
            "player.location_id",
            f"Player cannot move to unknown location {location_id!r}.",
        )
    world.player.location_id = location_id
    return None


def apply_update_player_stats(
    world: WorldModel, *, stats: CharacterStats
) -> ValidationError | None:
    world.player.stats = stats
    return None


def apply_set_player_gold(world: WorldModel, *, gold: int) -> ValidationError | None:
    if gold < 0:
        return ValidationError(
            code="invalid_amount",
            field_path="player.gold",
            detail=f"Gold cannot be negative: {gold}.",
        )
    world.player.gold = gold
    return None


def apply_gain_player_gold(world: WorldModel, *, amount: int) -> ValidationError | None:
    if amount < 0:
        return ValidationError(
            code="invalid_amount",
            field_path="player.gold",
            detail=f"Gold gain cannot be negative: {amount}.",
        )
    world.player.gold += amount
    return None


def apply_spend_player_gold(
    world: WorldModel, *, amount: int
) -> ValidationError | None:
    if amount < 0:
        return ValidationError(
            code="invalid_amount",
            field_path="player.gold",
            detail=f"Gold spend cannot be negative: {amount}.",
        )
    if amount > world.player.gold:
        return ValidationError(
            code="insufficient_funds",
            field_path="player.gold",
            detail=f"Player has {world.player.gold} gold but tried to spend {amount}.",
        )
    world.player.gold -= amount
    return None


def apply_add_player_item(world: WorldModel, *, item_id: str) -> ValidationError | None:
    if item_id not in world.items:
        return _unknown(
            "player.items", f"Cannot add unknown item {item_id!r} to player."
        )
    if item_id in world.player.items:
        return ValidationError(
            code="duplicate_id",
            field_path="player.items",
            detail=f"Player already has item {item_id!r}.",
        )
    world.player.items.append(item_id)
    return None


def apply_remove_player_item(
    world: WorldModel, *, item_id: str
) -> ValidationError | None:
    if item_id not in world.player.items:
        return _unknown(
            "player.items",
            f"Cannot remove item {item_id!r}; player does not have it.",
        )
    world.player.items.remove(item_id)
    return None


def apply_append_player_log(world: WorldModel, *, text: str) -> ValidationError | None:
    """Append an NL log entry. Cannot fail."""
    world.player.log.append(text)
    return None
