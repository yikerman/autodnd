"""WorldDelta / BootstrapDirective schemas + validators.

Source of truth: ``plan/PLAN.md`` "Flow" and "Schemas" sections, and the
per-field mutability table in "Why this shape".

Two entry points:

- :func:`apply_world_delta` — per-turn mutations.
- :func:`apply_bootstrap` — game start; requires ``world.turn == -1``.

Both return ``list[ValidationError]``. Empty list = success and the world is
mutated in place. Non-empty list = world is unchanged.
"""

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, Field

from autodnd.engine.world import (
    Character,
    CharacterStats,
    Event,
    Item,
    KnowledgeEntry,
    Location,
    PlayerState,
    Thread,
    WorldModel,
)


# ---------- Schemas ----------


class Beat(BaseModel):
    kind: Literal["action", "dialogue", "observation", "transition"]
    text: str
    speaker: str | None = None  # display name, not character id


class EntitiesToCreate(BaseModel):
    locations: list[Location] = Field(default_factory=list)
    characters: list[Character] = Field(default_factory=list)
    items: list[Item] = Field(default_factory=list)


class WorldDelta(BaseModel):
    # Append-only / additive
    events_to_mint: list[Event] = Field(default_factory=list)
    knowledge_to_append: list[KnowledgeEntry] = Field(default_factory=list)
    threads_to_create: list[Thread] = Field(default_factory=list)
    entities_to_create: EntitiesToCreate = Field(default_factory=EntitiesToCreate)

    # In-place mutations of mutable fields (per the policy table)
    threads_to_update: dict[str, str] = Field(default_factory=dict)
    character_moves: dict[str, str] = Field(default_factory=dict)
    character_stats: dict[str, CharacterStats] = Field(default_factory=dict)
    player_moves_to: str | None = None
    player_stats: CharacterStats | None = None
    player_items_added: list[str] = Field(default_factory=list)
    player_items_removed: list[str] = Field(default_factory=list)
    items_to_update: dict[str, str] = Field(
        default_factory=dict
    )  # item_id → new description


class TurnDirective(BaseModel):
    beats: list[Beat] = Field(default_factory=list)
    world_delta: WorldDelta = Field(default_factory=WorldDelta)
    end_scene: bool = False


class BootstrapDirective(BaseModel):
    """Emitted once at game start (world.turn = -1). Distinct from
    :class:`TurnDirective`: bootstrap mints the whole world and the opening
    beats in one shot, with no prior world to mutate."""

    entities: EntitiesToCreate
    threads: list[Thread] = Field(default_factory=list)
    backstory_events: list[Event] = Field(default_factory=list)
    initial_knowledge: list[KnowledgeEntry] = Field(default_factory=list)
    initial_player_state: PlayerState
    opening_beats: list[Beat] = Field(default_factory=list)


class ValidationError(BaseModel):
    code: Literal[
        "immutable_write",
        "unknown_ref",
        "duplicate_event_id",
        "non_monotonic_t",
        "schema_invalid",
    ]
    field_path: str
    detail: str


# ---------- Validators / appliers ----------


