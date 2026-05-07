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
        """Mint a `Location`."""
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
        """Mint an NPC. The player is not a `Character`; use the `*_player`
        tools for the player."""
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
        """Mint an `Item`. `effects` carries mechanics: `{"persuasion": 2}` for
        a +2 training, `{"attack": 1}` for a +1 sword, `{}` for flavor-only.
        `description` carries flavor and quantity."""
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
        """Mint a `Thread`. Pass `parent_id=None` for a root thread."""
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
        """Mint an immutable `Event`. Engine assigns `t`. Pass `participants=[]`
        for events with no character witnesses (backstory, weather, pure
        narration)."""
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
    def move_player(
        ctx: RunContext[BootstrapperDeps], location_id: str
    ) -> str:
        """Place the player at a location."""
        return _ok_or_err(apply_move_player(ctx.deps.world, location_id=location_id))

    @agent.tool
    def update_player_stats(
        ctx: RunContext[BootstrapperDeps], stats: CharacterStats
    ) -> str:
        """Set the player's stats wholesale (HP, AC, ability scores, mods)."""
        return _ok_or_err(apply_update_player_stats(ctx.deps.world, stats=stats))

    @agent.tool
    def add_player_item(ctx: RunContext[BootstrapperDeps], item_id: str) -> str:
        """Give the player an item (must already exist via `create_item`)."""
        return _ok_or_err(apply_add_player_item(ctx.deps.world, item_id=item_id))

    @agent.tool
    def append_player_log(ctx: RunContext[BootstrapperDeps], text: str) -> str:
        """Append a log entry in the player's voice — what they remember,
        believe, or assume going into the opening scene."""
        return _ok_or_err(apply_append_player_log(ctx.deps.world, text=text))

    # ---------- Handoff ----------

    @agent.tool
    def begin_play(ctx: RunContext[BootstrapperDeps]) -> str:
        """Hand off to the Director and start turn 0. Validates that minimum
        canon exists (>=1 location, >=1 thread, >=1 event, player placed with
        hp > 0). Returns an error listing missing invariants if called early."""
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
        "We're starting a solo D&D 5e one-shot. Run a short Q&A with the player "
        "to settle their character, the situation, and the opening scene. Mint "
        "canon (locations, threads, NPCs, items, events, player state) as "
        "decisions firm up. Call `begin_play` when the world has at least one "
        "location, one thread, one event, and the player is placed with hp > 0; "
        "after `begin_play` succeeds, write the opening prose in 2nd person. "
        "Begin by greeting the player and asking your first question."
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
