"""Test the hardcoded inn-scene bootstrap fixture round-trips through the engine."""

from autodnd.engine.delta import apply_bootstrap
from autodnd.engine.render import render_omniscient
from autodnd.engine.world import CharacterStats, PlayerState, WorldModel
from autodnd.fixtures import inn_scene_bootstrap


def _empty_world() -> WorldModel:
    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)),
        turn=-1,
    )


def test_inn_scene_bootstrap_applies_cleanly():
    world = _empty_world()
    errors = apply_bootstrap(world, inn_scene_bootstrap())
    assert errors == [], f"unexpected validation errors: {errors}"


def test_inn_scene_bootstrap_produces_expected_world():
    world = _empty_world()
    apply_bootstrap(world, inn_scene_bootstrap())

    assert world.turn == 0
    assert len(world.locations) == 6
    assert len(world.characters) == 5
    assert len(world.items) == 4
    assert len(world.threads) == 3
    assert len(world.events) == 6
    assert len(world.player.knowledge) == 5

    assert world.player.location_id == "inn"
    # persuasion +2 lives on the persuasion_skill item, not on stats.mods
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


def test_inn_scene_bootstrap_renders_to_markdown():
    world = _empty_world()
    apply_bootstrap(world, inn_scene_bootstrap())
    out = render_omniscient(world)

    # All character names appear by name (not just id)
    for name in ("Hadrian", "Spymaster Korel", "Olwen", "Grell"):
        assert name in out

    # Hadrian's hidden role is canon (omniscient view)
    assert "Informant for Grell's bandit crew" in out

    # Knowledge timeline shows the player's POV (not the omniscient truth)
    assert "Tomas died" in out
    assert "Discretion" in out

    # Next event t hint
    assert "Next `Event.t` must be ≥ 6" in out


def test_inn_scene_bootstrap_includes_opening_beats():
    directive = inn_scene_bootstrap()
    # 5 opening beats from the worked example
    assert len(directive.opening_beats) == 5
    speakers = [b.speaker for b in directive.opening_beats if b.speaker is not None]
    assert speakers == ["Hadrian"]
    kinds = {b.kind for b in directive.opening_beats}
    assert kinds == {"observation", "action", "dialogue"}
