"""Tests for engine.delta validators and appliers."""

import pytest

from autodnd.engine.delta import (
    BootstrapDirective,
    EntitiesToCreate,
    WorldDelta,
    apply_bootstrap,
    apply_world_delta,
)
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


def _empty_world() -> WorldModel:
    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)), turn=-1
    )


def _make_bootstrap() -> BootstrapDirective:
    """A small but reference-complete bootstrap directive."""
    return BootstrapDirective(
        entities=EntitiesToCreate(
            locations=[
                Location(
                    id="inn",
                    name="Crow's Foot Inn",
                    description="Roadside inn at dusk.",
                ),
                Location(id="cap", name="Vellor capital", description="Walled city."),
            ],
            characters=[
                Character(
                    id="hadrian",
                    name="Hadrian",
                    description="Innkeeper.",
                    location_id="inn",
                    stats=CharacterStats(hp=14, ac=11),
                ),
            ],
            items=[
                Item(id="sword", name="shortsword", description="Plain blade."),
            ],
        ),
        threads=[
            Thread(id="root", name="root arc", description="Setting tension."),
            Thread(
                id="inn_night",
                parent_id="root",
                name="Night at the inn",
                description="Mara stops over.",
            ),
        ],
        backstory_events=[
            Event(
                id="e0",
                t=0,
                narrative_time="year 1043",
                location_id="cap",
                participants=[],
                description="Treaty signed.",
                thread_id="root",
            ),
            Event(
                id="e1",
                t=1,
                narrative_time="today, dusk",
                location_id="inn",
                participants=["hadrian"],
                description="Mara arrived at the inn.",
                thread_id="inn_night",
            ),
        ],
        initial_knowledge=[
            KnowledgeEntry(
                event_id="e1", text="You reached the inn at dusk.", learned_at=-1
            ),
        ],
        initial_player_state=PlayerState(
            location_id="inn",
            stats=CharacterStats(hp=24, ac=13, mods={"persuasion": 2}),
            items=["sword"],
        ),
        opening_beats=[],
    )


def _bootstrapped_world() -> WorldModel:
    world = _empty_world()
    errors = apply_bootstrap(world, _make_bootstrap())
    assert errors == []
    return world


# ---------- apply_bootstrap ----------


def test_bootstrap_happy_path():
    world = _bootstrapped_world()
    assert world.turn == 0
    assert set(world.locations) == {"inn", "cap"}
    assert world.characters["hadrian"].location_id == "inn"
    assert set(world.events) == {"e0", "e1"}
    assert world.player.location_id == "inn"
    assert world.player.knowledge[0].event_id == "e1"
    assert world.player.stats.mods["persuasion"] == 2


def test_bootstrap_rejects_when_turn_not_minus_one():
    world = _bootstrapped_world()  # turn is now 0
    errors = apply_bootstrap(world, _make_bootstrap())
    assert len(errors) == 1
    assert errors[0].code == "schema_invalid"
    assert errors[0].field_path == "world.turn"


def test_bootstrap_rejects_unknown_thread_parent():
    directive = _make_bootstrap()
    directive.threads[1].parent_id = "ghost"
    world = _empty_world()
    errors = apply_bootstrap(world, directive)
    assert any(e.code == "unknown_ref" and "parent_id" in e.field_path for e in errors)
    assert world.turn == -1  # unchanged


def test_bootstrap_rejects_player_at_unknown_location():
    directive = _make_bootstrap()
    directive.initial_player_state.location_id = "ghost"
    world = _empty_world()
    errors = apply_bootstrap(world, directive)
    assert any(
        e.code == "unknown_ref" and "initial_player_state.location_id" in e.field_path
        for e in errors
    )


def test_bootstrap_rejects_event_with_unknown_participant():
    directive = _make_bootstrap()
    directive.backstory_events[1].participants = ["ghost"]
    world = _empty_world()
    errors = apply_bootstrap(world, directive)
    assert any(
        e.code == "unknown_ref" and "participants" in e.field_path for e in errors
    )


def test_bootstrap_rejects_duplicate_event_t():
    directive = _make_bootstrap()
    directive.backstory_events[1].t = 0  # collide with e0
    world = _empty_world()
    errors = apply_bootstrap(world, directive)
    assert any(e.code == "non_monotonic_t" for e in errors)


# ---------- apply_world_delta — happy paths ----------


def test_apply_delta_mints_event_and_appends_knowledge():
    world = _bootstrapped_world()
    delta = WorldDelta(
        events_to_mint=[
            Event(
                id="e_meal",
                t=2,
                narrative_time="today, dusk + few minutes",
                location_id="inn",
                participants=["hadrian"],
                description="Mara ate stew.",
                thread_id="inn_night",
            ),
        ],
        knowledge_to_append=[
            KnowledgeEntry(event_id="e_meal", text="You ate stew.", learned_at=0),
        ],
    )
    errors = apply_world_delta(world, delta)
    assert errors == []
    assert "e_meal" in world.events
    assert world.player.knowledge[-1].event_id == "e_meal"
    assert world.turn == 1


