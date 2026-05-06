"""Smoke tests for engine.render.render_omniscient.

The output format is iterative; these tests pin down structural invariants
the Director's prompt depends on (sections present, names resolved instead of
raw ids, deterministic ordering, knowledge timeline rendered).
"""

from autodnd.engine.delta import (
    BootstrapDirective,
    EntitiesToCreate,
    apply_bootstrap,
)
from autodnd.engine.render import render_omniscient
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
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)),
        turn=-1,
    )


def _bootstrapped_world() -> WorldModel:
    world = _empty_world()
    directive = BootstrapDirective(
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
            items=[Item(id="sword", name="shortsword", description="Plain blade.")],
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
            KnowledgeEntry(
                event_id=None, text="You assume the kingdom is at peace.", learned_at=-1
            ),
        ],
        initial_player_state=PlayerState(
            location_id="inn",
            stats=CharacterStats(hp=24, ac=13, mods={"persuasion": 2}),
            items=["sword"],
        ),
        opening_beats=[],
    )
    assert apply_bootstrap(world, directive) == []
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


def test_render_announces_next_t():
    out = render_omniscient(_bootstrapped_world())
    # max event.t == 1, so next must be ≥ 2
    assert "Next `Event.t` must be ≥ 2" in out


def test_render_resolves_names_not_just_ids():
    out = render_omniscient(_bootstrapped_world())
    assert "Hadrian" in out
    assert "Crow's Foot Inn" in out
    assert "Vellor capital" in out
    # Participants on e1 should resolve to "Hadrian" (name) inline with the event line
    assert "(with Hadrian)" in out


def test_render_thread_nesting_is_depth_first():
    out = render_omniscient(_bootstrapped_world())
    # root thread renders before its child
    root_idx = out.index("`root` — root arc")
    child_idx = out.index("`inn_night` — Night at the inn")
    assert root_idx < child_idx
    # child uses a deeper heading level
    assert "#### `inn_night`" in out
    assert "### `root`" in out


def test_render_knowledge_timeline_includes_assumption_marker():
    out = render_omniscient(_bootstrapped_world())
    assert "[event:`e1`]" in out
    assert "[assumption]" in out
    assert "You reached the inn at dusk." in out


def test_render_player_section_shows_stats_and_items():
    out = render_omniscient(_bootstrapped_world())
    assert "HP 24, AC 13" in out
    assert "persuasion+2" in out
    assert "`sword`" in out


def test_render_empty_world():
    out = render_omniscient(_empty_world())
    assert "# World (turn -1)" in out
    assert "(no threads)" in out
    assert "(none)" in out  # locations / characters / items / player.knowledge


def test_render_is_deterministic():
    a = render_omniscient(_bootstrapped_world())
    b = render_omniscient(_bootstrapped_world())
    assert a == b
