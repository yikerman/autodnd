"""Interactive Q&A bootstrapper.

Conducts a short interview with the player, minting atoms as their answers
firm up, and hands off via ``begin_play()`` once a small set of structural
invariants is satisfied. The handoff is the only gate — when ``begin_play``
returns an error string, the LLM is expected to fix what is missing and retry.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model

from autodnd.engine.delta import (
    advance_narrative_time as _advance_narrative_time,
    create_character as _create_character,
    create_item as _create_item,
    create_location as _create_location,
    mint_history as _mint_history,
)
from autodnd.engine.world import Abilities, AtLocation, HeldBy, World
from autodnd.trace import trace_run


BOOTSTRAPPER_SYSTEM = """\
You build the starting state of a fictional world simulator through a short
interview with the player. Mint atoms via tool calls as their answers firm up.
Never narrate scene prose. Hand off via begin_play() when the world is playable.

# Cadence

Ask one or two focused questions per turn — setting/tone first, then the
protagonist hook, then the opening situation. If the player front-loads detail,
skip ahead and only ask what is still missing. Confirm briefly after each
cluster of mints. Do not survey; do not bury the player.

# Depth target

Aim for a textured opening, not a sketch:
- 4-8 locations the campaign could plausibly reach.
- 4-10 characters total, one of which MUST be `character_id="player"`.
- 0-6 items, placed at locations or held by characters.
- 10-25 history records mixing:
  - cosmic backstory (`participants=[]`) — old wars, conspiracies, omens;
  - per-character private knowledge (single participant) — secrets, plans,
    motives, debts, false beliefs;
  - at least one in-scene beat (multi-participant including `player`) so play
    has a starting moment.

# Atom rules

- Player MUST use `character_id="player"`. The player is a character, not a
  separate atom.
- `Character.description` is PUBLIC-facing identity only — race, appearance,
  manner, voice, role. NEVER secrets, plans, stances, or private history.
  Spoilable content lives in private history records with that character as
  the sole participant.
- Items use exactly one of `at_location_id` or `held_by_character_id`.
- History: `participants=[]` is cosmic (no character knows it); single
  participant is that character's private knowledge; multi-participant means
  a real beat those characters witnessed together.

# Output discipline

Speak to the player as a DM warming up a table: short, in-character questions
and brief confirmations. Never expose tool names or schema. Do not write
opening scene prose — the narrator handles that at first play.

# Handoff

When the world is dense enough and the opening beat is in place, call
`set_opening_time` and then `begin_play()`. If `begin_play` returns an error,
read it, mint what is missing, and retry. After `begin_play` returns ok, emit
one short acknowledgment and stop calling tools.
"""


BOOTSTRAPPER_KICKOFF = (
    "Start the interview. Ask me a couple of focused questions about the world "
    "and the character you'll build for me, and mint atoms as my answers firm up."
)


@dataclass
class BootstrapperDeps:
    world: World
    ready: bool = False


def build_bootstrapper_agent(model: Model) -> Agent[BootstrapperDeps, str]:
    agent: Agent[BootstrapperDeps, str] = Agent(
        model,
        deps_type=BootstrapperDeps,
        output_type=str,
        system_prompt=BOOTSTRAPPER_SYSTEM,
    )

    @agent.tool
    def create_location(
        ctx: RunContext[BootstrapperDeps],
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
        ctx: RunContext[BootstrapperDeps],
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
        ctx: RunContext[BootstrapperDeps],
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

    @agent.tool
    def mint_history(
        ctx: RunContext[BootstrapperDeps],
        participants: list[str],
        description: str,
        location_id: str | None = None,
        narrative_time: str | None = None,
    ) -> str:
        return _mint_history(
            ctx.deps.world,
            participants=participants,
            description=description,
            location_id=location_id,
            narrative_time=narrative_time,
        )

    @agent.tool
    def set_opening_time(ctx: RunContext[BootstrapperDeps], new_time: str) -> str:
        """Set the opening fictional time (e.g. 'Day 1, dusk'). Required before begin_play."""
        return _advance_narrative_time(ctx.deps.world, new_time=new_time)

    @agent.tool
    def begin_play(ctx: RunContext[BootstrapperDeps]) -> str:
        """Hand off to play. Returns an error string if structural invariants are unmet."""
        world = ctx.deps.world
        missing: list[str] = []
        if not world.locations:
            missing.append("no locations created")
        player = world.characters.get("player")
        if player is None:
            missing.append("player character not created (use character_id='player')")
        else:
            if player.hp <= 0:
                missing.append("player hp is 0 — start the player with positive hp")
            if player.location_id not in world.locations:
                missing.append("player's location is unknown")
        if not any(
            h.location_id is not None and "player" in h.participants
            for h in world.history
        ):
            missing.append(
                "no opening scene history — mint a history record with the "
                "player as participant and a location set"
            )
        if world.narrative_time == "Day 1, dawn":
            missing.append(
                "narrative time is still the default — call set_opening_time"
            )
        if missing:
            return "error: cannot begin play — " + "; ".join(missing)
        ctx.deps.ready = True
        return "ok: ready for play"

    return agent


def run_bootstrapper(
    agent: Agent[BootstrapperDeps, str],
    world: World,
    *,
    read_input: Callable[[], str | None],
    on_agent_message: Callable[[str], None],
    max_turns: int = 24,
) -> bool:
    """Run the bootstrapper as a multi-turn interview.

    Each turn the agent's text output is forwarded to ``on_agent_message`` and
    the next player line is fetched via ``read_input``. Empty input or ``None``
    (EOF) aborts. Returns True iff ``begin_play()`` succeeded.
    """
    deps = BootstrapperDeps(world=world)
    history: list[ModelMessage] = []
    user_input = BOOTSTRAPPER_KICKOFF

    for turn_idx in range(max_turns):
        start = time.perf_counter()
        result = agent.run_sync(user_input, deps=deps, message_history=history or None)
        trace_run(
            f"bootstrapper.t{turn_idx}",
            result,
            (time.perf_counter() - start) * 1000,
        )
        history = list(result.all_messages())

        if result.output and result.output.strip():
            on_agent_message(result.output)
        if deps.ready:
            return True

        next_line = read_input()
        if not next_line:
            return False
        user_input = next_line

    return False
