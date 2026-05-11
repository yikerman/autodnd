"""Arbiter LLM agent — the conductor.

15 tools: 3 creation + 1 mint + 5 state mutation + 4 dice + 2 control.
Runs as a multi-round session per cycle. ``invoke_actor`` dispatches to
character or narrator agents (passed in via deps); their prose accumulates
into ``deps.prose_blocks`` for the engine to emit to the player.

The arbiter never writes prose itself — that's the actors' job. The arbiter
mints history, rolls dice, applies state, and decides who acts when.
"""

from __future__ import annotations

import random
import sys
import time
from dataclasses import dataclass, field

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from autodnd.engine.delta import (
    advance_narrative_time as _advance_narrative_time,
    create_character as _create_character,
    create_item as _create_item,
    create_location as _create_location,
    mint_history as _mint_history,
    move as _move,
    transfer_item as _transfer_item,
    update_item_description as _update_item_description,
    update_stats as _update_stats,
)
from autodnd.engine.perception import names_leaked_in_description
from autodnd.engine.render import ARBITER_SYSTEM, render_arbiter
from autodnd.engine.rules import (
    resolve_attack,
    resolve_check,
    resolve_save,
    roll as roll_dice,
)
from autodnd.engine.world import (
    Abilities,
    AtLocation,
    HeldBy,
    World,
)
from autodnd.llm.character import CharacterDeps, run_character
from autodnd.llm.narrator import run_narrator
from autodnd.trace import trace_run


# Soft cap on arbiter rounds before forcibly ending. Combat with many actors
# can chew several dozen; calm cycles use < 10. 50 is the empirical-feeling
# midpoint until traces tell us otherwise.
MAX_ROUNDS = 50


@dataclass
class ArbiterDeps:
    """Per-cycle state threaded through every arbiter tool call.

    ``cycle_history_ids`` accumulates ids of records minted during this cycle;
    used by character/narrator renders to fill the "Just happened (this
    cycle)" section.

    ``prose_blocks`` accumulates per-actor-invocation prose in invocation
    order; the engine concatenates these to build the player-facing output.

    ``pending_intents`` holds ``(actor_id, intent)`` declarations from
    character ``act()`` calls — the arbiter resolves these on its next round.
    """

    world: World
    character_agent: Agent[CharacterDeps, str]
    narrator_agent: Agent[None, str]
    cycle_history_ids: list[str] = field(default_factory=list)
    prose_blocks: list[str] = field(default_factory=list)
    pending_intents: list[tuple[str, str]] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)
    leak_warnings: list[str] = field(default_factory=list)


