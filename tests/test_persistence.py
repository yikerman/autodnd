"""Tests for session save/load round-trip."""

from pathlib import Path

import pytest

from autodnd.cli.persistence import load_session, save_session
from autodnd.engine.world import CharacterStats, PlayerState, WorldModel
from autodnd.fixtures import seed_inn_scene


def _empty_world() -> WorldModel:
    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)),
        turn=-1,
    )


def test_round_trip_preserves_session(tmp_path: Path):
    world = _empty_world()
    opening = seed_inn_scene(world)
    prose = [opening, "You step inside.", "The barkeep nods."]
    path = tmp_path / "save.json"

    save_session(path, world=world, prior_prose=prose)
    snap = load_session(path)

    assert snap.world.model_dump() == world.model_dump()
    assert snap.prior_prose == prose


def test_round_trip_empty_session(tmp_path: Path):
    world = _empty_world()
    path = tmp_path / "save.json"

    save_session(path, world=world, prior_prose=[])
    snap = load_session(path)

    assert snap.world.model_dump() == world.model_dump()
    assert snap.prior_prose == []


def test_save_overwrites_existing_file(tmp_path: Path):
    world = _empty_world()
    path = tmp_path / "save.json"
    path.write_text("garbage that should be replaced", encoding="utf-8")

    save_session(path, world=world, prior_prose=["hello"])
    snap = load_session(path)

    assert snap.prior_prose == ["hello"]


def test_load_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_session(tmp_path / "nope.json")


def test_load_malformed_file_raises(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{ not valid json", encoding="utf-8")

    with pytest.raises(ValueError):
        load_session(path)


def test_save_writes_human_readable_json(tmp_path: Path):
    world = _empty_world()
    path = tmp_path / "save.json"

    save_session(path, world=world, prior_prose=["hi"])
    text = path.read_text(encoding="utf-8")

    # indented JSON contains newlines and the top-level keys
    assert "\n" in text
    assert '"prior_prose"' in text
    assert '"world"' in text