def apply_bootstrap(
    world: WorldModel, directive: BootstrapDirective
) -> list[ValidationError]:
    """Initialize ``world`` from ``directive``. Requires ``world.turn == -1``.

    Returns ``[]`` on success (world mutated in place); non-empty list of
    :class:`ValidationError` on failure (world unchanged).
    """
    errors: list[ValidationError] = []

    if world.turn != -1:
        return [
            ValidationError(
                code="schema_invalid",
                field_path="world.turn",
                detail=f"Bootstrap requires world.turn == -1; got {world.turn}.",
            )
        ]

    # Within-list duplicate ids
    loc_ids = _collect_unique_ids(
        directive.entities.locations, "entities.locations", "location", errors
    )
    item_ids = _collect_unique_ids(
        directive.entities.items, "entities.items", "item", errors
    )
    char_ids = _collect_unique_ids(
        directive.entities.characters, "entities.characters", "character", errors
    )
    thread_ids = _collect_unique_ids(directive.threads, "threads", "thread", errors)

    event_ids: set[str] = set()
    event_t_values: set[int] = set()
    for i, ev in enumerate(directive.backstory_events):
        if ev.id in event_ids:
            errors.append(
                ValidationError(
                    code="duplicate_event_id",
                    field_path=f"backstory_events[{i}].id",
                    detail=f"Duplicate event id {ev.id!r} within directive.",
                )
            )
        event_ids.add(ev.id)
        if ev.t in event_t_values:
            errors.append(
                ValidationError(
                    code="non_monotonic_t",
                    field_path=f"backstory_events[{i}].t",
                    detail=f"Duplicate Event.t={ev.t} within directive.",
                )
            )
        event_t_values.add(ev.t)

    # Cross-ref validation (everything resolves within the directive)
    for i, char in enumerate(directive.entities.characters):
        if char.location_id not in loc_ids:
            errors.append(
                _unknown(
                    f"entities.characters[{i}].location_id",
                    char.id,
                    "location",
                    char.location_id,
                )
            )

    for i, thr in enumerate(directive.threads):
        if thr.parent_id is not None and thr.parent_id not in thread_ids:
            errors.append(
                _unknown(
                    f"threads[{i}].parent_id", thr.id, "parent thread", thr.parent_id
                )
            )

    for i, ev in enumerate(directive.backstory_events):
        if ev.location_id not in loc_ids:
            errors.append(
                _unknown(
                    f"backstory_events[{i}].location_id",
                    ev.id,
                    "location",
                    ev.location_id,
                )
            )
        for j, p in enumerate(ev.participants):
            if p not in char_ids:
                errors.append(
                    _unknown(
                        f"backstory_events[{i}].participants[{j}]",
                        ev.id,
                        "character",
                        p,
                    )
                )
        if ev.thread_id not in thread_ids:
            errors.append(
                _unknown(
                    f"backstory_events[{i}].thread_id", ev.id, "thread", ev.thread_id
                )
            )

    for i, ke in enumerate(directive.initial_knowledge):
        if ke.event_id is not None and ke.event_id not in event_ids:
            errors.append(
                _unknown(
                    f"initial_knowledge[{i}].event_id",
                    "<knowledge>",
                    "event",
                    ke.event_id,
                )
            )

    if directive.initial_player_state.location_id not in loc_ids:
        errors.append(
            _unknown(
                "initial_player_state.location_id",
                "<player>",
                "location",
                directive.initial_player_state.location_id,
            )
        )
    for i, item_id in enumerate(directive.initial_player_state.items):
        if item_id not in item_ids:
            errors.append(
                _unknown(
                    f"initial_player_state.items[{i}]", "<player>", "item", item_id
                )
            )
    for i, ke in enumerate(directive.initial_player_state.knowledge):
        if ke.event_id is not None and ke.event_id not in event_ids:
            errors.append(
                _unknown(
                    f"initial_player_state.knowledge[{i}].event_id",
                    "<knowledge>",
                    "event",
                    ke.event_id,
                )
            )

    if errors:
        return errors

    world.locations = {loc.id: loc for loc in directive.entities.locations}
    world.items = {item.id: item for item in directive.entities.items}
    world.characters = {char.id: char for char in directive.entities.characters}
    world.threads = {thr.id: thr for thr in directive.threads}
    world.events = {ev.id: ev for ev in directive.backstory_events}

    merged_knowledge = list(directive.initial_player_state.knowledge) + list(
        directive.initial_knowledge
    )
    world.player = directive.initial_player_state.model_copy(
        update={"knowledge": merged_knowledge}
    )
    world.turn = 0
    return []


