"""Director agent: omniscient narrative LLM for per-turn play.

Bootstrap (``world.turn == -1``) is handled by a separate ``Bootstrapper``
agent (see :mod:`autodnd.llm.bootstrapper`). The Director takes over once
``begin_play`` flips ``world.turn`` to ``0``. Tools cover dice
(roll/check/attack/save) and canon mutations (create/mint/move/update). Final
output is prose for the player.
"""

import random
import time
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models import Model

from autodnd.engine.delta import (
    ValidationError,
    apply_add_player_item,
    apply_create_character,
    apply_create_item,
    apply_create_location,
    apply_create_thread,
    apply_gain_player_gold,
    apply_mint_event,
    apply_move_character,
    apply_move_player,
    apply_remove_player_item,
    apply_spend_player_gold,
    apply_update_character_stats,
    apply_update_item_description,
    apply_update_player_stats,
    apply_update_thread_description,
)
from autodnd.engine.render import render_omniscient
from autodnd.engine.resolution import Resolution
from autodnd.engine.rules import (
    effective_mods,
    resolve_attack,
    resolve_check,
    resolve_save,
    roll,
)
from autodnd.engine.world import CharacterStats, WorldModel
from autodnd.llm import load_prompt, model_from_env
from autodnd.llm.tracing import log_agent_call


@dataclass
class DirectorDeps:
    world: WorldModel
    rng: random.Random


def _ok_or_err(err: ValidationError | None) -> str:
    if err is None:
        return "ok"
    return f"error: {err.code} at {err.field_path}: {err.detail}"


