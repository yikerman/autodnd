"""Manual demo: a single full arbiter cycle on the vale_inn fixture.

Run with:
    uv run python -m autodnd.demos.slice3_cycle

Requires ``MODEL_ENDPOINT``, ``MODEL_KEY``, ``MODEL_NAME`` in the environment.
Conducts one cycle for the player input "I sit down at the bar and ask Brona
for a drink." and prints prose blocks, post-cycle world state, intents, and
leak warnings.

What to look for:
- Prose blocks read in dramatic order (e.g., narrator, then Brona).
- ``world.history`` grew with records minted by the arbiter, character, and
  narrator. Each has the right ``participants``.
- ``leak_warnings`` is empty (or, if non-empty, the warned description does
  in fact name a non-participant — a real find).
"""

from __future__ import annotations

import random

from dotenv import load_dotenv

from autodnd.engine.world import World
from autodnd.fixtures import vale_inn
from autodnd.llm.arbiter import build_arbiter_agent, run_cycle
from autodnd.llm.character import build_character_agent
from autodnd.llm.client import model_from_env
from autodnd.llm.narrator import build_narrator_agent


def main() -> None:
    load_dotenv()
    model = model_from_env()
    arbiter = build_arbiter_agent(model)
    character = build_character_agent(model)
    narrator = build_narrator_agent(model)

    world = World()
    vale_inn(world)

    trigger = "Player input: I sit down at the bar and ask Brona for a drink."
    print(f"=== trigger ===\n{trigger}\n")
    deps = run_cycle(arbiter, character, narrator, world, trigger, rng=random.Random(0))

    print("=== prose blocks (in invocation order) ===")
    for i, block in enumerate(deps.prose_blocks):
        print(f"\n--- block {i} ---")
        print(block)

    if deps.pending_intents:
        print(f"\n=== pending intents ===\n{deps.pending_intents}")
    if deps.leak_warnings:
        print(f"\n=== leak warnings ===\n{deps.leak_warnings}")

    print("\n=== world.history ===")
    for h in world.history:
        print(
            f"  {h.id} (t={h.t}) loc={h.location_id} "
            f"participants={h.participants}\n     {h.description!r}"
        )
    print(f"\nnarrative_time: {world.narrative_time}")


if __name__ == "__main__":
    main()
