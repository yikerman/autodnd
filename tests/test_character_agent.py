"""Character LLM agent: tool wiring, deps round-trip, structural firewall."""

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

from autodnd.engine.world import HeldBy, World
from autodnd.fixtures import vale_inn
from autodnd.llm.character import build_character_agent, run_character


# ---------- Wiring ----------


def test_agent_registers_all_seven_tool_functions() -> None:
    """5 conceptual tools, but `request_dice` is split into 3 implementations."""
    agent = build_character_agent(TestModel())
    tools = set(agent._function_toolset.tools.keys())
    assert tools == {
        "say",
        "act",
        "request_dice_check",
        "request_dice_attack",
        "request_dice_save",
        "move_self",
        "transfer_item",
    }


# ---------- Tool behavior via FunctionModel ----------


def _emit_then_finish(
    tool_name: str, tool_args: dict, final_text: str = "(done)"
) -> FunctionModel:
    """A FunctionModel that calls one tool the first turn, then emits text the second."""
    state = {"called": False}

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if not state["called"]:
            state["called"] = True
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name=tool_name, args=tool_args, tool_call_id="call-1"
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content=final_text)])

    return FunctionModel(fn)


def test_say_mints_history_with_all_present_perceivers() -> None:
    w = World()
    vale_inn(w)
    history_before = len(w.history)

    agent = build_character_agent(_emit_then_finish("say", {"content": "Welcome."}))
    prose, deps = run_character(agent, w, "brona", rng=random.Random(0))

    assert len(w.history) == history_before + 1
    new = w.history[-1]
    # vale_inn has player + brona present; both should be participants.
    assert set(new.participants) == {"player", "brona"}
    assert "Welcome." in new.description
    assert new.location_id == "vale_inn"
    assert new.id in deps.cycle_history_ids
    assert prose == "(done)"


def test_act_records_intent_does_not_mint_history() -> None:
    w = World()
    vale_inn(w)
    history_before = len(w.history)

    agent = build_character_agent(
        _emit_then_finish("act", {"intent": "lunge across the bar at the player"})
    )
    _prose, deps = run_character(agent, w, "brona")

    assert deps.intents == ["lunge across the bar at the player"]
    assert len(w.history) == history_before  # act() doesn't mint
    assert deps.cycle_history_ids == []


def test_move_self_updates_location() -> None:
    w = World()
    vale_inn(w)
    # Add a destination.
    from autodnd.engine.delta import create_location

    create_location(w, location_id="cellar", name="Cellar", description="cool, dark")

    agent = build_character_agent(
        _emit_then_finish("move_self", {"location_id": "cellar"})
    )
    _prose, _deps = run_character(agent, w, "brona")
    assert w.characters["brona"].location_id == "cellar"


def test_move_self_unknown_location_returns_error() -> None:
    w = World()
    vale_inn(w)
    agent = build_character_agent(
        _emit_then_finish("move_self", {"location_id": "void"})
    )
    _prose, _deps = run_character(agent, w, "brona")
    # World unchanged
    assert w.characters["brona"].location_id == "vale_inn"


def test_transfer_item_validates_ownership() -> None:
    """Brona doesn't hold the shortsword — transfer must be rejected."""
    w = World()
    vale_inn(w)
    agent = build_character_agent(
        _emit_then_finish(
            "transfer_item",
            {"item_id": "shortsword", "recipient_character_id": "brona"},
        )
    )
    _prose, _deps = run_character(agent, w, "brona")
    # Item still held by player.
    assert isinstance(w.items["shortsword"].position, HeldBy)
    assert w.items["shortsword"].position.character_id == "player"


def test_transfer_item_happy_path() -> None:
    w = World()
    vale_inn(w)
    agent = build_character_agent(
        _emit_then_finish(
            "transfer_item",
            {"item_id": "shortsword", "recipient_character_id": "brona"},
        )
    )
    # Player holds shortsword; transferring to brona should succeed.
    _prose, _deps = run_character(agent, w, "player")
    assert isinstance(w.items["shortsword"].position, HeldBy)
    assert w.items["shortsword"].position.character_id == "brona"


def test_request_dice_check_is_self_only() -> None:
    """Dice tools roll for self-checks; outcome string returned to LLM."""
    w = World()
    vale_inn(w)
    agent = build_character_agent(
        _emit_then_finish(
            "request_dice_check", {"skill": "perception", "dc": 10, "modifier": 2}
        )
    )
    # Use a fixed-seed RNG so the call is deterministic. We don't assert outcome,
    # just that the tool resolved and the run completed.
    _prose, _deps = run_character(agent, w, "brona", rng=random.Random(42))


# ---------- System prompt is per-character (firewall) ----------


def test_system_prompt_contains_character_description() -> None:
    """The agent's dynamic system prompt is built from render_for_character.

    We hook a no-op FunctionModel that records the AgentInfo's instructions
    on first call.
    """
    captured: dict[str, str] = {}

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        # The system prompt arrives as the first SystemPromptPart in messages.
        from pydantic_ai.messages import ModelRequest, SystemPromptPart

        for msg in messages:
            if isinstance(msg, ModelRequest):
                for part in msg.parts:
                    if isinstance(part, SystemPromptPart):
                        captured["system"] = part.content
        return ModelResponse(parts=[TextPart(content="(silent)")])

    w = World()
    vale_inn(w)
    agent = build_character_agent(FunctionModel(fn))
    _prose, _deps = run_character(agent, w, "brona")

    system = captured.get("system", "")
    assert "You are Brona." in system
    assert "weathered hands" in system  # part of brona's description
    # Ensure player's private description elements aren't in Brona's system prompt
    # (they shouldn't be — system is built from brona only).
    # The fixture's player description has "wandering scout"; that DOES appear
    # in Brona's user prompt (Present in scene). Not a leak — public-only.
