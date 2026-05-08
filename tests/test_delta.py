"""Tests for engine.delta per-mutation validators and appliers."""

import pytest

from autodnd.engine.delta import (
    apply_add_player_item,
    apply_append_player_log,
    apply_create_character,
    apply_create_item,
    apply_create_location,
    apply_create_thread,
    apply_mint_event,
    apply_move_character,
    apply_move_player,
    apply_remove_player_item,
    apply_gain_player_gold,
    apply_set_player_gold,
    apply_spend_player_gold,
    apply_update_character_stats,
    apply_update_item_description,
    apply_update_player_stats,
    apply_update_thread_description,
)
from autodnd.engine.world import (
    CharacterStats,
    PlayerState,
    WorldModel,
)


def _empty_world() -> WorldModel:
    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)),
        turn=-1,
    )


def _seeded_world() -> WorldModel:
    """Small world: 2 locations, 2 threads, 1 character, 1 item, 1 event already minted,
    player at the inn with the sword and a persuasion mod."""
    world = _empty_world()
    assert (
        apply_create_location(
            world, id="inn", name="Inn", description="A roadside inn."
        )
        is None
    )
    assert (
        apply_create_location(
            world, id="cap", name="Capital", description="Walled city."
        )
        is None
    )
    assert (
        apply_create_thread(
            world, id="root", name="root arc", parent_id=None, description="..."
        )
        is None
    )
    assert (
        apply_create_thread(
            world,
            id="inn_night",
            name="Inn night",
            parent_id="root",
            description="...",
        )
        is None
    )
    assert (
        apply_create_character(
            world,
            id="hadrian",
            name="Hadrian",
            description="Innkeeper.",
            location_id="inn",
            stats=CharacterStats(hp=14, ac=11),
        )
        is None
    )
    assert (
        apply_create_item(
            world, id="sword", name="shortsword", description="Plain blade."
        )
        is None
    )
    assert (
        apply_mint_event(
            world,
            id="e0",
            narrative_time="year 1043",
            location_id="cap",
            participants=[],
            description="Treaty signed.",
            thread_id="root",
        )
        is None
    )
    assert apply_move_player(world, location_id="inn") is None
    assert (
        apply_update_player_stats(
            world, stats=CharacterStats(hp=24, ac=13, mods={"persuasion": 2})
        )
        is None
    )
    assert apply_add_player_item(world, item_id="sword") is None
    return world


# ---------- Creation ----------


def test_create_location_minted_into_world():
    world = _empty_world()
    err = apply_create_location(world, id="inn", name="Inn", description="...")
    assert err is None
    assert world.locations["inn"].name == "Inn"


def test_create_location_rejects_duplicate():
    world = _seeded_world()
    err = apply_create_location(world, id="inn", name="Other", description="...")
    assert err is not None
    assert err.code == "duplicate_id"


def test_create_character_rejects_unknown_location():
    world = _empty_world()
    err = apply_create_character(
        world,
        id="ghost",
        name="Ghost",
        description="...",
        location_id="nowhere",
        stats=CharacterStats(hp=1, ac=10),
    )
    assert err is not None
    assert err.code == "unknown_ref"
    assert "location" in err.detail


def test_create_character_rejects_duplicate():
    world = _seeded_world()
    err = apply_create_character(
        world,
        id="hadrian",
        name="Other",
        description="...",
        location_id="inn",
        stats=CharacterStats(hp=1, ac=10),
    )
    assert err is not None
    assert err.code == "duplicate_id"


def test_create_thread_rejects_unknown_parent():
    world = _empty_world()
    err = apply_create_thread(
        world, id="child", name="Child", parent_id="phantom", description="..."
    )
    assert err is not None
    assert err.code == "unknown_ref"


def test_create_thread_root_is_ok_without_parent():
    world = _empty_world()
    err = apply_create_thread(
        world, id="root", name="Root", parent_id=None, description="..."
    )
    assert err is None
    assert world.threads["root"].parent_id is None


def test_create_item_with_effects():
    world = _empty_world()
    err = apply_create_item(
        world,
        id="persuasion_skill",
        name="persuasion",
        description="trained.",
        effects={"persuasion": 2},
    )
    assert err is None
    assert world.items["persuasion_skill"].effects["persuasion"] == 2


