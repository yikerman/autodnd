"""Tests for the JSONL trace logger."""

import json
import random

import pytest

from autodnd.engine.delta import TurnDirective
from autodnd.engine.world import CharacterStats, PlayerState, WorldModel
from autodnd.llm import tracing
from autodnd.llm.director import run_turn_director
from tests.test_agents import _text_responder


@pytest.fixture(autouse=True)
def _isolate_tracing(monkeypatch: pytest.MonkeyPatch):
    """Reset module state and ensure default-disabled in tests unless explicitly enabled."""
    monkeypatch.delenv("AUTODND_TRACE", raising=False)
    tracing.reset_for_tests()
    yield
    tracing.reset_for_tests()


def _empty_world() -> WorldModel:
    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)), turn=0
    )


def test_init_creates_trace_file(tmp_path):
    path = tracing.init(tmp_path / "logs")
    assert path is not None
    assert path.exists()
    assert path.parent == tmp_path / "logs"
    assert path.suffix == ".jsonl"


def test_init_disabled_by_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTODND_TRACE", "0")
    assert tracing.init(tmp_path / "logs") is None
    assert not tracing.is_enabled()


def test_init_disabled_when_value_is_false(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTODND_TRACE", "false")
    assert tracing.init(tmp_path / "logs") is None


def test_log_agent_call_writes_one_line_per_call(tmp_path):
    path = tracing.init(tmp_path)
    assert path is not None

    world = _empty_world()
    payload = TurnDirective().model_dump()
    run_turn_director(
        world=world,
        player_input="step 1",
        prior_prose="",
        rng=random.Random(0),
        model=_text_responder(payload),
    )
    run_turn_director(
        world=world,
        player_input="step 2",
        prior_prose="",
        rng=random.Random(0),
        model=_text_responder(payload),
    )

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2

    rec1, rec2 = (json.loads(line) for line in lines)
    assert rec1["step"] == 1
    assert rec2["step"] == 2
    assert rec1["agent"] == "turn_director"
    assert rec1["world_turn"] == 0
    assert rec1["player_input"] == "step 1"
    assert "messages" in rec1 and len(rec1["messages"]) >= 2  # at least system + user
    assert rec1["output"] == payload  # parsed TurnDirective dump
    assert rec1["latency_ms"] >= 0


def test_log_agent_call_no_op_when_disabled(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTODND_TRACE", "0")
    tracing.init(tmp_path)
    # Run an agent call with tracing disabled — should not raise, no file written.
    world = _empty_world()
    run_turn_director(
        world=world,
        player_input="x",
        prior_prose="",
        rng=random.Random(0),
        model=_text_responder(TurnDirective().model_dump()),
    )
    # No log file in tmp_path
    assert list(tmp_path.iterdir()) == []


def test_step_counter_resets_on_re_init(tmp_path):
    path1 = tracing.init(tmp_path / "a")
    assert path1 is not None
    world = _empty_world()
    run_turn_director(
        world=world,
        player_input="x",
        prior_prose="",
        rng=random.Random(0),
        model=_text_responder(TurnDirective().model_dump()),
    )
    rec1 = json.loads(path1.read_text().splitlines()[0])
    assert rec1["step"] == 1

    path2 = tracing.init(tmp_path / "b")
    assert path2 is not None
    run_turn_director(
        world=world,
        player_input="y",
        prior_prose="",
        rng=random.Random(0),
        model=_text_responder(TurnDirective().model_dump()),
    )
    rec2 = json.loads(path2.read_text().splitlines()[0])
    assert rec2["step"] == 1  # counter reset