def apply_world_delta(world: WorldModel, delta: WorldDelta) -> list[ValidationError]:
    """Validate and apply ``delta`` to ``world``, advancing ``world.turn`` by 1.

    Returns ``[]`` on success (world mutated in place); non-empty list of
    :class:`ValidationError` on failure (world unchanged).
    """
    errors: list[ValidationError] = []

    new_loc_ids = _check_creates_against(
        delta.entities_to_create.locations,
        world.locations,
        "entities_to_create.locations",
        "location",
        errors,
    )
    new_item_ids = _check_creates_against(
        delta.entities_to_create.items,
        world.items,
        "entities_to_create.items",
        "item",
        errors,
    )
    new_char_ids = _check_creates_against(
        delta.entities_to_create.characters,
        world.characters,
        "entities_to_create.characters",
        "character",
        errors,
    )
    new_thread_ids = _check_creates_against(
        delta.threads_to_create,
        world.threads,
        "threads_to_create",
        "thread",
        errors,
    )

    # Events: also check t monotonicity
    existing_max_t = max((e.t for e in world.events.values()), default=-1)
    new_event_ids: set[str] = set()
    new_event_t_values: set[int] = set()
    for i, ev in enumerate(delta.events_to_mint):
        if ev.id in world.events:
            errors.append(
                ValidationError(
                    code="duplicate_event_id",
                    field_path=f"events_to_mint[{i}].id",
                    detail=f"Event id {ev.id!r} already exists.",
                )
            )
        if ev.id in new_event_ids:
            errors.append(
                ValidationError(
                    code="duplicate_event_id",
                    field_path=f"events_to_mint[{i}].id",
                    detail=f"Duplicate event id {ev.id!r} within directive.",
                )
            )
        new_event_ids.add(ev.id)
        if ev.t <= existing_max_t:
            errors.append(
                ValidationError(
                    code="non_monotonic_t",
                    field_path=f"events_to_mint[{i}].t",
                    detail=f"Event.t={ev.t} not strictly greater than current max ({existing_max_t}).",
                )
            )
        if ev.t in new_event_t_values:
            errors.append(
                ValidationError(
                    code="non_monotonic_t",
                    field_path=f"events_to_mint[{i}].t",
                    detail=f"Duplicate Event.t={ev.t} within directive.",
                )
            )
        new_event_t_values.add(ev.t)

    would_locations = set(world.locations) | new_loc_ids
    would_items = set(world.items) | new_item_ids
    would_characters = set(world.characters) | new_char_ids
    would_threads = set(world.threads) | new_thread_ids
    would_events = set(world.events) | new_event_ids

    # Refs in newly-created entities
    for i, char in enumerate(delta.entities_to_create.characters):
        if char.location_id not in would_locations:
            errors.append(
                _unknown(
                    f"entities_to_create.characters[{i}].location_id",
                    char.id,
                    "location",
                    char.location_id,
                )
            )

    for i, thr in enumerate(delta.threads_to_create):
        if thr.parent_id is not None and thr.parent_id not in would_threads:
            errors.append(
                _unknown(
                    f"threads_to_create[{i}].parent_id",
                    thr.id,
                    "parent thread",
                    thr.parent_id,
                )
            )

    for i, ev in enumerate(delta.events_to_mint):
        if ev.location_id not in would_locations:
            errors.append(
                _unknown(
                    f"events_to_mint[{i}].location_id",
                    ev.id,
                    "location",
                    ev.location_id,
                )
            )
        for j, p in enumerate(ev.participants):
            if p not in would_characters:
                errors.append(
                    _unknown(
                        f"events_to_mint[{i}].participants[{j}]", ev.id, "character", p
                    )
                )
        if ev.thread_id not in would_threads:
            errors.append(
                _unknown(
                    f"events_to_mint[{i}].thread_id", ev.id, "thread", ev.thread_id
                )
            )

    # Refs in mutations
    for i, ke in enumerate(delta.knowledge_to_append):
        if ke.event_id is not None and ke.event_id not in would_events:
            errors.append(
                _unknown(
                    f"knowledge_to_append[{i}].event_id",
                    "<knowledge>",
                    "event",
                    ke.event_id,
                )
            )

    for thread_id in delta.threads_to_update:
        if thread_id not in would_threads:
            errors.append(
                _unknown(
                    f"threads_to_update[{thread_id!r}]", thread_id, "thread", thread_id
                )
            )

    for char_id, new_loc in delta.character_moves.items():
        if char_id not in would_characters:
            errors.append(
                _unknown(f"character_moves[{char_id!r}]", char_id, "character", char_id)
            )
        if new_loc not in would_locations:
            errors.append(
                ValidationError(
                    code="unknown_ref",
                    field_path=f"character_moves[{char_id!r}]",
                    detail=f"Character {char_id!r} cannot move to unknown location {new_loc!r}.",
                )
            )

    for char_id in delta.character_stats:
        if char_id not in would_characters:
            errors.append(
                _unknown(f"character_stats[{char_id!r}]", char_id, "character", char_id)
            )

    if (
        delta.player_moves_to is not None
        and delta.player_moves_to not in would_locations
    ):
        errors.append(
            ValidationError(
                code="unknown_ref",
                field_path="player_moves_to",
                detail=f"Player cannot move to unknown location {delta.player_moves_to!r}.",
            )
        )

    for i, item_id in enumerate(delta.player_items_added):
        if item_id not in would_items:
            errors.append(
                _unknown(f"player_items_added[{i}]", "<player>", "item", item_id)
            )

    for i, item_id in enumerate(delta.player_items_removed):
        if item_id not in world.player.items:
            errors.append(
                ValidationError(
                    code="unknown_ref",
                    field_path=f"player_items_removed[{i}]",
                    detail=f"Cannot remove item {item_id!r}; player does not have it.",
                )
            )

    for item_id in delta.items_to_update:
        if item_id not in would_items:
            errors.append(
                _unknown(f"items_to_update[{item_id!r}]", item_id, "item", item_id)
            )

    if errors:
        return errors

    # Apply
    for loc in delta.entities_to_create.locations:
        world.locations[loc.id] = loc
    for item in delta.entities_to_create.items:
        world.items[item.id] = item
    for char in delta.entities_to_create.characters:
        world.characters[char.id] = char
    for thr in delta.threads_to_create:
        world.threads[thr.id] = thr
    for ev in delta.events_to_mint:
        world.events[ev.id] = ev

    for ke in delta.knowledge_to_append:
        world.player.knowledge.append(ke)

    for thread_id, new_desc in delta.threads_to_update.items():
        world.threads[thread_id].description = new_desc
    for char_id, new_loc in delta.character_moves.items():
        world.characters[char_id].location_id = new_loc
    for char_id, new_stats in delta.character_stats.items():
        world.characters[char_id].stats = new_stats

    if delta.player_moves_to is not None:
        world.player.location_id = delta.player_moves_to
    if delta.player_stats is not None:
        world.player.stats = delta.player_stats

    world.player.items.extend(delta.player_items_added)
    for item_id in delta.player_items_removed:
        world.player.items.remove(item_id)

    for item_id, new_desc in delta.items_to_update.items():
        world.items[item_id].description = new_desc

    world.turn += 1
    return []


