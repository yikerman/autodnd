"""Director agent: omniscient narrative LLM.

One agent for both bootstrap (``world.turn == -1``) and per-turn play. Tools
cover dice (roll/check/attack/save) and canon mutations (create/mint/move/
update/append/end-scene). Final output is prose for the player.
"""

import random
import time
from dataclasses import dataclass, field

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelResponse, TextPart
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
    apply_move_character,
    apply_move_player,
    apply_remove_player_item,
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
    scene_boundaries: list[int] = field(default_factory=list)


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
        """Roll a dice expression like ``2d6+3`` or ``d20``. Returns the sum."""
        return roll(spec, ctx.deps.rng)

    @agent.tool
    def check(ctx: RunContext[DirectorDeps], skill: str, dc: int) -> Resolution:
        """Resolve a player skill check: d20 + bonus vs DC. Bonus = ``stats.mods[skill]``
        plus the sum of ``effects[skill]`` from every carried item."""
        world = ctx.deps.world
        mods = effective_mods(world.player.stats, world.player.items, world.items)
        return resolve_check(skill, dc, mods, ctx.deps.rng)

    @agent.tool
    def attack(
        ctx: RunContext[DirectorDeps], attack_mod: int, target_ac: int
    ) -> Resolution:
        """Resolve an attack roll: d20 + ``attack_mod`` vs ``target_ac``."""
        return resolve_attack(attack_mod, target_ac, ctx.deps.rng)

    @agent.tool
    def save(ctx: RunContext[DirectorDeps], save_kind: str, dc: int) -> Resolution:
        """Resolve a player saving throw: d20 + bonus vs DC. Bonus = ``stats.mods[save_kind]``
        plus the sum of ``effects[save_kind]`` from every carried item."""
        world = ctx.deps.world
        mods = effective_mods(world.player.stats, world.player.items, world.items)
        return resolve_save(save_kind, dc, mods, ctx.deps.rng)

    # ---------- Creation ----------

    @agent.tool
    def create_location(
        ctx: RunContext[DirectorDeps], id: str, name: str, description: str
    ) -> str:
        """Mint a new Location. Returns ``"ok"`` or an error string."""
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
        """Mint a new NPC. The player is NOT a Character — for the player use
        ``move_player`` / ``update_player_stats`` / ``add_player_item``."""
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
        """Mint a new Item. ``effects`` is the mechanical-bonus map (e.g.
        ``{"persuasion": 2}`` for a trained skill, ``{"attack": 1}`` for a +1 sword,
        ``{}`` for flavor-only items)."""
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
        """Mint a new Thread. Pass ``parent_id=None`` for a root thread."""
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
        """Mint a canonical Event. Engine assigns ``Event.t`` from ``world.next_event_t``.
        Use ``participants=[]`` for events with no character witnesses (backstory,
        weather, narration). Events are immutable once minted."""
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
        """Replace a thread's description (the arc has evolved)."""
        return _ok_or_err(
            apply_update_thread_description(
                ctx.deps.world, id=id, description=description
            )
        )

    @agent.tool
    def update_item_description(
        ctx: RunContext[DirectorDeps], id: str, description: str
    ) -> str:
        """Replace an item's description (state changed: charges consumed,
        condition, count, etc.)."""
        return _ok_or_err(
            apply_update_item_description(
                ctx.deps.world, id=id, description=description
            )
        )

    @agent.tool
    def move_character(ctx: RunContext[DirectorDeps], id: str, location_id: str) -> str:
        """Move an NPC to a new location."""
        return _ok_or_err(
            apply_move_character(ctx.deps.world, id=id, location_id=location_id)
        )

    @agent.tool
    def update_character_stats(
        ctx: RunContext[DirectorDeps], id: str, stats: CharacterStats
    ) -> str:
        """Replace an NPC's stats wholesale (HP changed, condition changed, etc.)."""
        return _ok_or_err(
            apply_update_character_stats(ctx.deps.world, id=id, stats=stats)
        )

    @agent.tool
    def move_player(ctx: RunContext[DirectorDeps], location_id: str) -> str:
        """Move the player to a new location."""
        return _ok_or_err(apply_move_player(ctx.deps.world, location_id=location_id))

    @agent.tool
    def update_player_stats(
        ctx: RunContext[DirectorDeps], stats: CharacterStats
    ) -> str:
        """Replace the player's stats wholesale (HP changed, ability change, etc.)."""
        return _ok_or_err(apply_update_player_stats(ctx.deps.world, stats=stats))

    @agent.tool
    def add_player_item(ctx: RunContext[DirectorDeps], item_id: str) -> str:
        """Give the player an item (must already exist via ``create_item``)."""
        return _ok_or_err(apply_add_player_item(ctx.deps.world, item_id=item_id))

    @agent.tool
    def remove_player_item(ctx: RunContext[DirectorDeps], item_id: str) -> str:
        """Take an item from the player (must currently be carried)."""
        return _ok_or_err(apply_remove_player_item(ctx.deps.world, item_id=item_id))

    @agent.tool
    def append_player_log(ctx: RunContext[DirectorDeps], text: str) -> str:
        """Append an NL log entry — what the player perceived this turn (or
        misinterpreted, or assumed). Always succeeds."""
        return _ok_or_err(apply_append_player_log(ctx.deps.world, text=text))

    @agent.tool
    def mark_end_scene(ctx: RunContext[DirectorDeps]) -> str:
        """Mark the current turn as a scene boundary. Records ``world.turn`` so
        the engine can group events by scene later."""
        ctx.deps.scene_boundaries.append(ctx.deps.world.turn)
        return "ok"

    return agent


# ---------- User-message templates ----------


def bootstrap_user_message() -> str:
    return (
        "## Bootstrap mode\n\n"
        "World is empty (`turn = -1`). Mint the initial world: locations, "
        "characters, items, threads, backstory events (use `narrative_time` "
        "strings like 'year 1043, spring'), the player's initial stats and "
        "items, and the player log (one entry for each thing the PC remembers "
        "or has just experienced). Then write the opening prose."
    )


def turn_user_message(world: WorldModel, player_input: str, prior_prose: str) -> str:
    return (
        f"{render_omniscient(world)}\n\n"
        "## Prior turn's prose\n\n"
        f"{prior_prose or '(none — this is the first turn after the opening.)'}\n\n"
        "## Player input\n\n"
        f"{player_input}"
    )


# ---------- Driver ----------


def run_director(
    world: WorldModel,
    user_message: str,
    rng: random.Random,
    *,
    model: Model | None = None,
    scene_boundaries: list[int] | None = None,
) -> str:
    """Run one Director turn. Returns prose. ``scene_boundaries`` is a
    caller-owned list that ``mark_end_scene`` appends to (mutated in place)."""
    if scene_boundaries is None:
        scene_boundaries = []
    agent = build_director(model)
    deps = DirectorDeps(world=world, rng=rng, scene_boundaries=scene_boundaries)
    start = time.monotonic()
    result = agent.run_sync(user_message, deps=deps)
    log_agent_call(
        agent="director",
        world_turn=world.turn,
        result=result,
        latency_ms=(time.monotonic() - start) * 1000,
    )
    # Concatenate every TextPart across all model responses. The model may emit
    # prose both before and after tool calls in the same run; `result.output`
    # only carries the final text part, so prose written before a tool call
    # would otherwise be lost.
    chunks: list[str] = []
    for msg in result.all_messages():
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, TextPart) and part.content:
                    chunks.append(part.content)
    return "\n\n".join(chunks)
