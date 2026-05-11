"""Character LLM agent — 5 tools, restricted view, in-character voice.

The system prompt is built dynamically from ``render_for_character`` per call,
which reads the character's public-only ``description``. The view (user prompt)
is also built per call: only history with the character in ``participants`` is
included. Engine constructs the firewall — never a soft prompt instruction.

Tools split:
- Self-effecting (``say``, ``move_self``, ``transfer_item``): apply directly.
- Cross-character: declared via ``act(intent)``; arbiter resolves on its
  next round. This is the structural fix for "character does something the
  arbiter didn't anticipate."
- Dice (self-checks only): ``request_dice_check``, ``request_dice_attack``,
  ``request_dice_save``.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from autodnd.engine.delta import mint_history, move
from autodnd.engine.delta import transfer_item as delta_transfer_item
from autodnd.engine.perception import who_is_in
from autodnd.engine.render import render_for_character
from autodnd.engine.rules import resolve_attack, resolve_check, resolve_save
from autodnd.engine.world import PLAYER, HeldBy, World
from autodnd.trace import trace_run


@dataclass
class CharacterDeps:
    """Per-call inputs and per-call outputs threaded through tools."""

    world: World
    character_id: str
    cycle_history_ids: list[str] = field(default_factory=list)
    intents: list[str] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)
    arbiter_hint: str | None = None


def build_character_agent(model: Model) -> Agent[CharacterDeps, str]:
    """Construct the character agent with all 5 tools.

    One agent serves every character — system prompt and view are dynamic
    per call via ``deps.character_id``. Build once, reuse.
    """
    agent: Agent[CharacterDeps, str] = Agent(
        model,
        deps_type=CharacterDeps,
        output_type=str,
    )

    @agent.system_prompt
    def _system(ctx: RunContext[CharacterDeps]) -> str:
        system, _user = render_for_character(ctx.deps.world, ctx.deps.character_id)
        return system

    @agent.tool
    def say(ctx: RunContext[CharacterDeps], content: str) -> str:
        """Speak the given content aloud.

        Mints a history record with you and every character at your location
        as participants (everyone present hears it). Does not include
        bystanders elsewhere or eavesdroppers — those are the arbiter's call.
        """
        world = ctx.deps.world
        cid = ctx.deps.character_id
        char = world.characters[cid]
        present = who_is_in(world, char.location_id)
        before_count = len(world.history)
        result = mint_history(
            world,
            participants=present,
            description=f"{char.name} said: {content!r}",
            location_id=char.location_id,
        )
        if result.startswith("ok:") and len(world.history) > before_count:
            ctx.deps.cycle_history_ids.append(world.history[-1].id)
        return result

    @agent.tool
    def act(ctx: RunContext[CharacterDeps], intent: str) -> str:
        """Declare a non-speech action (attack, pickpocket, gesture toward another).

        The arbiter resolves it on its next round — rolls dice, mints
        cross-character events, schedules reactions. Use this for anything
        that affects characters other than yourself.
        """
        ctx.deps.intents.append(intent)
        return f"ok: intent recorded — {intent}"

    @agent.tool
    def request_dice_check(
        ctx: RunContext[CharacterDeps],
        skill: str,
        dc: int,
        modifier: int = 0,
    ) -> str:
        """Roll a self-check (perception, stealth, insight, etc.). For self only."""
        res = resolve_check(skill=skill, dc=dc, modifier=modifier, rng=ctx.deps.rng)
        return res.detail

    @agent.tool
    def request_dice_attack(
        ctx: RunContext[CharacterDeps], attack_mod: int, target_ac: int
    ) -> str:
        """Roll an attack. Resolves only the roll; the arbiter decides damage."""
        res = resolve_attack(
            attack_mod=attack_mod, target_ac=target_ac, rng=ctx.deps.rng
        )
        return res.detail

    @agent.tool
    def request_dice_save(
        ctx: RunContext[CharacterDeps],
        save_kind: str,
        dc: int,
        modifier: int = 0,
    ) -> str:
        """Roll a saving throw."""
        res = resolve_save(
            save_kind=save_kind, dc=dc, modifier=modifier, rng=ctx.deps.rng
        )
        return res.detail

    @agent.tool
    def move_self(ctx: RunContext[CharacterDeps], location_id: str) -> str:
        """Move yourself to another location."""
        return move(
            ctx.deps.world,
            character_id=ctx.deps.character_id,
            location_id=location_id,
        )

    @agent.tool
    def transfer_item(
        ctx: RunContext[CharacterDeps],
        item_id: str,
        recipient_character_id: str,
    ) -> str:
        """Give an item you currently hold to another character."""
        world = ctx.deps.world
        if recipient_character_id == PLAYER:
            recipient = HeldBy(character_id=PLAYER)
        elif recipient_character_id in world.characters:
            recipient = HeldBy(character_id=recipient_character_id)
        else:
            return f"error: character {recipient_character_id!r} does not exist"
        item = world.items.get(item_id)
        if item is None:
            return f"error: item {item_id!r} does not exist"
        if not (
            isinstance(item.position, HeldBy)
            and item.position.character_id == ctx.deps.character_id
        ):
            return f"error: you don't hold {item_id!r}"
        return delta_transfer_item(world, item_id=item_id, to=recipient)

    return agent


def run_character(
    agent: Agent[CharacterDeps, str],
    world: World,
    character_id: str,
    *,
    cycle_history_ids: list[str] | None = None,
    arbiter_hint: str | None = None,
    rng: random.Random | None = None,
) -> tuple[str, CharacterDeps]:
    """Synchronously invoke a character. Returns (prose, deps).

    ``deps.cycle_history_ids`` accumulates ids of history records minted
    during this call. ``deps.intents`` carries ``act()`` declarations the
    arbiter must resolve on its next round.
    """
    if character_id == PLAYER:
        raise ValueError("the player is not an NPC actor")
    _system, user = render_for_character(
        world,
        character_id,
        cycle_history_ids=cycle_history_ids,
        arbiter_hint=arbiter_hint,
    )
    deps = CharacterDeps(
        world=world,
        character_id=character_id,
        cycle_history_ids=list(cycle_history_ids or []),
        intents=[],
        rng=rng or random.Random(),
        arbiter_hint=arbiter_hint,
    )
    start = time.perf_counter()
    result = agent.run_sync(user, deps=deps)
    trace_run(
        "character",
        result,
        (time.perf_counter() - start) * 1000,
        extra={"actor": character_id},
    )
    return result.output, deps