def test_apply_delta_self_ref_to_freshly_minted_event():
    """Knowledge can reference an event minted in the same delta."""
    world = _bootstrapped_world()
    delta = WorldDelta(
        events_to_mint=[
            Event(
                id="e_new",
                t=2,
                narrative_time="now",
                location_id="inn",
                participants=[],
                description=".",
                thread_id="inn_night",
            ),
        ],
        knowledge_to_append=[KnowledgeEntry(event_id="e_new", text="…", learned_at=0)],
    )
    assert apply_world_delta(world, delta) == []


def test_apply_delta_thread_description_update():
    world = _bootstrapped_world()
    delta = WorldDelta(
        threads_to_update={"inn_night": "Hadrian has decided to betray Mara."}
    )
    assert apply_world_delta(world, delta) == []
    assert (
        world.threads["inn_night"].description == "Hadrian has decided to betray Mara."
    )


def test_apply_delta_character_move_and_stats():
    world = _bootstrapped_world()
    delta = WorldDelta(
        character_moves={"hadrian": "cap"},
        character_stats={"hadrian": CharacterStats(hp=8, ac=11)},
    )
    assert apply_world_delta(world, delta) == []
    assert world.characters["hadrian"].location_id == "cap"
    assert world.characters["hadrian"].stats.hp == 8


def test_apply_delta_player_items_added_and_removed():
    world = _bootstrapped_world()
    delta = WorldDelta(
        entities_to_create=EntitiesToCreate(
            items=[Item(id="lantern", name="lantern", description="dim")]
        ),
        player_items_added=["lantern"],
        player_items_removed=["sword"],
    )
    assert apply_world_delta(world, delta) == []
    assert "lantern" in world.player.items
    assert "sword" not in world.player.items


# ---------- apply_world_delta — rejections ----------


def test_apply_delta_rejects_duplicate_event_id():
    world = _bootstrapped_world()
    delta = WorldDelta(
        events_to_mint=[
            Event(
                id="e0",  # already exists from bootstrap
                t=2,
                narrative_time="now",
                location_id="inn",
                participants=[],
                description=".",
                thread_id="inn_night",
            ),
        ],
    )
    errors = apply_world_delta(world, delta)
    assert any(e.code == "duplicate_event_id" for e in errors)


def test_apply_delta_rejects_non_monotonic_t():
    world = _bootstrapped_world()  # max t = 1
    delta = WorldDelta(
        events_to_mint=[
            Event(
                id="e_x",
                t=1,  # not strictly greater than 1
                narrative_time="now",
                location_id="inn",
                participants=[],
                description=".",
                thread_id="inn_night",
            ),
        ],
    )
    errors = apply_world_delta(world, delta)
    assert any(e.code == "non_monotonic_t" for e in errors)


def test_apply_delta_rejects_immutable_write_on_existing_entity():
    world = _bootstrapped_world()
    delta = WorldDelta(
        entities_to_create=EntitiesToCreate(
            locations=[Location(id="inn", name="duplicate", description="?")]
        ),
    )
    errors = apply_world_delta(world, delta)
    assert any(e.code == "immutable_write" for e in errors)


def test_apply_delta_rejects_unknown_character_move():
    world = _bootstrapped_world()
    delta = WorldDelta(character_moves={"ghost": "inn"})
    errors = apply_world_delta(world, delta)
    assert any(e.code == "unknown_ref" for e in errors)


def test_apply_delta_rejects_remove_item_player_lacks():
    world = _bootstrapped_world()
    delta = WorldDelta(player_items_removed=["nonexistent"])
    errors = apply_world_delta(world, delta)
    assert any(
        e.code == "unknown_ref" and "player_items_removed" in e.field_path
        for e in errors
    )


def test_apply_delta_world_unchanged_on_failure():
    world = _bootstrapped_world()
    snapshot = world.model_dump()
    delta = WorldDelta(
        events_to_mint=[
            Event(
                id="dup",
                t=2,
                narrative_time="now",
                location_id="inn",
                participants=[],
                description=".",
                thread_id="inn_night",
            ),
            Event(
                id="dup",  # within-delta duplicate id
                t=3,
                narrative_time="now",
                location_id="inn",
                participants=[],
                description=".",
                thread_id="inn_night",
            ),
        ],
    )
    errors = apply_world_delta(world, delta)
    assert errors  # rejected
    assert world.model_dump() == snapshot  # untouched


# ---------- Marker for pytest discovery ----------


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
