"""Wire tests for the LLM agents using TestModel + FunctionModel.

These don't hit a real API. They verify:
- agents are constructible
- output specs are correct (PromptedOutput-wrapped)
- tools are registered
- one tool loop end-to-end (Director's roll tool returns engine ints)
"""

import json
import random

from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.output import PromptedOutput

from autodnd.engine.delta import (
    Beat,
    BootstrapDirective,
    EntitiesToCreate,
    TurnDirective,
)
from autodnd.engine.world import (
    CharacterStats,
    PlayerState,
    WorldModel,
)
from autodnd.llm.director import (
    build_bootstrap_director,
    build_turn_director,
    run_bootstrap_director,
    run_turn_director,
)
from autodnd.llm.narrator import run_narrator
from autodnd.llm.sidebar import run_sidebar


def _empty_world() -> WorldModel:
    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)), turn=-1
    )


def _text_responder(payload: dict) -> FunctionModel:
    """A FunctionModel that returns a single text response containing JSON.

    Mirrors how a PromptedOutput-mode model would emit structured output:
    as text, not as a final_result tool call."""

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:  # noqa: ARG001
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(respond)


def _minimal_bootstrap_payload() -> dict:
    return BootstrapDirective(
        entities=EntitiesToCreate(),
        initial_player_state=PlayerState(
            location_id="x", stats=CharacterStats(hp=1, ac=1)
        ),
    ).model_dump()


# ---------- Construction ----------


def test_bootstrap_director_uses_prompted_output():
    agent = build_bootstrap_director(model=TestModel())
    assert isinstance(agent.output_type, PromptedOutput)
    assert agent.output_type.outputs is BootstrapDirective


def test_turn_director_uses_prompted_output():
    agent = build_turn_director(model=TestModel())
    assert isinstance(agent.output_type, PromptedOutput)
    assert agent.output_type.outputs is TurnDirective


def test_turn_director_registers_dice_tools():
    agent = build_turn_director(model=TestModel())
    tool_names = set(agent._function_toolset.tools.keys())  # type: ignore[attr-defined]  # noqa: SLF001
    assert {"roll_dice", "check", "attack", "save"}.issubset(tool_names)


# ---------- FunctionModel: agents return structured output via prompted JSON ----------


def test_run_bootstrap_director_returns_bootstrap_directive():
    out = run_bootstrap_director(
        rng=random.Random(0), model=_text_responder(_minimal_bootstrap_payload())
    )
    assert isinstance(out, BootstrapDirective)


def test_run_turn_director_returns_turn_directive():
    world = _empty_world()
    world.turn = 0
    out = run_turn_director(
        world=world,
        player_input="I look around.",
        prior_prose="",
        rng=random.Random(0),
        model=_text_responder(TurnDirective().model_dump()),
    )
    assert isinstance(out, TurnDirective)


def test_run_narrator_returns_string():
    out = run_narrator(
        beats=[Beat(kind="action", text="Mara sits down.")],
        narration_history=[],
        model=TestModel(custom_output_text="Mara settles onto the bench."),
    )
    assert isinstance(out, str)
    assert out


def test_run_sidebar_returns_string():
    player = PlayerState(
        location_id="inn", stats=CharacterStats(hp=24, ac=13), items=["sword"]
    )
    out = run_sidebar(
        player, "What's my HP?", model=TestModel(custom_output_text="HP 24.")
    )
    assert isinstance(out, str)
    assert out


# ---------- FunctionModel: Director's tool loop reaches the engine ----------


def test_turn_director_roll_tool_dispatches_to_engine():
    """Drive the Director with a scripted FunctionModel: call the roll tool once,
    then emit a final TurnDirective as JSON text. Verify the tool's return came
    from the engine (a real int between 1 and 20)."""
    captured_roll: list[int] = []

    def script(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:  # noqa: ARG001
        already_rolled = any(
            isinstance(part, ToolCallPart) and part.tool_name == "roll_dice"
            for m in messages
            for part in getattr(m, "parts", [])
        )
        if not already_rolled:
            return ModelResponse(
                parts=[ToolCallPart(tool_name="roll_dice", args={"spec": "1d20"})]
            )
        # The most recent tool return holds the engine's roll.
        for m in messages:
            for part in getattr(m, "parts", []):
                if getattr(part, "tool_name", None) == "roll_dice" and hasattr(
                    part, "content"
                ):
                    captured_roll.append(int(part.content))  # type: ignore[arg-type]
        return ModelResponse(parts=[TextPart(json.dumps(TurnDirective().model_dump()))])

    world = _empty_world()
    world.turn = 0
    out = run_turn_director(
        world=world,
        player_input="(test)",
        prior_prose="",
        rng=random.Random(42),
        model=FunctionModel(script),
    )
    assert isinstance(out, TurnDirective)
    assert len(captured_roll) == 1
    assert 1 <= captured_roll[0] <= 20
    first_roll = captured_roll[0]

    captured_roll.clear()
    run_turn_director(
        world=world,
        player_input="(test)",
        prior_prose="",
        rng=random.Random(42),
        model=FunctionModel(script),
    )
    assert captured_roll == [first_roll]  # same seed → same engine roll
