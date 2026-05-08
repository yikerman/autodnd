"""Tests for the inn-scene seed fixture."""

from autodnd.engine.render import render_omniscient
from autodnd.engine.world import CharacterStats, PlayerState, WorldModel
from autodnd.fixtures import seed_inn_scene


def _empty_world() -> WorldModel:
    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)),
        turn=-1,
    )


def test_seed_inn_scene_seeds_full_world():
    world = _empty_world()
    prose = seed_inn_scene(world)

    assert world.turn == 0
    assert len(world.locations) == 6
    assert len(world.characters) == 5
    assert len(world.items) == 3
    assert len(world.threads) == 3
    assert len(world.events) == 6
    assert len(world.player.log) == 5
    assert world.next_event_t == 6  # 6 events minted at t=0..5

    assert world.player.location_id == "inn"
    assert world.player.gold == 50
    # persuasion +2 lives on the persuasion_skill item's effects
    assert world.items["persuasion_skill"].effects == {"persuasion": 2}
    assert "persuasion_skill" in world.player.items
    assert "sealed_letter" in world.player.items

    # Thread forest: vellor_sken_tensions → courier_mission → inn_night
    assert world.threads["vellor_sken_tensions"].parent_id is None
    assert world.threads["courier_mission"].parent_id == "vellor_sken_tensions"
    assert world.threads["inn_night"].parent_id == "courier_mission"

    # Events ordered by t monotonically
    ts = sorted(e.t for e in world.events.values())
    assert ts == [0, 1, 2, 3, 4, 5]

    # Returns non-empty opening prose mentioning the inn
    assert prose
    assert "Crow's Foot" in prose


def test_seed_inn_scene_renders_to_markdown():
    world = _empty_world()
    seed_inn_scene(world)
    out = render_omniscient(world)

    for name in ("Hadrian", "Spymaster Korel", "Olwen", "Grell"):
        assert name in out

    # Hadrian's hidden role is canon (omniscient view)
    assert "Informant for Grell's bandit crew" in out

    # Player log shows the player's POV
    assert "Tomas died" in out
    assert "Discretion" in out
