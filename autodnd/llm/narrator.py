"""Narrator pseudo-character — prose only, no tools.

Engine auto-mints a `player_perceived` history record with the narrator's
prose as description (participants = [player]). The narrator's system prompt
is global (cached forever across all narrator calls); only the user prompt
varies per invocation.
"""

from __future__ import annotations

import time

from pydantic_ai import Agent
from pydantic_ai.models import Model

from autodnd.engine.delta import mint_history
from autodnd.engine.render import NARRATOR_SYSTEM, render_for_narrator
from autodnd.engine.world import World
from autodnd.trace import trace_run


def build_narrator_agent(model: Model) -> Agent[None, str]:
    """Single agent for all narrator calls. No tools."""
    return Agent(model, output_type=str, system_prompt=NARRATOR_SYSTEM)


def run_narrator(
    agent: Agent[None, str],
    world: World,
    *,
    cycle_history_ids: list[str] | None = None,
    arbiter_hint: str | None = None,
) -> tuple[str, str | None]:
    """Run the narrator. Returns ``(prose, minted_event_id)``.

    The minted event has ``participants=["player"]`` and the prose as
    description, so the player's render layer treats narrator beats as
    perceived events.
    """
    _system, user = render_for_narrator(
        world,
        cycle_history_ids=cycle_history_ids,
        arbiter_hint=arbiter_hint,
    )
    start = time.perf_counter()
    result = agent.run_sync(user)
    trace_run("narrator", result, (time.perf_counter() - start) * 1000)
    prose = result.output

    player = world.characters.get("player")
    location_id = player.location_id if player is not None else None
    mint_result = mint_history(
        world,
        participants=["player"],
        description=prose,
        location_id=location_id,
    )
    event_id = world.history[-1].id if mint_result.startswith("ok:") else None
    return prose, event_id
