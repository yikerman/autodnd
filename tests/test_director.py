"""Smoke tests for the Director agent.

These exercise the agent's tool wiring and self-correction loop with a scripted
``FunctionModel`` instead of a real LLM. End-to-end naturalness is verified by
playtest, not here.
"""

import random

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from autodnd.engine.delta import (
    apply_create_location,
    apply_create_thread,
)
from autodnd.engine.world import CharacterStats, PlayerState, WorldModel
from autodnd.llm.director import (
    DirectorDeps,
    build_director,
    run_director,
    turn_user_message,
)


def _empty_world() -> WorldModel:
    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)),
        turn=-1,
    )


def _seeded_world() -> WorldModel:
    """A minimal world with one location + one thread, enough to mint events into."""
    world = _empty_world()
    apply_create_location(world, id="inn", name="Inn", description="...")
    apply_create_thread(world, id="t", name="t", parent_id=None, description="...")
    world.turn = 0
    return world


def test_director_runs_tool_then_returns_prose():
    """Director can call a mutation tool and emit prose as final output."""
    world = _seeded_world()

    step = {"n": 0}

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        step["n"] += 1
        if step["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="move_player",
                        args={"location_id": "inn"},
                        tool_call_id="call_1",
                    )
                ]
            )
        return ModelResponse(parts=[TextPart("You see the inn.")])

    agent = build_director(model=FunctionModel(model_fn))
    deps = DirectorDeps(world=world, rng=random.Random(42))
    result = agent.run_sync("test", deps=deps)

    assert result.output == "You see the inn."
    assert world.player.location_id == "inn"


def test_director_receives_validation_error_inline():
    """When a mutation tool errors, the model sees the error string in the next request
    so it can self-correct."""
    world = _seeded_world()

    seen_returns: list[str] = []
    step = {"n": 0}

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        step["n"] += 1
        # Capture move_player tool returns as they come back from the engine
        for msg in messages:
            if isinstance(msg, ModelRequest):
                for part in msg.parts:
                    if (
                        isinstance(part, ToolReturnPart)
                        and part.tool_name == "move_player"
                    ):
                        seen_returns.append(str(part.content))
        if step["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="move_player",
                        args={"location_id": "phantom"},
                        tool_call_id="call_1",
                    )
                ]
            )
        return ModelResponse(parts=[TextPart("done")])

    agent = build_director(model=FunctionModel(model_fn))
    deps = DirectorDeps(world=world, rng=random.Random(42))
    agent.run_sync("test", deps=deps)

    assert any("error" in r and "phantom" in r for r in seen_returns), seen_returns


def test_run_director_keeps_only_final_prose_block():
    """The Director is prompted to emit prose once, at the end. If the model
    drafts a complete narrative early and then writes another after more tool
    calls, only the final block is shown to the player — otherwise the player
    sees stacked, near-duplicate turn endings."""
    world = _seeded_world()

    step = {"n": 0}

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        step["n"] += 1
        if step["n"] == 1:
            return ModelResponse(
                parts=[
                    TextPart("Draft block. **What do you do?**"),
                    ToolCallPart(
                        tool_name="move_player",
                        args={"location_id": "inn"},
                        tool_call_id="call_1",
                    ),
                ]
            )
        return ModelResponse(parts=[TextPart("Final block. **What do you do?**")])

    output = run_director(
        world,
        "test",
        random.Random(42),
        model=FunctionModel(model_fn),
    )

    assert output == "Final block. **What do you do?**"


def test_turn_user_message_includes_world_render_and_input():
    world = _seeded_world()
    msg = turn_user_message(
        world,
        "I look around.",
        ["You stand at the door.", "The door creaks open."],
    )
    assert "# World (turn 0)" in msg  # render_omniscient header
    assert "I look around." in msg
    assert "You stand at the door." in msg
    assert "The door creaks open." in msg
    assert "## Prior prose (oldest first)" in msg
    assert "## Player input" in msg


def test_turn_user_message_handles_empty_prior_prose():
    world = _seeded_world()
    msg = turn_user_message(world, "go.", [])
    assert "(none — this is the first turn after the opening.)" in msg
