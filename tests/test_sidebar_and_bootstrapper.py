"""Sidebar and bootstrapper agents: wiring + state mutation."""

from __future__ import annotations

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from autodnd.engine.world import World
from autodnd.fixtures import vale_inn
from autodnd.llm.bootstrapper import build_bootstrapper_agent, run_bootstrapper
from autodnd.llm.sidebar import build_sidebar_agent, run_sidebar


# ---------- Sidebar ----------


def test_sidebar_has_no_tools() -> None:
    """Sidebar is read-only — should never mutate state."""
    agent = build_sidebar_agent(TestModel())
    assert agent._function_toolset.tools == {}


def test_sidebar_returns_answer_string() -> None:
    """Smoke test: sidebar runs end-to-end on a fixture."""
    w = World()
    vale_inn(w)
    agent = build_sidebar_agent(
        FunctionModel(
            lambda msgs, info: ModelResponse(parts=[TextPart(content="HP: 10/10")])
        )
    )
    answer = run_sidebar(agent, w, "What's my HP?")
    assert answer == "HP: 10/10"


def test_sidebar_does_not_mutate_world() -> None:
    w = World()
    vale_inn(w)
    history_before = len(w.history)
    agent = build_sidebar_agent(
        FunctionModel(lambda msgs, info: ModelResponse(parts=[TextPart(content="ok")]))
    )
    run_sidebar(agent, w, "anything")
    assert len(w.history) == history_before


# ---------- Bootstrapper ----------


def _script_model(
    responses: list[ModelResponse],
) -> tuple[FunctionModel, list[list[ModelMessage]], list[int]]:
    """FunctionModel scripted with an ordered list of ModelResponses.

    Returns ``(model, captured_messages, call_count)``. ``captured_messages``
    grows by one entry per model call; ``call_count[0]`` is the running count.
    After the script is exhausted, emits a default TextPart so the agent
    terminates cleanly.
    """
    state = {"i": 0}
    captured: list[list[ModelMessage]] = []
    call_count = [0]

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        captured.append(list(messages))
        call_count[0] += 1
        i = state["i"]
        state["i"] = i + 1
        if i < len(responses):
            return responses[i]
        return ModelResponse(parts=[TextPart(content="(end)")])

    return FunctionModel(fn), captured, call_count


def _scripted_input(lines: list[str | None]):
    """Returns a read_input callable that yields scripted lines in order."""
    it = iter(lines)

    def read():
        return next(it, None)

    return read


def _begin_play_returns(captured: list[list[ModelMessage]]) -> list[str]:
    """Collect every begin_play tool return content from a captured trace."""
    contents: list[str] = []
    seen: set[str] = set()
    for snapshot in captured:
        for msg in snapshot:
            if isinstance(msg, ModelRequest):
                for part in msg.parts:
                    if (
                        isinstance(part, ToolReturnPart)
                        and part.tool_name == "begin_play"
                        and part.tool_call_id not in seen
                    ):
                        seen.add(part.tool_call_id)
                        contents.append(str(part.content))
    return contents


def _tool_call(name: str, args: dict, call_id: str) -> ToolCallPart:
    return ToolCallPart(tool_name=name, args=args, tool_call_id=call_id)


def test_bootstrapper_registers_creation_tools_plus_begin_play() -> None:
    agent = build_bootstrapper_agent(TestModel())
    tools = set(agent._function_toolset.tools.keys())
    assert tools == {
        "create_location",
        "create_character",
        "create_item",
        "mint_history",
        "set_opening_time",
        "begin_play",
    }


def test_begin_play_rejects_empty_world() -> None:
    """begin_play on an empty world returns an error naming all four missing invariants."""
    model, captured, _ = _script_model(
        [
            ModelResponse(parts=[_tool_call("begin_play", {}, "c1")]),
            ModelResponse(parts=[TextPart(content="(noted)")]),
        ]
    )
    agent = build_bootstrapper_agent(model)
    w = World()
    ready = run_bootstrapper(
        agent,
        w,
        read_input=_scripted_input([""]),
        on_agent_message=lambda s: None,
    )
    assert ready is False
    returns = _begin_play_returns(captured)
    assert returns and returns[0].startswith("error:")
    msg = returns[0]
    assert "no locations created" in msg
    assert "player character not created" in msg
    assert "no opening scene history" in msg
    assert "narrative time" in msg


def test_begin_play_rejects_partial_world() -> None:
    """With a location + player but no scene history or opening time, begin_play
    names only those two failures."""
    model, captured, _ = _script_model(
        [
            ModelResponse(
                parts=[
                    _tool_call(
                        "create_location",
                        {
                            "location_id": "field",
                            "name": "Field",
                            "description": "Open.",
                        },
                        "c1",
                    ),
                    _tool_call(
                        "create_character",
                        {
                            "character_id": "player",
                            "name": "Hero",
                            "description": "A wanderer.",
                            "location_id": "field",
                            "hp": 10,
                            "hp_max": 10,
                            "ac": 12,
                        },
                        "c2",
                    ),
                    _tool_call("begin_play", {}, "c3"),
                ]
            ),
            ModelResponse(parts=[TextPart(content="(retrying)")]),
        ]
    )
    agent = build_bootstrapper_agent(model)
    w = World()
    ready = run_bootstrapper(
        agent,
        w,
        read_input=_scripted_input([""]),
        on_agent_message=lambda s: None,
    )
    assert ready is False
    returns = _begin_play_returns(captured)
    assert returns and returns[0].startswith("error:")
    msg = returns[0]
    assert "no opening scene history" in msg
    assert "narrative time" in msg
    assert "no locations created" not in msg
    assert "player character not created" not in msg


