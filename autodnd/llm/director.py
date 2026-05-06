"""Director agents: bootstrap (game start) and per-turn.

Both share the same dice tools, but emit different output types:
:class:`BootstrapDirective` vs :class:`TurnDirective`.
"""

import random
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model
from pydantic_ai.output import PromptedOutput

from autodnd.engine.delta import BootstrapDirective, TurnDirective
from autodnd.engine.render import render_omniscient
from autodnd.engine.resolution import Resolution
from autodnd.engine.rules import resolve_attack, resolve_check, resolve_save, roll
from autodnd.engine.world import WorldModel
from autodnd.llm import load_prompt, model_from_env


@dataclass
class DirectorDeps:
    world: WorldModel
    rng: random.Random


def build_bootstrap_director(model: Model | None = None) -> Agent[DirectorDeps, BootstrapDirective]:
    # PromptedOutput puts the schema in the system prompt instead of forcing
    # tool_choice — works with reasoner models (DeepSeek, o1) that reject the
    # `required` tool_choice the default ToolOutput uses.
    return Agent(
        model or model_from_env(),
        deps_type=DirectorDeps,
        output_type=PromptedOutput(BootstrapDirective),
        system_prompt=load_prompt("director_bootstrap.md"),
    )


def build_turn_director(model: Model | None = None) -> Agent[DirectorDeps, TurnDirective]:
    agent = Agent(
        model or model_from_env(),
        deps_type=DirectorDeps,
        output_type=PromptedOutput(TurnDirective),
        system_prompt=load_prompt("director_turn.md"),
    )

    @agent.tool
    def roll_dice(ctx: RunContext[DirectorDeps], spec: str) -> int:
        """Roll a dice expression like ``2d6+3`` or ``d20``. Returns the sum."""
        return roll(spec, ctx.deps.rng)

    @agent.tool
    def check(ctx: RunContext[DirectorDeps], skill: str, dc: int) -> Resolution:
        """Resolve a player skill check: d20 + ``stats.mods[skill]`` vs DC."""
        return resolve_check(skill, dc, ctx.deps.world.player.stats.mods, ctx.deps.rng)

    @agent.tool
    def attack(ctx: RunContext[DirectorDeps], attack_mod: int, target_ac: int) -> Resolution:
        """Resolve an attack roll: d20 + ``attack_mod`` vs ``target_ac``."""
        return resolve_attack(attack_mod, target_ac, ctx.deps.rng)

    @agent.tool
    def save(ctx: RunContext[DirectorDeps], save_kind: str, dc: int) -> Resolution:
        """Resolve a player saving throw: d20 + ``stats.mods[save_kind]`` vs DC."""
        return resolve_save(save_kind, dc, ctx.deps.world.player.stats.mods, ctx.deps.rng)

    return agent


def run_bootstrap_director(
    rng: random.Random,
    *,
    model: Model | None = None,
    world: WorldModel | None = None,
) -> BootstrapDirective:
    """Mint the initial world. ``world`` is unused but accepted for symmetry with deps."""
    agent = build_bootstrap_director(model)
    deps = DirectorDeps(world=world or _placeholder_world(), rng=rng)
    return agent.run_sync("Begin a new session. Mint the initial world.", deps=deps).output


def run_turn_director(
    world: WorldModel,
    player_input: str,
    prior_prose: str,
    rng: random.Random,
    *,
    model: Model | None = None,
) -> TurnDirective:
    agent = build_turn_director(model)
    user_message = (
        f"{render_omniscient(world)}\n\n"
        f"## Prior Narrator prose (last turn)\n\n"
        f"{prior_prose or '(no prior turn — this is the first.)'}\n\n"
        f"## Player input\n\n{player_input}"
    )
    return agent.run_sync(user_message, deps=DirectorDeps(world=world, rng=rng)).output


def _placeholder_world() -> WorldModel:
    """A throwaway world for the bootstrap call's deps slot — bootstrap doesn't read world state."""
    from autodnd.engine.world import CharacterStats, PlayerState

    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)), turn=-1
    )