# ---------- Helpers ----------


class _HasId(Protocol):
    id: str


_T = TypeVar("_T", bound=_HasId)


def _collect_unique_ids(
    items: Sequence[_T], field_prefix: str, kind: str, errors: list[ValidationError]
) -> set[str]:
    seen: set[str] = set()
    for i, obj in enumerate(items):
        if obj.id in seen:
            errors.append(
                ValidationError(
                    code="immutable_write",
                    field_path=f"{field_prefix}[{i}].id",
                    detail=f"Duplicate {kind} id {obj.id!r} within directive.",
                )
            )
        seen.add(obj.id)
    return seen


def _check_creates_against(
    items: Sequence[_T],
    existing: Mapping[str, object],
    field_prefix: str,
    kind: str,
    errors: list[ValidationError],
) -> set[str]:
    new_ids: set[str] = set()
    for i, obj in enumerate(items):
        if obj.id in existing:
            errors.append(
                ValidationError(
                    code="immutable_write",
                    field_path=f"{field_prefix}[{i}].id",
                    detail=f"{kind.capitalize()} id {obj.id!r} already exists; canon is immutable.",
                )
            )
        if obj.id in new_ids:
            errors.append(
                ValidationError(
                    code="immutable_write",
                    field_path=f"{field_prefix}[{i}].id",
                    detail=f"Duplicate {kind} id {obj.id!r} within directive.",
                )
            )
        new_ids.add(obj.id)
    return new_ids


def _unknown(field_path: str, owner_id: str, kind: str, ref: str) -> ValidationError:
    return ValidationError(
        code="unknown_ref",
        field_path=field_path,
        detail=f"{owner_id!r} references unknown {kind} {ref!r}.",
    )