def build_director(model: Model | None = None) -> Agent[DirectorDeps, str]:
    agent = Agent(
        model or model_from_env(),
        deps_type=DirectorDeps,
        output_type=str,
        system_prompt=load_prompt("director.md"),
    )

    # ---------- Dice ----------

    @agent.tool
    def roll_dice(ctx: RunContext[DirectorDeps], spec: str) -> int:
        """Roll a dice expression like `2d6+3` or `d20`."""
        return roll(spec, ctx.deps.rng)

    @agent.tool
    def check(ctx: RunContext[DirectorDeps], skill: str, dc: int) -> Resolution:
        """Resolve a skill check against a DC using player mods and item effects."""
        world = ctx.deps.world
        mods = effective_mods(world.player.stats, world.player.items, world.items)
        return resolve_check(skill, dc, mods, ctx.deps.rng)

    @agent.tool
    def attack(
        ctx: RunContext[DirectorDeps], attack_mod: int, target_ac: int
    ) -> Resolution:
        """Resolve an attack roll against target AC."""
        return resolve_attack(attack_mod, target_ac, ctx.deps.rng)

    @agent.tool
    def save(ctx: RunContext[DirectorDeps], save_kind: str, dc: int) -> Resolution:
        """Resolve a saving throw against a DC using player mods and item effects."""
        world = ctx.deps.world
        mods = effective_mods(world.player.stats, world.player.items, world.items)
        return resolve_save(save_kind, dc, mods, ctx.deps.rng)

    # ---------- Creation ----------

    @agent.tool
    def create_location(
        ctx: RunContext[DirectorDeps], id: str, name: str, description: str
    ) -> str:
        """Mint a location the session can reference."""
        return _ok_or_err(
            apply_create_location(
                ctx.deps.world, id=id, name=name, description=description
            )
        )

    @agent.tool
    def create_character(
        ctx: RunContext[DirectorDeps],
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
        ctx: RunContext[DirectorDeps],
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
        ctx: RunContext[DirectorDeps],
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
        ctx: RunContext[DirectorDeps],
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

    # ---------- Mutation ----------

    @agent.tool
    def update_thread_description(
        ctx: RunContext[DirectorDeps], id: str, description: str
    ) -> str:
        """Update a thread after its truth, pressure, or stakes change."""
        return _ok_or_err(
            apply_update_thread_description(
                ctx.deps.world, id=id, description=description
            )
        )

    @agent.tool
    def update_item_description(
        ctx: RunContext[DirectorDeps], id: str, description: str
    ) -> str:
        """Update an item's fictional state, condition, charges, or non-gold quantity."""
        return _ok_or_err(
            apply_update_item_description(
                ctx.deps.world, id=id, description=description
            )
        )

    @agent.tool
    def move_character(ctx: RunContext[DirectorDeps], id: str, location_id: str) -> str:
        """Move an NPC to a known location."""
        return _ok_or_err(
            apply_move_character(ctx.deps.world, id=id, location_id=location_id)
        )

    @agent.tool
    def update_character_stats(
        ctx: RunContext[DirectorDeps], id: str, stats: CharacterStats
    ) -> str:
        """Update an NPC's HP, AC, abilities, or mods."""
        return _ok_or_err(
            apply_update_character_stats(ctx.deps.world, id=id, stats=stats)
        )

    @agent.tool
    def move_player(ctx: RunContext[DirectorDeps], location_id: str) -> str:
        """Move the player to a known location."""
        return _ok_or_err(apply_move_player(ctx.deps.world, location_id=location_id))

    @agent.tool
    def update_player_stats(
        ctx: RunContext[DirectorDeps], stats: CharacterStats
    ) -> str:
        """Update player HP, AC, abilities, and mods."""
        return _ok_or_err(apply_update_player_stats(ctx.deps.world, stats=stats))

    @agent.tool
    def gain_player_gold(ctx: RunContext[DirectorDeps], amount: int) -> str:
        """Increase the player's gold after payment, treasure, reward, or refund."""
        return _ok_or_err(apply_gain_player_gold(ctx.deps.world, amount=amount))

    @agent.tool
    def spend_player_gold(ctx: RunContext[DirectorDeps], amount: int) -> str:
        """Spend player gold for purchases, bribes, fees, losses, or wagers."""
        return _ok_or_err(apply_spend_player_gold(ctx.deps.world, amount=amount))

    @agent.tool
    def add_player_item(ctx: RunContext[DirectorDeps], item_id: str) -> str:
        """Add an existing item to the player's inventory."""
        return _ok_or_err(apply_add_player_item(ctx.deps.world, item_id=item_id))

    @agent.tool
    def remove_player_item(ctx: RunContext[DirectorDeps], item_id: str) -> str:
        """Remove an item from the player's inventory."""
        return _ok_or_err(apply_remove_player_item(ctx.deps.world, item_id=item_id))

    return agent


# ---------- User-message templates ----------


def turn_user_message(
    world: WorldModel, player_input: str, prior_prose: list[str]
) -> str:
    if prior_prose:
        prose_section = "\n\n---\n\n".join(prior_prose)
    else:
        prose_section = "(none)"
    return (
        f"{render_omniscient(world)}\n\n"
        "## Prior player-facing prose\n\n"
        f"{prose_section}\n\n"
        "## Player action\n\n"
        f"{player_input}"
    )


# ---------- Driver ----------


def run_director(
    world: WorldModel,
    user_message: str,
    rng: random.Random,
    *,
    model: Model | None = None,
) -> str:
    """Run one Director turn. Returns prose."""
    agent = build_director(model)
    deps = DirectorDeps(world=world, rng=rng)
    start = time.monotonic()
    result = agent.run_sync(user_message, deps=deps)
    log_agent_call(
        agent="director",
        world_turn=world.turn,
        result=result,
        latency_ms=(time.monotonic() - start) * 1000,
    )
    # Keep only text parts from the final ModelResponse. Prompt instructs the
    # Director to emit one prose block at the end after all tool calls; if the
    # model drafts prose mid-run and rewrites it, the final response is the
    # canonical one.
    final_response: ModelResponse | None = None
    for msg in result.all_messages():
        if isinstance(msg, ModelResponse):
            final_response = msg
    if final_response is None:
        return ""
    return "\n\n".join(
        part.content
        for part in final_response.parts
        if isinstance(part, TextPart) and part.content
    )
