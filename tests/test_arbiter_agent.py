"""Arbiter agent: tool wiring, invoke_actor dispatch, defensive leak check."""

from __future__ import annotations

import random

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from autodnd.engine.world import World
from autodnd.fixtures import vale_inn
from autodnd.llm.arbiter import build_arbiter_agent, run_cycle
from autodnd.llm.character import build_character_agent
from autodnd.llm.narrator import build_narrator_agent


# ---------- Wiring ----------


def test_arbiter_registers_tools() -> None:
    agent = build_arbiter_agent(TestModel())
    tools = set(agent._function_toolset.tools.keys())
    expected = {
        "create_location",
        "create_npc",
        "create_item",
        "mint_history",
        "move_player",
        "update_player_stats",
        "move_npc",
        "update_npc_stats",
        "transfer_item",
        "update_item_description",
        "advance_narrative_time",
        "roll",
        "check",
        "attack",
        "save",
        "invoke_actor",
        "end_cycle",
    }
    assert tools == expected


# ---------- invoke_actor dispatch ----------


def _scripted_arbiter(
    calls: list[tuple[str, dict]], final_text: str = "(end)"
) -> FunctionModel:
    """A FunctionModel that emits the given tool calls in order, then finishes."""
    state = {"i": 0}

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        i = state["i"]
        state["i"] = i + 1
        if i < len(calls):
            name, args = calls[i]
            return ModelResponse(
                parts=[
                    ToolCallPart(tool_name=name, args=args, tool_call_id=f"call-{i}")
                ]
            )
        return ModelResponse(parts=[TextPart(content=final_text)])

    return FunctionModel(fn)


def test_invoke_actor_routes_narrator() -> None:
    w = World()
    vale_inn(w)
    arbiter = build_arbiter_agent(
        _scripted_arbiter(
            [("invoke_actor", {"actor_id": "narrator", "hint": "describe morning"})]
        )
    )
    character = build_character_agent(TestModel())
    narrator = build_narrator_agent(
        # narrator emits prose as final text directly
        FunctionModel(
            lambda msgs, info: ModelResponse(
                parts=[TextPart(content="Morning light spills across the bar.")]
            )
        )
    )
    deps = run_cycle(arbiter, character, narrator, w, "Player input: I wake up.")
    assert len(deps.prose_blocks) == 1
    assert "Morning light" in deps.prose_blocks[0]
    # Narrator auto-mints a player_perceived event.
    assert any(
        "Morning light" in h.description and h.participants == ["player"]
        for h in w.history
    )


def test_invoke_actor_routes_character() -> None:
    w = World()
    vale_inn(w)
    arbiter = build_arbiter_agent(
        _scripted_arbiter(
            [("invoke_actor", {"actor_id": "brona", "hint": "greet the player"})]
        )
    )
    # Brona's model says "Welcome." via say().
    brona_state = {"called": False}

    def brona_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if not brona_state["called"]:
            brona_state["called"] = True
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="say",
                        args={"content": "Welcome, traveler."},
                        tool_call_id="c1",
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="(done)")])

    character = build_character_agent(FunctionModel(brona_fn))
    narrator = build_narrator_agent(TestModel())
    deps = run_cycle(arbiter, character, narrator, w, "Player: I sit down.")

    assert deps.prose_blocks == ["(done)"]
    # Brona's say minted a record with present perceivers as participants.
    assert any(
        "Welcome, traveler." in h.description
        and set(h.participants) == {"brona", "player"}
        for h in w.history
    )


def test_invoke_actor_unknown_returns_error() -> None:
    w = World()
    vale_inn(w)
    arbiter = build_arbiter_agent(
        _scripted_arbiter([("invoke_actor", {"actor_id": "nobody", "hint": "x"})])
    )
    character = build_character_agent(TestModel())
    narrator = build_narrator_agent(TestModel())
    deps = run_cycle(arbiter, character, narrator, w, "trigger")
    # No prose accumulated (error returned to the arbiter LLM).
    assert deps.prose_blocks == []


# ---------- Defensive leak check ----------


def test_mint_history_warns_when_name_outside_participants() -> None:
    """When the description names a character not in participants, the
    defensive check stores a warning on deps."""
    w = World()
    vale_inn(w)
    arbiter = build_arbiter_agent(
        _scripted_arbiter(
            [
                (
                    "mint_history",
                    {
                        "participants": ["player"],
                        "description": "The player noticed Brona pour a drink.",
                        "location_id": "vale_inn",
                    },
                ),
            ]
        )
    )
    character = build_character_agent(TestModel())
    narrator = build_narrator_agent(TestModel())
    deps = run_cycle(arbiter, character, narrator, w, "trigger")

    # The mint succeeded; the warning surfaced.
    assert any("Brona" in h.description for h in w.history)
    assert deps.leak_warnings
    assert "brona" in deps.leak_warnings[0]


def test_mint_history_no_warning_when_clean() -> None:
    w = World()
    vale_inn(w)
    arbiter = build_arbiter_agent(
        _scripted_arbiter(
            [
                (
                    "mint_history",
                    {
                        "participants": ["player"],
                        "description": "The player felt the warmth of the fire.",
                        "location_id": "vale_inn",
                    },
                ),
            ]
        )
    )
    character = build_character_agent(TestModel())
    narrator = build_narrator_agent(TestModel())
    deps = run_cycle(arbiter, character, narrator, w, "trigger")
    assert deps.leak_warnings == []


# ---------- act() intents flow back to the arbiter ----------


def test_act_intents_populate_pending_intents() -> None:
    w = World()
    vale_inn(w)

    arbiter = build_arbiter_agent(
        _scripted_arbiter([("invoke_actor", {"actor_id": "brona", "hint": "react"})])
    )

    brona_state = {"called": False}

    def brona_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if not brona_state["called"]:
            brona_state["called"] = True
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="act",
                        args={"intent": "draw the knife"},
                        tool_call_id="c1",
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="(done)")])

    character = build_character_agent(FunctionModel(brona_fn))
    narrator = build_narrator_agent(TestModel())
    deps = run_cycle(arbiter, character, narrator, w, "trigger")

    assert deps.pending_intents == [("brona", "draw the knife")]


# ---------- Dice tools ----------


def test_check_tool_returns_resolution_detail() -> None:
    w = World()
    vale_inn(w)
    arbiter = build_arbiter_agent(
        _scripted_arbiter([("check", {"skill": "perception", "dc": 10, "modifier": 2})])
    )
    character = build_character_agent(TestModel())
    narrator = build_narrator_agent(TestModel())
    # We don't inspect the result string directly here; just verify the run
    # completes without exception. Determinism of dice is tested in test_rules.
    _ = run_cycle(arbiter, character, narrator, w, "trigger", rng=random.Random(0))