def test_begin_play_accepts_complete_world() -> None:
    """All invariants satisfied: begin_play flips ready and returns ok."""
    model, _, _ = _script_model(
        [
            ModelResponse(
                parts=[
                    _tool_call(
                        "create_location",
                        {
                            "location_id": "field",
                            "name": "Field",
                            "description": "Open.",
                        },
                        "c1",
                    ),
                    _tool_call(
                        "create_character",
                        {
                            "character_id": "player",
                            "name": "Hero",
                            "description": "A wanderer.",
                            "location_id": "field",
                            "hp": 10,
                            "hp_max": 10,
                            "ac": 12,
                        },
                        "c2",
                    ),
                    _tool_call(
                        "mint_history",
                        {
                            "participants": ["player"],
                            "description": "Hero stands in the field, weighing the road.",
                            "location_id": "field",
                        },
                        "c3",
                    ),
                    _tool_call(
                        "set_opening_time", {"new_time": "Day 1, midmorning"}, "c4"
                    ),
                    _tool_call("begin_play", {}, "c5"),
                ]
            ),
            ModelResponse(parts=[TextPart(content="World ready.")]),
        ]
    )
    agent = build_bootstrapper_agent(model)
    w = World()
    ready = run_bootstrapper(
        agent,
        w,
        read_input=_scripted_input([""]),
        on_agent_message=lambda s: None,
    )
    assert ready is True
    assert "field" in w.locations
    assert "player" in w.characters
    assert len(w.history) == 1
    assert w.narrative_time == "Day 1, midmorning"


def test_begin_play_retries_after_error() -> None:
    """LLM attempts begin_play early, reads error, mints what's missing, retries."""
    model, captured, _ = _script_model(
        [
            ModelResponse(parts=[_tool_call("begin_play", {}, "c1")]),
            ModelResponse(
                parts=[
                    _tool_call(
                        "create_location",
                        {
                            "location_id": "field",
                            "name": "Field",
                            "description": "Open.",
                        },
                        "c2",
                    ),
                    _tool_call(
                        "create_character",
                        {
                            "character_id": "player",
                            "name": "Hero",
                            "description": "A wanderer.",
                            "location_id": "field",
                            "hp": 10,
                            "hp_max": 10,
                            "ac": 12,
                        },
                        "c3",
                    ),
                    _tool_call(
                        "mint_history",
                        {
                            "participants": ["player"],
                            "description": "Hero stands in the field.",
                            "location_id": "field",
                        },
                        "c4",
                    ),
                    _tool_call("set_opening_time", {"new_time": "Day 1, dusk"}, "c5"),
                    _tool_call("begin_play", {}, "c6"),
                ]
            ),
            ModelResponse(parts=[TextPart(content="World ready.")]),
        ]
    )
    agent = build_bootstrapper_agent(model)
    w = World()
    ready = run_bootstrapper(
        agent,
        w,
        read_input=_scripted_input([""]),
        on_agent_message=lambda s: None,
    )
    assert ready is True
    returns = _begin_play_returns(captured)
    assert len(returns) == 2
    assert returns[0].startswith("error:")
    assert returns[1].startswith("ok:")


def test_run_bootstrapper_threads_message_history() -> None:
    """Turn 2 sees turn 1's messages threaded in via message_history."""
    model, captured, _ = _script_model(
        [
            ModelResponse(parts=[TextPart(content="What kind of world?")]),
            ModelResponse(parts=[TextPart(content="(noted)")]),
        ]
    )
    agent = build_bootstrapper_agent(model)
    w = World()
    run_bootstrapper(
        agent,
        w,
        read_input=_scripted_input(["A grim coastal city.", ""]),
        on_agent_message=lambda s: None,
    )
    assert len(captured) >= 2
    assert len(captured[1]) > len(captured[0])


def test_run_bootstrapper_exits_on_empty_input() -> None:
    """Empty player line aborts the loop after one model turn."""
    model, _, call_count = _script_model(
        [ModelResponse(parts=[TextPart(content="What kind of world?")])]
    )
    agent = build_bootstrapper_agent(model)
    w = World()
    ready = run_bootstrapper(
        agent,
        w,
        read_input=_scripted_input([""]),
        on_agent_message=lambda s: None,
    )
    assert ready is False
    assert call_count[0] == 1


def test_run_bootstrapper_exits_on_eof() -> None:
    """None from read_input (EOF/Ctrl-C) aborts the loop after one model turn."""
    model, _, call_count = _script_model(
        [ModelResponse(parts=[TextPart(content="What kind of world?")])]
    )
    agent = build_bootstrapper_agent(model)
    w = World()
    ready = run_bootstrapper(
        agent,
        w,
        read_input=_scripted_input([None]),
        on_agent_message=lambda s: None,
    )
    assert ready is False
    assert call_count[0] == 1