def test_create_item_defaults_effects_to_empty():
    world = _empty_world()
    err = apply_create_item(world, id="sword", name="sword", description="plain.")
    assert err is None
    assert world.items["sword"].effects == {}


# ---------- mint_event ----------


def test_mint_event_assigns_t_monotonically():
    world = _seeded_world()  # already minted e0 at t=0
    assert world.events["e0"].t == 0
    assert world.next_event_t == 1
    err = apply_mint_event(
        world,
        id="e1",
        narrative_time="dusk",
        location_id="inn",
        participants=["hadrian"],
        description="...",
        thread_id="inn_night",
    )
    assert err is None
    assert world.events["e1"].t == 1
    assert world.next_event_t == 2


def test_mint_event_rejects_duplicate_id():
    world = _seeded_world()
    err = apply_mint_event(
        world,
        id="e0",
        narrative_time="now",
        location_id="inn",
        participants=[],
        description="...",
        thread_id="root",
    )
    assert err is not None
    assert err.code == "duplicate_id"
    # next_event_t should NOT advance on rejection
    assert world.next_event_t == 1


def test_mint_event_rejects_unknown_participant():
    world = _seeded_world()
    err = apply_mint_event(
        world,
        id="e_x",
        narrative_time="now",
        location_id="inn",
        participants=["ghost"],
        description="...",
        thread_id="inn_night",
    )
    assert err is not None
    assert err.code == "unknown_ref"
    assert "ghost" in err.detail


def test_mint_event_rejects_unknown_thread():
    world = _seeded_world()
    err = apply_mint_event(
        world,
        id="e_x",
        narrative_time="now",
        location_id="inn",
        participants=[],
        description="...",
        thread_id="phantom",
    )
    assert err is not None
    assert err.code == "unknown_ref"


def test_mint_event_rejects_unknown_location():
    world = _seeded_world()
    err = apply_mint_event(
        world,
        id="e_x",
        narrative_time="now",
        location_id="nowhere",
        participants=[],
        description="...",
        thread_id="inn_night",
    )
    assert err is not None
    assert err.code == "unknown_ref"


# ---------- Mutation ----------


def test_update_thread_description():
    world = _seeded_world()
    err = apply_update_thread_description(
        world, id="inn_night", description="Hadrian has decided to betray Mara."
    )
    assert err is None
    assert world.threads["inn_night"].description.startswith("Hadrian")


def test_update_thread_description_rejects_unknown():
    world = _empty_world()
    err = apply_update_thread_description(world, id="ghost", description="...")
    assert err is not None
    assert err.code == "unknown_ref"


def test_update_item_description():
    world = _seeded_world()
    err = apply_update_item_description(world, id="sword", description="Bloodied.")
    assert err is None
    assert world.items["sword"].description == "Bloodied."


def test_update_item_description_rejects_unknown():
    world = _empty_world()
    err = apply_update_item_description(world, id="ghost", description="...")
    assert err is not None
    assert err.code == "unknown_ref"


def test_move_character():
    world = _seeded_world()
    err = apply_move_character(world, id="hadrian", location_id="cap")
    assert err is None
    assert world.characters["hadrian"].location_id == "cap"


def test_move_character_rejects_unknown_character():
    world = _empty_world()
    err = apply_move_character(world, id="ghost", location_id="anywhere")
    assert err is not None
    assert err.code == "unknown_ref"


def test_move_character_rejects_unknown_location():
    world = _seeded_world()
    err = apply_move_character(world, id="hadrian", location_id="nowhere")
    assert err is not None
    assert err.code == "unknown_ref"


def test_update_character_stats():
    world = _seeded_world()
    err = apply_update_character_stats(
        world, id="hadrian", stats=CharacterStats(hp=8, ac=11)
    )
    assert err is None
    assert world.characters["hadrian"].stats.hp == 8


def test_update_character_stats_rejects_unknown():
    world = _empty_world()
    err = apply_update_character_stats(
        world, id="ghost", stats=CharacterStats(hp=1, ac=10)
    )
    assert err is not None
    assert err.code == "unknown_ref"


