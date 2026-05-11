"""Persistence: WorldDB round-trips and prose log append/read."""

from __future__ import annotations

from pathlib import Path

from autodnd.engine.persistence import (
    CycleProseEntry,
    append_prose,
    load_world,
    prose_log_path,
    read_prose_log,
    save_world,
)
from autodnd.engine.world import World
from autodnd.fixtures import vale_inn, waymeet_scene


def test_save_load_round_trip_vale_inn(tmp_path: Path) -> None:
    w = World()
    vale_inn(w)
    path = tmp_path / "sess.json"
    save_world(w, path)
    loaded = load_world(path)
    assert loaded.model_dump() == w.model_dump()


def test_save_load_round_trip_waymeet(tmp_path: Path) -> None:
    """Larger fixture exercises every atom type and many history records."""
    w = World()
    waymeet_scene(w)
    path = tmp_path / "waymeet.json"
    save_world(w, path)
    loaded = load_world(path)
    assert loaded.model_dump() == w.model_dump()
    assert len(loaded.history) == len(w.history)
    # Spot-check: the firewall participants survive serialization.
    silan_brief = next(
        h
        for h in loaded.history
        if h.participants == ["silan"] and "Whisperer" in h.description
    )
    assert silan_brief.participants == ["silan"]


def test_prose_log_append_and_read(tmp_path: Path) -> None:
    save_path = tmp_path / "sess.json"
    save_path.write_text("{}")  # placeholder; we're only testing prose log
    append_prose(
        save_path,
        CycleProseEntry(trigger="I look around.", blocks=["You see a bar."]),
    )
    append_prose(
        save_path,
        CycleProseEntry(
            trigger="I greet Brona.",
            blocks=["You wave to Brona.", "She nods."],
        ),
    )
    entries = read_prose_log(save_path)
    assert len(entries) == 2
    assert entries[0].trigger == "I look around."
    assert entries[1].blocks == ["You wave to Brona.", "She nods."]


def test_prose_log_path_derives_from_world_path(tmp_path: Path) -> None:
    p = prose_log_path(tmp_path / "world.json")
    assert p == tmp_path / "world.json.prose.jsonl"


def test_read_prose_log_missing_returns_empty(tmp_path: Path) -> None:
    assert read_prose_log(tmp_path / "nonexistent.json") == []
