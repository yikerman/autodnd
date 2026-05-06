"""Narrator agent: restyles directive beats into prose. No tools, no world access."""

import time

from pydantic_ai import Agent
from pydantic_ai.models import Model

from autodnd.engine.delta import Beat
from autodnd.llm import load_prompt, model_from_env
from autodnd.llm.tracing import log_agent_call


def build_narrator(model: Model | None = None) -> Agent[None, str]:
    return Agent(
        model or model_from_env(),
        output_type=str,
        system_prompt=load_prompt("narrator.md"),
    )


def _format_beats(beats: list[Beat]) -> str:
    lines: list[str] = []
    for b in beats:
        if b.kind == "dialogue" and b.speaker is not None:
            lines.append(f"- ({b.kind}) {b.speaker}: {b.text}")
        else:
            lines.append(f"- ({b.kind}) {b.text}")
    return "\n".join(lines)


def run_narrator(
    beats: list[Beat],
    narration_history: list[str],
    *,
    model: Model | None = None,
    world_turn: int | None = None,
) -> str:
    agent = build_narrator(model)
    history_block = (
        "\n\n---\n\n".join(narration_history)
        if narration_history
        else "(no prior prose — this is the opening.)"
    )
    user_message = (
        "## Prior prose history\n\n"
        f"{history_block}\n\n"
        "## Beats to restyle\n\n"
        f"{_format_beats(beats)}"
    )
    start = time.monotonic()
    result = agent.run_sync(user_message)
    log_agent_call(
        agent="narrator",
        world_turn=world_turn,
        result=result,
        latency_ms=(time.monotonic() - start) * 1000,
    )
    return result.output
