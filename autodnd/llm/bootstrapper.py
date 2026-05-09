"""Bootstrapper agent: interactive Q&A that mints initial canon.

Runs before the Director. Asks the player a few focused questions, mints
locations / threads / NPCs / items / events / player state as decisions firm
up, then calls ``begin_play`` to hand off to the Director (turn 0). Conversation
history is threaded across calls via PydanticAI ``message_history``.

Tool surface is intentionally minimal: only what's needed to mint initial
canon and hand off. No dice (nothing uncertain happens during setup), no
per-turn mutations (nothing exists yet to mutate).
"""

import time
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models import Model

from autodnd.engine.delta import (
    ValidationError,
    apply_add_player_item,
    apply_append_player_log,
    apply_create_character,
    apply_create_item,
    apply_create_location,
    apply_create_thread,
    apply_mint_event,
    apply_move_player,
    apply_set_player_gold,
    apply_update_player_stats,
)
from autodnd.engine.world import CharacterStats, WorldModel
from autodnd.llm import load_prompt, model_from_env
from autodnd.llm.tracing import log_agent_call


@dataclass
class BootstrapperDeps:
    world: WorldModel


def _ok_or_err(err: ValidationError | None) -> str:
    if err is None:
        return "ok"
    return f"error: {err.code} at {err.field_path}: {err.detail}"


def build_bootstrapper(model: Model | None = None) -> Agent[BootstrapperDeps, str]:
    agent = Agent(
        model or model_from_env(),
        deps_type=BootstrapperDeps,
        output_type=str,
        system_prompt=load_prompt("bootstrapper.md"),
    )

    # ---------- Creation ----------

    @agent.tool
    def create_location(
        ctx: RunContext[BootstrapperDeps], id: str, name: str, description: str
    ) -> str:
        """Mint a location the session can reference."""
        return _ok_or_err(
            apply_create_location(
                ctx.deps.world, id=id, name=name, description=description
            )
        )

    @agent.tool
    def create_character(
        ctx: RunContext[BootstrapperDeps],
        id: str,
        name: str,
        description: str,
        location_id: str,
        stats: CharacterStats,
    ) -> str:
        """Mint an NPC at a known location. Player state uses player tools."""
        return _ok_or_err(
            apply_create_character(
                ctx.deps.world,
                id=id,
                name=name,
                description=description,
                location_id=location_id,
                stats=stats,
            )
        )

    @agent.tool
    def create_item(
        ctx: RunContext[BootstrapperDeps],
        id: str,
        name: str,
        description: str,
        effects: dict[str, int],
    ) -> str:
        """Mint an item. Effects are mechanical bonuses; description is fictional state."""
        return _ok_or_err(
            apply_create_item(
                ctx.deps.world,
                id=id,
                name=name,
                description=description,
                effects=effects,
            )
        )

    @agent.tool
    def create_thread(
        ctx: RunContext[BootstrapperDeps],
        id: str,
        name: str,
        parent_id: str | None,
        description: str,
    ) -> str:
        """Mint a plot thread. Use `parent_id=None` for a root thread."""
        return _ok_or_err(
            apply_create_thread(
                ctx.deps.world,
                id=id,
                name=name,
                parent_id=parent_id,
                description=description,
            )
        )

    @agent.tool
    def mint_event(
        ctx: RunContext[BootstrapperDeps],
        id: str,
        narrative_time: str,
        location_id: str,
        participants: list[str],
        description: str,
        thread_id: str,
    ) -> str:
        """Mint a canonical event. Use for history, discoveries, consequences, or notable changes."""
        return _ok_or_err(
            apply_mint_event(
                ctx.deps.world,
                id=id,
                narrative_time=narrative_time,
                location_id=location_id,
                participants=participants,
                description=description,
                thread_id=thread_id,
            )
        )

    # ---------- Player setup ----------

    @agent.tool
    def move_player(ctx: RunContext[BootstrapperDeps], location_id: str) -> str:
        """Place the player at a known location."""
        return _ok_or_err(apply_move_player(ctx.deps.world, location_id=location_id))

    @agent.tool
    def update_player_stats(
        ctx: RunContext[BootstrapperDeps], stats: CharacterStats
    ) -> str:
        """Set player HP, AC, abilities, and mods."""
        return _ok_or_err(apply_update_player_stats(ctx.deps.world, stats=stats))

    @agent.tool
    def set_player_gold(ctx: RunContext[BootstrapperDeps], gold: int) -> str:
        """Set the player's starting gold."""
        return _ok_or_err(apply_set_player_gold(ctx.deps.world, gold=gold))

    @agent.tool
    def add_player_item(ctx: RunContext[BootstrapperDeps], item_id: str) -> str:
        """Add an existing item to the player's inventory."""
        return _ok_or_err(apply_add_player_item(ctx.deps.world, item_id=item_id))

    @agent.tool
    def append_player_log(ctx: RunContext[BootstrapperDeps], text: str) -> str:
        """Append player-facing memory, belief, rumor, or assumption."""
        return _ok_or_err(apply_append_player_log(ctx.deps.world, text=text))

    # ---------- Handoff ----------

    @agent.tool
    def begin_play(ctx: RunContext[BootstrapperDeps]) -> str:
        """Hand off to the Director and start turn 0. Requires location, thread,
        event, player location, and positive HP."""
        world = ctx.deps.world
        missing: list[str] = []
        if not world.locations:
            missing.append("no locations (call create_location)")
        if not world.threads:
            missing.append("no threads (call create_thread)")
        if not world.events:
            missing.append("no events (call mint_event)")
        if not world.player.location_id:
            missing.append("player has no location_id (call move_player)")
        if world.player.stats.hp <= 0:
            missing.append("player hp <= 0 (call update_player_stats)")
        if missing:
            return "error: cannot begin_play yet — " + "; ".join(missing)
        world.turn = 0
        return "ok"

    return agent


# ---------- User-message templates ----------


def bootstrap_user_message() -> str:
    return (
        "Start a solo D&D 5e one-shot setup. Ask the first focused question to "
        "settle the player character, tone, and opening premise. As answers firm "
        "up, mint canon, set starting gold, and call `begin_play` when the world is ready."
    )


# ---------- Driver ----------


def run_bootstrapper(
    world: WorldModel,
    user_message: str,
    *,
    model: Model | None = None,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Run one Bootstrapper turn. Returns ``(prose, all_messages)``. Pass
    ``all_messages`` from the previous call as ``message_history`` to thread
    the conversation."""
    agent = build_bootstrapper(model)
    deps = BootstrapperDeps(world=world)
    start = time.monotonic()
    result = agent.run_sync(user_message, deps=deps, message_history=message_history)
    log_agent_call(
        agent="bootstrapper",
        world_turn=world.turn,
        result=result,
        latency_ms=(time.monotonic() - start) * 1000,
    )
    final_response: ModelResponse | None = None
    for msg in result.all_messages():
        if isinstance(msg, ModelResponse):
            final_response = msg
    prose = ""
    if final_response is not None:
        prose = "\n\n".join(
            part.content
            for part in final_response.parts
            if isinstance(part, TextPart) and part.content
        )
    return prose, list(result.all_messages())