def build_arbiter_agent(model: Model) -> Agent[ArbiterDeps, str]:
    """Construct the arbiter agent. Reuse across cycles."""
    agent: Agent[ArbiterDeps, str] = Agent(
        model,
        deps_type=ArbiterDeps,
        output_type=str,
        system_prompt=ARBITER_SYSTEM,
    )

    # ---------- Creation ----------

    @agent.tool
    def create_location(
        ctx: RunContext[ArbiterDeps],
        location_id: str,
        name: str,
        description: str,
    ) -> str:
        return _create_location(
            ctx.deps.world,
            location_id=location_id,
            name=name,
            description=description,
        )

    @agent.tool
    def create_character(
        ctx: RunContext[ArbiterDeps],
        character_id: str,
        name: str,
        description: str,
        location_id: str,
        hp: int,
        hp_max: int,
        ac: int,
        gold: int = 0,
        skill_mods: dict[str, int] | None = None,
    ) -> str:
        return _create_character(
            ctx.deps.world,
            character_id=character_id,
            name=name,
            description=description,
            location_id=location_id,
            hp=hp,
            hp_max=hp_max,
            ac=ac,
            abilities=Abilities(),
            skill_mods=skill_mods,
            gold=gold,
        )

    @agent.tool
    def create_item(
        ctx: RunContext[ArbiterDeps],
        item_id: str,
        name: str,
        description: str,
        at_location_id: str | None = None,
        held_by_character_id: str | None = None,
        effects: dict[str, int] | None = None,
    ) -> str:
        if at_location_id is not None and held_by_character_id is not None:
            return (
                "error: provide either at_location_id or held_by_character_id, not both"
            )
        if at_location_id is not None:
            position = AtLocation(location_id=at_location_id)
        elif held_by_character_id is not None:
            position = HeldBy(character_id=held_by_character_id)
        else:
            return "error: provide at_location_id or held_by_character_id"
        return _create_item(
            ctx.deps.world,
            item_id=item_id,
            name=name,
            description=description,
            position=position,
            effects=effects,
        )

    # ---------- History ----------

    @agent.tool
    def mint_history(
        ctx: RunContext[ArbiterDeps],
        participants: list[str],
        description: str,
        location_id: str | None = None,
        narrative_time: str | None = None,
    ) -> str:
        result = _mint_history(
            ctx.deps.world,
            participants=participants,
            description=description,
            location_id=location_id,
            narrative_time=narrative_time,
        )
        if result.startswith("ok:"):
            event_id = ctx.deps.world.history[-1].id
            ctx.deps.cycle_history_ids.append(event_id)
            leaked = names_leaked_in_description(
                description, participants, ctx.deps.world
            )
            if leaked:
                warning = (
                    f"warning: {event_id} description mentions {leaked} "
                    f"not in participants — possible leak"
                )
                ctx.deps.leak_warnings.append(warning)
                print(warning, file=sys.stderr)
        return result

    # ---------- State mutation ----------

    @agent.tool
    def move(ctx: RunContext[ArbiterDeps], character_id: str, location_id: str) -> str:
        return _move(ctx.deps.world, character_id=character_id, location_id=location_id)

    @agent.tool
    def update_stats(
        ctx: RunContext[ArbiterDeps],
        character_id: str,
        hp: int | None = None,
        hp_max: int | None = None,
        ac: int | None = None,
        gold: int | None = None,
    ) -> str:
        return _update_stats(
            ctx.deps.world,
            character_id=character_id,
            hp=hp,
            hp_max=hp_max,
            ac=ac,
            gold=gold,
        )

    @agent.tool
    def transfer_item(
        ctx: RunContext[ArbiterDeps],
        item_id: str,
        to_character_id: str | None = None,
        to_location_id: str | None = None,
    ) -> str:
        if to_character_id is not None and to_location_id is not None:
            return "error: provide either to_character_id or to_location_id, not both"
        if to_character_id is not None:
            position = HeldBy(character_id=to_character_id)
        elif to_location_id is not None:
            position = AtLocation(location_id=to_location_id)
        else:
            return "error: provide to_character_id or to_location_id"
        return _transfer_item(ctx.deps.world, item_id=item_id, to=position)

    @agent.tool
    def update_item_description(
        ctx: RunContext[ArbiterDeps], item_id: str, description: str
    ) -> str:
        return _update_item_description(
            ctx.deps.world, item_id=item_id, description=description
        )

    @agent.tool
    def advance_narrative_time(ctx: RunContext[ArbiterDeps], new_time: str) -> str:
        return _advance_narrative_time(ctx.deps.world, new_time=new_time)

    # ---------- Dice ----------

    @agent.tool
    def roll(ctx: RunContext[ArbiterDeps], spec: str) -> str:
        try:
            return f"rolled {spec}: {roll_dice(spec, ctx.deps.rng)}"
        except ValueError as e:
            return f"error: {e}"

    @agent.tool
    def check(
        ctx: RunContext[ArbiterDeps], skill: str, dc: int, modifier: int = 0
    ) -> str:
        return resolve_check(
            skill=skill, dc=dc, modifier=modifier, rng=ctx.deps.rng
        ).detail

    @agent.tool
    def attack(ctx: RunContext[ArbiterDeps], attack_mod: int, target_ac: int) -> str:
        return resolve_attack(
            attack_mod=attack_mod, target_ac=target_ac, rng=ctx.deps.rng
        ).detail

    @agent.tool
    def save(
        ctx: RunContext[ArbiterDeps],
        save_kind: str,
        dc: int,
        modifier: int = 0,
    ) -> str:
        return resolve_save(
            save_kind=save_kind, dc=dc, modifier=modifier, rng=ctx.deps.rng
        ).detail

    # ---------- Control flow ----------

    @agent.tool
    def invoke_actor(ctx: RunContext[ArbiterDeps], actor_id: str, hint: str) -> str:
        """Invoke a character or the narrator. Returns a summary of what they did."""
        deps = ctx.deps
        if actor_id == "narrator":
            prose, event_id = run_narrator(
                deps.narrator_agent,
                deps.world,
                cycle_history_ids=deps.cycle_history_ids,
                arbiter_hint=hint,
            )
            deps.prose_blocks.append(prose)
            if event_id is not None:
                deps.cycle_history_ids.append(event_id)
            return f"narrator emitted prose ({len(prose)} chars)"

        if actor_id not in deps.world.characters:
            return f"error: no character {actor_id!r}"

        prose, sub_deps = run_character(
            deps.character_agent,
            deps.world,
            actor_id,
            cycle_history_ids=deps.cycle_history_ids,
            arbiter_hint=hint,
            rng=deps.rng,
        )
        deps.prose_blocks.append(prose)
        for event_id in sub_deps.cycle_history_ids:
            if event_id not in deps.cycle_history_ids:
                deps.cycle_history_ids.append(event_id)
        for intent in sub_deps.intents:
            deps.pending_intents.append((actor_id, intent))

        summary_parts: list[str] = [f"{actor_id} acted"]
        if sub_deps.cycle_history_ids:
            summary_parts.append(f"minted: {sub_deps.cycle_history_ids}")
        if sub_deps.intents:
            summary_parts.append(f"intents: {sub_deps.intents}")
        return " | ".join(summary_parts)

    @agent.tool
    def end_cycle(ctx: RunContext[ArbiterDeps]) -> str:
        """Signal that the cycle is complete. Emit a final brief acknowledgment after this."""
        return (
            "ok: cycle ending — emit a brief acknowledgment text and stop calling tools"
        )

    return agent


def run_cycle(
    arbiter_agent: Agent[ArbiterDeps, str],
    character_agent: Agent[CharacterDeps, str],
    narrator_agent: Agent[None, str],
    world: World,
    trigger: str,
    *,
    rng: random.Random | None = None,
) -> ArbiterDeps:
    """Run one cycle of the simulator. Returns the populated deps.

    Caller takes ``deps.prose_blocks`` to emit to the player and inspects
    ``deps.cycle_history_ids``, ``deps.pending_intents``, and
    ``deps.leak_warnings`` for follow-up handling.
    """
    deps = ArbiterDeps(
        world=world,
        character_agent=character_agent,
        narrator_agent=narrator_agent,
        rng=rng or random.Random(),
    )
    _system, user = render_arbiter(world, trigger)
    start = time.perf_counter()
    result = arbiter_agent.run_sync(user, deps=deps)
    trace_run("arbiter", result, (time.perf_counter() - start) * 1000)
    return deps
