"""Sidebar agent — read-only player queries.

Mechanical questions like "what's my HP?" or "what's in my pack?" bypass the
arbiter entirely. No state mutation, no time advance, no events minted. The
sidebar LLM gets ``render_for_player`` (third-person, mechanical) plus the
player's question and answers concisely.

Used by ``/hp``, ``/inv``, ``/log``, and ``/ask <question>`` slash commands.
"""

from __future__ import annotations

import time

from pydantic_ai import Agent
from pydantic_ai.models import Model

from autodnd.engine.render import render_for_player
from autodnd.engine.world import World
from autodnd.trace import trace_run

SIDEBAR_SYSTEM = """\
You answer the player's mechanical questions about their own character — \
HP, inventory, gold, abilities, recent memory. Answer concisely from the \
data below; do not narrate, do not invent. Use third-person framing ("Fox \
has 12/15 HP" rather than "you have"). If the question can't be answered \
from the data, say so plainly. One short paragraph max.
"""


# Canonical text for common slash commands.
SLASH_QUERIES: dict[str, str] = {
    "/hp": "Show HP, AC, ability scores, and modifiers.",
    "/log": "Show recent memory in chronological order.",
    "/inv": "Show inventory and gold.",
}


def build_sidebar_agent(model: Model) -> Agent[None, str]:
    return Agent(model, output_type=str, system_prompt=SIDEBAR_SYSTEM)


def run_sidebar(agent: Agent[None, str], world: World, question: str) -> str:
    """Answer one question against the player's mechanical view. No mutation."""
    user = render_for_player(world) + f"\n\n## Question\n{question}"
    start = time.perf_counter()
    result = agent.run_sync(user)
    trace_run("sidebar", result, (time.perf_counter() - start) * 1000)
    return result.output
