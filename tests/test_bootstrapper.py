"""Smoke tests for the Bootstrapper agent.

Like ``test_director.py``, these use a scripted ``FunctionModel`` to verify
tool wiring and the begin_play handoff. End-to-end naturalness is verified
by playtest.
"""

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from autodnd.engine.world import CharacterStats, PlayerState, WorldModel
from autodnd.llm.bootstrapper import (
    BootstrapperDeps,
    bootstrap_user_message,
    build_bootstrapper,
    run_bootstrapper,
)


def _empty_world() -> WorldModel:
    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)),
        turn=-1,
    )


def test_bootstrap_user_message_returns_kickoff():
    msg = bootstrap_user_message()
    assert msg.strip()
    assert "begin_play" in msg


def test_begin_play_rejects_when_invariants_unmet():
    """Calling begin_play on an empty world returns an error and leaves turn=-1."""
    world = _empty_world()

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        # Always call begin_play first, then emit a placeholder reply.
        if not any(
            isinstance(part, ToolCallPart)
            for msg in messages
            if isinstance(msg, ModelResponse)
            for part in msg.parts
        ):
            return ModelResponse(
                parts=[ToolCallPart(tool_name="begin_play", args={}, tool_call_id="c1")]
            )
        return ModelResponse(parts=[TextPart("ok, will fix.")])

    agent = build_bootstrapper(model=FunctionModel(model_fn))
    deps = BootstrapperDeps(world=world)
    agent.run_sync("test", deps=deps)

    assert world.turn == -1


def test_begin_play_succeeds_after_seeding():
    """Scripted FunctionModel mints minimum canon then calls begin_play; world.turn -> 0."""
    world = _empty_world()

    script = [
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="create_location",
                    args={"id": "inn", "name": "Inn", "description": "..."},
                    tool_call_id="c1",
                ),
                ToolCallPart(
                    tool_name="create_thread",
                    args={
                        "id": "t",
                        "name": "Mission",
                        "parent_id": None,
                        "description": "...",
                    },
                    tool_call_id="c2",
                ),
                ToolCallPart(
                    tool_name="mint_event",
                    args={
                        "id": "e1",
                        "narrative_time": "today, dusk",
                        "location_id": "inn",
                        "participants": [],
                        "description": "Arrived at the inn.",
                        "thread_id": "t",
                    },
                    tool_call_id="c3",
                ),
                ToolCallPart(
                    tool_name="move_player",
                    args={"location_id": "inn"},
                    tool_call_id="c4",
                ),
                ToolCallPart(
                    tool_name="update_player_stats",
                    args={"stats": {"hp": 12, "hp_max": 12, "ac": 13}},
                    tool_call_id="c5",
                ),
                ToolCallPart(
                    tool_name="advance_narrative_time",
                    args={"to": "Day 1, dusk"},
                    tool_call_id="c6",
                ),
                ToolCallPart(tool_name="begin_play", args={}, tool_call_id="c7"),
            ]
        ),
        ModelResponse(parts=[TextPart("You stand in the inn, dusk light fading.")]),
    ]
    step = {"n": 0}

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        resp = script[step["n"]]
        step["n"] += 1
        return resp

    prose, history = run_bootstrapper(world, "test", model=FunctionModel(model_fn))

    assert world.turn == 0
    assert "inn" in world.locations
    assert "t" in world.threads
    assert "e1" in world.events
    assert world.player.location_id == "inn"
    assert world.player.stats.hp == 12
    assert world.narrative_time == "Day 1, dusk"
    assert prose == "You stand in the inn, dusk light fading."
    assert history  # non-empty list of ModelMessages


def test_begin_play_rejects_when_narrative_time_unset():
    """All other invariants met but narrative_time empty -> begin_play returns
    error and world.turn stays -1."""
    world = _empty_world()

    script = [
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="create_location",
                    args={"id": "inn", "name": "Inn", "description": "..."},
                    tool_call_id="c1",
                ),
                ToolCallPart(
                    tool_name="create_thread",
                    args={
                        "id": "t",
                        "name": "Mission",
                        "parent_id": None,
                        "description": "...",
                    },
                    tool_call_id="c2",
                ),
                ToolCallPart(
                    tool_name="mint_event",
                    args={
                        "id": "e1",
                        "narrative_time": "today, dusk",
                        "location_id": "inn",
                        "participants": [],
                        "description": "Arrived at the inn.",
                        "thread_id": "t",
                    },
                    tool_call_id="c3",
                ),
                ToolCallPart(
                    tool_name="move_player",
                    args={"location_id": "inn"},
                    tool_call_id="c4",
                ),
                ToolCallPart(
                    tool_name="update_player_stats",
                    args={"stats": {"hp": 12, "hp_max": 12, "ac": 13}},
                    tool_call_id="c5",
                ),
                # Note: no advance_narrative_time before begin_play.
                ToolCallPart(tool_name="begin_play", args={}, tool_call_id="c6"),
            ]
        ),
        ModelResponse(parts=[TextPart("ack")]),
    ]
    step = {"n": 0}

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        resp = script[step["n"]]
        step["n"] += 1
        return resp

    run_bootstrapper(world, "test", model=FunctionModel(model_fn))

    assert world.turn == -1
    assert world.narrative_time == ""


def test_run_bootstrapper_threads_message_history():
    """Second call sees the first call's messages prepended via message_history."""
    world = _empty_world()

    seen_history_lengths: list[int] = []

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen_history_lengths.append(len(messages))
        return ModelResponse(parts=[TextPart("ack")])

    _, history1 = run_bootstrapper(world, "first", model=FunctionModel(model_fn))
    _, history2 = run_bootstrapper(
        world, "second", model=FunctionModel(model_fn), message_history=history1
    )

    # Second call sees more messages than the first (history threaded in).
    assert seen_history_lengths[0] < seen_history_lengths[1]
    assert len(history2) > len(history1)
