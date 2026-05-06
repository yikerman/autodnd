"""Smoke tests for the REPL's wiring. Mocks LLM calls; exercises the
Director→validate→Narrator dispatch and slash routing.
"""

import random
from typing import Any

import pytest

from autodnd.cli.main import handle_slash, initialize_session, run_turn
from autodnd.engine.delta import (
    Beat,
    Event,
    KnowledgeEntry,
    TurnDirective,
    WorldDelta,
)
from autodnd.engine.world import WorldModel


def _patch_llm(
    monkeypatch: pytest.MonkeyPatch,
    *,
    directive: TurnDirective,
    prose: str,
    sidebar_answer: str = "(stub)",
) -> dict[str, list[Any]]:
    """Replace the three run_* LLM entry points with deterministic stubs.
    Returns a dict capturing the call args for assertion."""
    captured: dict[str, list[Any]] = {"director": [], "narrator": [], "sidebar": []}

    def fake_director(world, player_input, prior_prose, rng):  # noqa: ARG001
        captured["director"].append((player_input, prior_prose))
        return directive

    def fake_narrator(beats, history):  # noqa: ARG001
        captured["narrator"].append((list(beats), list(history)))
        return prose

    def fake_sidebar(player, query):  # noqa: ARG001
        captured["sidebar"].append(query)
        return sidebar_answer

    monkeypatch.setattr("autodnd.cli.main.run_turn_director", fake_director)
    monkeypatch.setattr("autodnd.cli.main.run_narrator", fake_narrator)
    monkeypatch.setattr("autodnd.cli.main.run_sidebar", fake_sidebar)
    return captured


def _bootstrapped() -> WorldModel:
    rng = random.Random(0)
    world, _directive = initialize_session(demo_scene=True, rng=rng)
    return world


def test_initialize_session_with_demo_scene_succeeds():
    world, directive = initialize_session(demo_scene=True, rng=random.Random())
    assert world.turn == 0
    assert len(directive.opening_beats) > 0


def test_run_turn_dispatches_director_then_narrator(monkeypatch: pytest.MonkeyPatch):
    world = _bootstrapped()
    directive = TurnDirective(
        beats=[Beat(kind="action", text="Mara nods.")],
        world_delta=WorldDelta(),
    )
    captured = _patch_llm(monkeypatch, directive=directive, prose="She nods, slowly.")
    out = run_turn(world, "I nod.", "prior prose", ["history"], random.Random(0))

    assert out == "She nods, slowly."
    assert len(captured["director"]) == 1
    assert captured["director"][0] == ("I nod.", "prior prose")
    assert len(captured["narrator"]) == 1
    assert captured["narrator"][0][0] == directive.beats


def test_run_turn_advances_world_turn(monkeypatch: pytest.MonkeyPatch):
    world = _bootstrapped()
    starting_turn = world.turn
    directive = TurnDirective(beats=[Beat(kind="action", text="…")], world_delta=WorldDelta())
    _patch_llm(monkeypatch, directive=directive, prose="…")
    run_turn(world, "test", "", [], random.Random(0))
    assert world.turn == starting_turn + 1


def test_run_turn_applies_world_delta(monkeypatch: pytest.MonkeyPatch):
    world = _bootstrapped()
    next_t = max(e.t for e in world.events.values()) + 1
    new_event = Event(
        id="e_test",
        t=next_t,
        narrative_time="test",
        location_id="inn",
        participants=[],
        description="test event",
        thread_id="inn_night",
    )
    directive = TurnDirective(
        beats=[Beat(kind="action", text="…")],
        world_delta=WorldDelta(
            events_to_mint=[new_event],
            knowledge_to_append=[
                KnowledgeEntry(event_id="e_test", text="A test happened.", learned_at=1)
            ],
        ),
    )
    _patch_llm(monkeypatch, directive=directive, prose="…")
    run_turn(world, "test", "", [], random.Random(0))
    assert "e_test" in world.events
    assert any(ke.event_id == "e_test" for ke in world.player.knowledge)


def test_run_turn_retries_director_on_validator_failure(monkeypatch: pytest.MonkeyPatch):
    """First directive is invalid (duplicate event id); second is valid.
    REPL should retry and end up with prose, not a DM error."""
    world = _bootstrapped()
    bad_directive = TurnDirective(
        beats=[Beat(kind="action", text="…")],
        world_delta=WorldDelta(
            events_to_mint=[
                Event(
                    id="e_arrival",  # already exists from bootstrap
                    t=99,
                    narrative_time="x",
                    location_id="inn",
                    participants=[],
                    description="x",
                    thread_id="inn_night",
                ),
            ],
        ),
    )
    next_t = max(e.t for e in world.events.values()) + 1
    good_directive = TurnDirective(
        beats=[Beat(kind="action", text="okay")],
        world_delta=WorldDelta(
            events_to_mint=[
                Event(
                    id="e_recovered",
                    t=next_t,
                    narrative_time="x",
                    location_id="inn",
                    participants=[],
                    description="recovered",
                    thread_id="inn_night",
                ),
            ],
        ),
    )

    call_count = {"n": 0}

    def fake_director(world, player_input, prior_prose, rng):  # noqa: ARG001
        call_count["n"] += 1
        return bad_directive if call_count["n"] == 1 else good_directive

    def fake_narrator(beats, history):  # noqa: ARG001
        return "narrated"

    monkeypatch.setattr("autodnd.cli.main.run_turn_director", fake_director)
    monkeypatch.setattr("autodnd.cli.main.run_narrator", fake_narrator)

    out = run_turn(world, "test", "", [], random.Random(0))
    assert out == "narrated"
    assert call_count["n"] == 2
    assert "e_recovered" in world.events
    assert "e_arrival" in world.events  # was already there from bootstrap


def test_run_turn_aborts_on_double_failure(monkeypatch: pytest.MonkeyPatch):
    world = _bootstrapped()
    bad_directive = TurnDirective(
        beats=[Beat(kind="action", text="…")],
        world_delta=WorldDelta(
            events_to_mint=[
                Event(
                    id="e_arrival",  # collide on every retry
                    t=99,
                    narrative_time="x",
                    location_id="inn",
                    participants=[],
                    description="x",
                    thread_id="inn_night",
                ),
            ],
        ),
    )
    monkeypatch.setattr(
        "autodnd.cli.main.run_turn_director", lambda *a, **k: bad_directive
    )
    out = run_turn(world, "test", "", [], random.Random(0))
    assert "DM error" in out


def test_handle_slash_routes_to_sidebar(monkeypatch: pytest.MonkeyPatch):
    world = _bootstrapped()
    captured: list[str] = []
    monkeypatch.setattr(
        "autodnd.cli.main.run_sidebar",
        lambda player, query: (captured.append(query), "answer")[1],
    )
    out = handle_slash("/hp", world)
    assert out == "answer"
    assert captured == ["What's my HP?"]


def test_handle_slash_quit_raises_systemexit():
    world = _bootstrapped()
    with pytest.raises(SystemExit):
        handle_slash("/quit", world)


def test_handle_slash_unknown_command():
    world = _bootstrapped()
    out = handle_slash("/nonsense", world)
    assert "Unknown command" in out


def test_handle_slash_ask_passes_freeform_query(monkeypatch: pytest.MonkeyPatch):
    world = _bootstrapped()
    captured: list[str] = []
    monkeypatch.setattr(
        "autodnd.cli.main.run_sidebar",
        lambda player, query: (captured.append(query), "answer")[1],
    )
    handle_slash("/ask How heavy is my pouch?", world)
    assert captured == ["How heavy is my pouch?"]
