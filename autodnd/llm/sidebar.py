"""Sidebar agent: read-only Q&A over the player's own state.

Separate session from the Director — its conversation never feeds back into
the Director's, so mechanical chatter doesn't pollute narrative context.
"""

import time
from collections.abc import Mapping

from pydantic_ai import Agent
from pydantic_ai.models import Model

from autodnd.engine.rules import effective_mods
from autodnd.engine.world import Item, PlayerState
from autodnd.llm import load_prompt, model_from_env
from autodnd.llm.tracing import log_agent_call


def build_sidebar(model: Model | None = None) -> Agent[None, str]:
    return Agent(
        model or model_from_env(),
        output_type=str,
        system_prompt=load_prompt("sidebar.md"),
    )


def _format_mods(d: dict[str, int]) -> str:
    if not d:
        return "(none)"
    return ", ".join(f"{k}{v:+d}" for k, v in sorted(d.items()))


def _format_player_state(p: PlayerState, items: Mapping[str, Item]) -> str:
    s = p.stats
    hp_str = f"{s.hp}/{s.hp_max}" if s.hp_max > 0 else str(s.hp)

    eff = effective_mods(s, p.items, items)

    if p.items:
        item_lines: list[str] = []
        for item_id in p.items:
            it = items.get(item_id)
            if it is None:
                item_lines.append(f"  - {item_id} (unknown)")
                continue
            effects = f" [effects: {_format_mods(it.effects)}]" if it.effects else ""
            item_lines.append(f"  - {it.name}{effects} — {it.description}")
        items_block = "\n".join(item_lines)
    else:
        items_block = "  (none)"

    log_lines = "\n".join(f"- {entry}" for entry in p.log) if p.log else "(none)"

    return (
        f"Location: {p.location_id}\n"
        f"HP: {hp_str}, AC: {s.ac}\n"
        f"Gold: {p.gold}\n"
        f"Abilities: STR {s.strength}, DEX {s.dexterity}, CON {s.constitution}, "
        f"INT {s.intelligence}, WIS {s.wisdom}, CHA {s.charisma}\n"
        f"Base mods: {_format_mods(s.mods)}\n"
        f"Effective mods (with carried items): {_format_mods(eff)}\n"
        f"Items:\n{items_block}\n\n"
        f"Player log:\n{log_lines}"
    )


def run_sidebar(
    player: PlayerState,
    query: str,
    *,
    items: Mapping[str, Item] | None = None,
    model: Model | None = None,
    world_turn: int | None = None,
) -> str:
    agent = build_sidebar(model)
    user_message = (
        f"## Player state\n\n{_format_player_state(player, items or {})}\n\n"
        f"## Question\n\n{query}"
    )
    start = time.monotonic()
    result = agent.run_sync(user_message)
    log_agent_call(
        agent="sidebar",
        world_turn=world_turn,
        result=result,
        latency_ms=(time.monotonic() - start) * 1000,
        extra={"query": query},
    )
    return result.output
