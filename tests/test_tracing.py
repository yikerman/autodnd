"""Tests for the human-readable trace log.

Covers init/disable behavior, the ``_walk`` part-decomposition (incl. tool
call/return pairing), and end-to-end trace files written by Director and
Bootstrapper runs driven by ``FunctionModel``.
"""

import random
import re
from pathlib import Path

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from autodnd.engine.delta import apply_create_location, apply_create_thread
from autodnd.engine.world import CharacterStats, PlayerState, WorldModel
from autodnd.llm import tracing
from autodnd.llm.bootstrapper import run_bootstrapper
from autodnd.llm.director import run_director


@pytest.fixture(autouse=True)
def _reset_tracing():
    """Module-level state leaks across tests; reset before and after each."""
    tracing._TRACE_FILE = None
    tracing._STEP_COUNTER = 0
    yield
    tracing._TRACE_FILE = None
    tracing._STEP_COUNTER = 0


def _empty_world() -> WorldModel:
    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)),
        turn=-1,
    )


def _seeded_world() -> WorldModel:
    world = _empty_world()
    apply_create_location(world, id="inn", name="Inn", description="...")
    apply_create_thread(world, id="t", name="t", parent_id=None, description="...")
    world.turn = 0
    return world


def test_init_creates_log_in_directory(tmp_path: Path):
    sub = tmp_path / "nested" / "trace"
    path = tracing.init(sub)
    assert path.exists()
    assert path.parent == sub
    assert path.suffix == ".log"
    assert tracing.is_enabled()
    assert tracing.current_path() == path


def test_init_resets_step_counter(tmp_path: Path):
    tracing.init(tmp_path / "a")
    assert tracing.start_run(agent="x", world_turn=0) == 1
    assert tracing.start_run(agent="x", world_turn=0) == 2
    tracing.init(tmp_path / "b")
    assert tracing.start_run(agent="x", world_turn=0) == 1


def test_disabled_when_init_not_called():
    """Without init, start_run returns 0 and end_run is a no-op (does not
    touch its result arg)."""
    assert not tracing.is_enabled()
    assert tracing.start_run(agent="x", world_turn=0) == 0
    tracing.end_run(step=0, agent="x", world_turn=0, result=None, latency_ms=12.5)


def test_walk_produces_blocks_for_all_part_types():
    messages: list[ModelMessage] = [
        ModelRequest(
            parts=[
                SystemPromptPart(content="sys"),
                UserPromptPart(content="usr"),
            ]
        ),
        ModelResponse(
            parts=[
                ThinkingPart(content="thinking..."),
                TextPart(content="hello"),
                ToolCallPart(tool_name="t", args={"x": 1}, tool_call_id="c1"),
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(tool_name="t", content="ok", tool_call_id="c1"),
                RetryPromptPart(content="bad input", tool_name="t"),
            ]
        ),
    ]
    blocks = list(tracing._walk(messages))
    tags = [b[0] for b in blocks]

    assert "[system]" in tags
    assert "[user]" in tags
    assert "[think]" in tags
    assert "[text]" in tags
    assert "[tool] t" in tags
    assert any(t.startswith("[retry]") for t in tags)
    # tool return is paired into the [tool] block, not standalone
    assert not any(t.startswith("[tool-return]") for t in tags)


def test_walk_pairs_tool_call_and_return_in_one_block():
    messages: list[ModelMessage] = [
        ModelResponse(
            parts=[
                ToolCallPart(tool_name="t", args={"x": 1}, tool_call_id="c1"),
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(tool_name="t", content="all good", tool_call_id="c1"),
            ]
        ),
    ]
    blocks = list(tracing._walk(messages))
    assert len(blocks) == 1
    tag, body = blocks[0]
    assert tag == "[tool] t"
    assert "args:" in body
    assert "ret:" in body
    assert "all good" in body


def test_walk_skips_empty_text_and_thinking():
    """Whitespace-only TextPart/ThinkingPart shouldn't add noise blocks."""
    messages: list[ModelMessage] = [
        ModelResponse(
            parts=[
                ThinkingPart(content="   "),
                TextPart(content=""),
                TextPart(content="real content"),
            ]
        ),
    ]
    blocks = list(tracing._walk(messages))
    assert blocks == [("[text]", "real content")]


def test_director_trace_emits_expected_blocks(tmp_path: Path):
    tracing.init(tmp_path)
    world = _seeded_world()

    step_n = {"n": 0}

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        step_n["n"] += 1
        if step_n["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="move_player",
                        args={"location_id": "inn"},
                        tool_call_id="c1",
                    )
                ]
            )
        return ModelResponse(parts=[TextPart("You see the inn.")])

    run_director(
        world,
        "I look around.",
        random.Random(42),
        model=FunctionModel(model_fn),
    )

    log_path = tracing.current_path()
    assert log_path is not None
    log_text = log_path.read_text()

    assert "=== step 1 · director · turn 0 ===" in log_text
    assert "[system]" in log_text
    assert "[user]" in log_text
    assert "I look around." in log_text
    assert "[tool] move_player" in log_text
    assert '"location_id": "inn"' in log_text
    assert "ret:" in log_text
    assert "ok" in log_text
    assert "[text]" in log_text
    assert "You see the inn." in log_text
    assert re.search(r"=== step 1 end · \d+ms · \d+→\d+ tokens ===", log_text)


def test_sidebar_extra_query_in_banner(tmp_path: Path):
    """start_run's `extra` dict surfaces in the opening banner so each step's
    purpose is readable at a glance."""
    tracing.init(tmp_path)
    tracing.start_run(agent="sidebar", world_turn=5, extra={"query": "hp?"})
    log_text = tracing.current_path().read_text()  # type: ignore[union-attr]
    assert "step 1 · sidebar · turn 5" in log_text
    assert "query=" in log_text
    assert "hp?" in log_text


def test_bootstrapper_threaded_history_does_not_relog(tmp_path: Path):
    """end_run uses result.new_messages(), so a bootstrapper second turn must
    not re-emit the first turn's user message in its trace block."""
    tracing.init(tmp_path)
    world = _empty_world()

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart("ack")])

    _, history = run_bootstrapper(world, "FIRST_PROMPT", model=FunctionModel(model_fn))
    run_bootstrapper(
        world, "SECOND_PROMPT", model=FunctionModel(model_fn), message_history=history
    )

    log_text = tracing.current_path().read_text()  # type: ignore[union-attr]
    step2_idx = log_text.index("=== step 2 ·")
    after_step2 = log_text[step2_idx:]
    assert "FIRST_PROMPT" not in after_step2
    assert "SECOND_PROMPT" in after_step2


def test_block_format_is_indented_two_spaces(tmp_path: Path):
    tracing.init(tmp_path)
    tracing.start_run(agent="x", world_turn=0)
    tracing._write_block("[user]", "line one\nline two")
    log_text = tracing.current_path().read_text()  # type: ignore[union-attr]
    assert "[user]\n  line one\n  line two\n" in log_text