def test_move_player():
    world = _seeded_world()
    err = apply_move_player(world, location_id="cap")
    assert err is None
    assert world.player.location_id == "cap"


def test_move_player_rejects_unknown_location():
    world = _empty_world()
    err = apply_move_player(world, location_id="nowhere")
    assert err is not None
    assert err.code == "unknown_ref"


def test_update_player_stats():
    world = _seeded_world()
    err = apply_update_player_stats(world, stats=CharacterStats(hp=10, ac=13))
    assert err is None
    assert world.player.stats.hp == 10


def test_set_player_gold():
    world = _seeded_world()
    err = apply_set_player_gold(world, gold=12)
    assert err is None
    assert world.player.gold == 12


def test_set_player_gold_rejects_negative():
    world = _seeded_world()
    err = apply_set_player_gold(world, gold=-1)
    assert err is not None
    assert err.code == "invalid_amount"
    assert world.player.gold == 0


def test_gain_player_gold():
    world = _seeded_world()
    apply_set_player_gold(world, gold=3)
    err = apply_gain_player_gold(world, amount=7)
    assert err is None
    assert world.player.gold == 10


def test_gain_player_gold_rejects_negative():
    world = _seeded_world()
    err = apply_gain_player_gold(world, amount=-1)
    assert err is not None
    assert err.code == "invalid_amount"
    assert world.player.gold == 0


def test_spend_player_gold():
    world = _seeded_world()
    apply_set_player_gold(world, gold=10)
    err = apply_spend_player_gold(world, amount=4)
    assert err is None
    assert world.player.gold == 6


def test_spend_player_gold_rejects_negative():
    world = _seeded_world()
    apply_set_player_gold(world, gold=10)
    err = apply_spend_player_gold(world, amount=-1)
    assert err is not None
    assert err.code == "invalid_amount"
    assert world.player.gold == 10


def test_spend_player_gold_rejects_insufficient_funds():
    world = _seeded_world()
    apply_set_player_gold(world, gold=3)
    err = apply_spend_player_gold(world, amount=4)
    assert err is not None
    assert err.code == "insufficient_funds"
    assert world.player.gold == 3


def test_add_player_item():
    world = _seeded_world()
    apply_create_item(world, id="lantern", name="lantern", description="dim.")
    err = apply_add_player_item(world, item_id="lantern")
    assert err is None
    assert "lantern" in world.player.items


def test_add_player_item_rejects_unknown():
    world = _empty_world()
    err = apply_add_player_item(world, item_id="phantom")
    assert err is not None
    assert err.code == "unknown_ref"


def test_add_player_item_rejects_duplicate():
    world = _seeded_world()  # already has "sword"
    err = apply_add_player_item(world, item_id="sword")
    assert err is not None
    assert err.code == "duplicate_id"


def test_remove_player_item():
    world = _seeded_world()
    err = apply_remove_player_item(world, item_id="sword")
    assert err is None
    assert "sword" not in world.player.items


def test_remove_player_item_rejects_not_held():
    world = _seeded_world()
    err = apply_remove_player_item(world, item_id="phantom")
    assert err is not None
    assert err.code == "unknown_ref"


def test_append_player_log():
    world = _empty_world()
    err = apply_append_player_log(world, text="You arrived.")
    assert err is None
    assert world.player.log == ["You arrived."]


# ---------- Sequencing: create-then-reference within a turn ----------


def test_create_then_reference_within_turn():
    """An entity created mid-turn is immediately available to subsequent calls.
    No more all-or-nothing atomicity — tool calls compose freely."""
    world = _empty_world()
    apply_create_location(world, id="inn", name="Inn", description="...")
    apply_create_thread(world, id="t", name="t", parent_id=None, description="...")
    err = apply_create_character(
        world,
        id="h",
        name="H",
        description="...",
        location_id="inn",
        stats=CharacterStats(hp=10, ac=10),
    )
    assert err is None
    err = apply_mint_event(
        world,
        id="e",
        narrative_time="now",
        location_id="inn",
        participants=["h"],
        description="...",
        thread_id="t",
    )
    assert err is None
    assert world.events["e"].t == 0


# ---------- Marker for pytest discovery ----------


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
