"""Sidebar agent: read-only Q&A over the player's own state.

Separate session from Director and Narrator — its conversation never feeds
back into theirs, so mechanical chatter doesn't pollute narrative context.
"""

from pydantic_ai import Agent
from pydantic_ai.models import Model

from autodnd.engine.world import PlayerState
from autodnd.llm import load_prompt, model_from_env


def build_sidebar(model: Model | None = None) -> Agent[None, str]:
    return Agent(
        model or model_from_env(),
        output_type=str,
        system_prompt=load_prompt("sidebar.md"),
    )


def _format_player_state(p: PlayerState) -> str:
    mods = (
        ", ".join(f"{k}{v:+d}" for k, v in sorted(p.stats.mods.items()))
        if p.stats.mods
        else "(none)"
    )
    items = ", ".join(p.items) if p.items else "(none)"
    if p.knowledge:
        knowledge_lines = "\n".join(
            f"- (turn {ke.learned_at}) {ke.text}" for ke in p.knowledge
        )
    else:
        knowledge_lines = "(none)"
    return (
        f"Location: {p.location_id}\n"
        f"HP: {p.stats.hp}, AC: {p.stats.ac}, mods: {mods}\n"
        f"Items: {items}\n\n"
        f"Knowledge log:\n{knowledge_lines}"
    )


def run_sidebar(
    player: PlayerState,
    query: str,
    *,
    model: Model | None = None,
) -> str:
    agent = build_sidebar(model)
    user_message = (
        f"## Player state\n\n{_format_player_state(player)}\n\n"
        f"## Question\n\n{query}"
    )
    return agent.run_sync(user_message).output
