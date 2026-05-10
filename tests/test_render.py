"""Smoke tests for engine.render.render_omniscient.

Pin down structural invariants the Director's prompt depends on (sections
present, names resolved instead of raw ids, deterministic ordering, player
log timeline rendered).
"""

from autodnd.engine.delta import (
    apply_add_player_item,
    apply_advance_narrative_time,
    apply_append_player_log,
    apply_create_character,
    apply_create_item,
    apply_create_location,
    apply_create_thread,
    apply_mint_event,
    apply_move_player,
    apply_set_player_gold,
    apply_update_player_stats,
)
from autodnd.engine.render import render_omniscient
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


def _bootstrapped_world() -> WorldModel:
    world = _empty_world()
    apply_create_location(
        world, id="inn", name="Crow's Foot Inn", description="Roadside inn at dusk."
    )
    apply_create_location(
        world, id="cap", name="Vellor capital", description="Walled city."
    )
    apply_create_thread(
        world,
        id="root",
        name="root arc",
        parent_id=None,
        description="Setting tension.",
    )
    apply_create_thread(
        world,
        id="inn_night",
        name="Night at the inn",
        parent_id="root",
        description="Mara stops over.",
    )
    apply_create_character(
        world,
        id="hadrian",
        name="Hadrian",
        description="Innkeeper.",
        location_id="inn",
        stats=CharacterStats(hp=14, ac=11),
    )
    apply_create_item(world, id="sword", name="shortsword", description="Plain blade.")
    apply_mint_event(
        world,
        id="e0",
        narrative_time="year 1043",
        location_id="cap",
        participants=[],
        description="Treaty signed.",
        thread_id="root",
    )
    apply_mint_event(
        world,
        id="e1",
        narrative_time="today, dusk",
        location_id="inn",
        participants=["hadrian"],
        description="Mara arrived at the inn.",
        thread_id="inn_night",
    )
    apply_move_player(world, location_id="inn")
    apply_update_player_stats(
        world, stats=CharacterStats(hp=24, ac=13, mods={"persuasion": 2})
    )
    apply_set_player_gold(world, gold=50)
    apply_add_player_item(world, item_id="sword")
    apply_append_player_log(world, text="You reached the inn at dusk.")
    apply_append_player_log(world, text="You assume the kingdom is at peace.")
    apply_advance_narrative_time(world, to="today, dusk")
    world.turn = 0
    return world


def test_render_includes_top_level_sections():
    out = render_omniscient(_bootstrapped_world())
    for header in (
        "# World (turn 0)",
        "## Threads",
        "## Characters",
        "## Locations",
        "## Items",
        "## Player",
    ):
        assert header in out, f"missing section: {header!r}"


def test_render_resolves_names_not_just_ids():
    out = render_omniscient(_bootstrapped_world())
    assert "Hadrian" in out
    assert "Crow's Foot Inn" in out
    assert "Vellor capital" in out
    assert "(with Hadrian)" in out


def test_render_thread_nesting_is_depth_first():
    out = render_omniscient(_bootstrapped_world())
    root_idx = out.index("`root` — root arc")
    child_idx = out.index("`inn_night` — Night at the inn")
    assert root_idx < child_idx
    assert "#### `inn_night`" in out
    assert "### `root`" in out


def test_render_player_log_appears_in_order():
    out = render_omniscient(_bootstrapped_world())
    assert "Player log" in out
    inn_idx = out.index("You reached the inn at dusk.")
    assume_idx = out.index("You assume the kingdom is at peace.")
    assert inn_idx < assume_idx


def test_render_player_section_shows_stats_and_items():
    out = render_omniscient(_bootstrapped_world())
    assert "HP 24, AC 13" in out
    assert "Gold: 50" in out
    assert "persuasion+2" in out
    assert "`sword`" in out


def test_render_empty_world():
    out = render_omniscient(_empty_world())
    assert "# World (turn -1)" in out
    assert "(no threads)" in out
    assert "(none)" in out  # locations / characters / items / player.log


def test_render_shows_world_clock_when_set():
    out = render_omniscient(_bootstrapped_world())
    assert "Now: today, dusk" in out


def test_render_shows_unset_clock_on_empty_world():
    out = render_omniscient(_empty_world())
    assert "Now: (unset)" in out


def test_render_shows_last_event_per_thread_with_events():
    out = render_omniscient(_bootstrapped_world())
    # Thread `inn_night` has one event at "today, dusk".
    assert "Last event: today, dusk" in out


def test_render_omits_last_event_for_threads_without_events():
    """A thread with no events should not produce a 'Last event:' line."""
    world = _empty_world()
    apply_create_thread(
        world, id="quiet", name="Quiet", parent_id=None, description="Nothing yet."
    )
    out = render_omniscient(world)
    # The thread renders, but no "Last event:" line for it.
    assert "`quiet`" in out
    assert "Last event:" not in out


def test_render_is_deterministic():
    a = render_omniscient(_bootstrapped_world())
    b = render_omniscient(_bootstrapped_world())
    assert a == b
