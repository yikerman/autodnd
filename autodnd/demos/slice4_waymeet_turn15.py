"""Manual demo: reproduce the test.json turn-15 failure scenario.

Run with:
    uv run python -m autodnd.demos.slice4_waymeet_turn15

Setup: ports the Waymeet atoms from ``test.json`` with secrets stripped out
of character descriptions into private History records. At the moment of the
trigger, Thrag has just walked into The Anvil's Rest and asked "This seat
taken?" — and the player input is Fox's dismissive gesture.

What to compare against ``test.json``:

Failure mode A — exposition dump:
- Legacy prose (turn 15) opened with a long "What the archives told you
  freely... What the restricted text told you... Lirien..." exposition dump.
- New system: Fox's archive reading is in his private history. The arbiter
  has it, but won't surface it as exposition unless the fiction warrants
  doing so. Characters can't see it. Narrator can only describe what the
  player perceives.

Failure mode B — over-reading subtext:
- Legacy: Brona "set the cup down. Hard." with disappointment; Thrag "narrowed
  eyes" — implying they detected meaning beyond Fox's surface rudeness.
- New system: Brona and Thrag's perception views contain only what's been
  minted. Their reactions should reflect rudeness, not classified knowledge
  subtext.

Look for:
- Prose blocks read in dramatic order.
- ``world.history`` grew with reactions, not exposition.
- ``leak_warnings`` is empty.
"""

from __future__ import annotations

import random

from dotenv import load_dotenv

from autodnd import trace as trace_module
from autodnd.engine.world import World
from autodnd.fixtures import waymeet_scene
from autodnd.llm.arbiter import build_arbiter_agent, run_cycle
from autodnd.llm.character import build_character_agent
from autodnd.llm.client import model_from_env
from autodnd.llm.narrator import build_narrator_agent


TRIGGER = (
    "Player input: I gesture dismissively to the orc — half-distracted, "
    "attention still on my journal page with the Dragon's Tooth sketch."
)


def main() -> None:
    load_dotenv()
    trace_path = trace_module.init()
    print(f"Trace log: {trace_path}\n")

    model = model_from_env()
    arbiter = build_arbiter_agent(model)
    character = build_character_agent(model)
    narrator = build_narrator_agent(model)

    world = World()
    waymeet_scene(world)

    print("=== trigger ===")
    print(TRIGGER)
    print()

    deps = run_cycle(arbiter, character, narrator, world, TRIGGER, rng=random.Random(0))

    print("=== prose blocks (in invocation order) ===")
    for i, block in enumerate(deps.prose_blocks):
        print(f"\n--- block {i} ---")
        print(block)

    if deps.pending_intents:
        print(f"\n=== pending intents ===\n{deps.pending_intents}")
    if deps.leak_warnings:
        print("\n=== ⚠ leak warnings ===")
        for w in deps.leak_warnings:
            print(f"  {w}")

    print("\n=== history minted during this cycle ===")
    for hid in deps.cycle_history_ids:
        h = next(h for h in world.history if h.id == hid)
        print(
            f"  {h.id} loc={h.location_id} participants={h.participants}\n"
            f"     {h.description!r}"
        )
    print(f"\nnarrative_time: {world.narrative_time}")


if __name__ == "__main__":
    main()
