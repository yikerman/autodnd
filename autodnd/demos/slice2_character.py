"""Manual demo: invoke a character LLM against the vale_inn fixture.

Run with:
    uv run python -m autodnd.demos.slice2_character

Requires ``MODEL_ENDPOINT``, ``MODEL_KEY``, ``MODEL_NAME`` in the environment
(or in ``.env``). Reads no input — produces several invocations with different
hints so you can read the output and judge whether the character stayed in
voice and didn't reveal anything outside their event history.

What to look for:
- Brona's voice (gruff, careful) is consistent.
- She does not narrate the player's thoughts (her render doesn't contain them).
- She doesn't volunteer her private resolution about Korel (it's in her events
  but the system prompt instructs in-character reticence).
"""

from __future__ import annotations

import random

from dotenv import load_dotenv

from autodnd.engine.world import World
from autodnd.fixtures import vale_inn
from autodnd.llm.character import build_character_agent, run_character
from autodnd.llm.client import model_from_env


_HINTS: list[tuple[str, str]] = [
    ("brona", "The player just sat down at the bar. Greet them, terse."),
    (
        "brona",
        "The player asks: 'What's the news from up the road?' Answer briefly.",
    ),
    (
        "brona",
        "The player asks if you've seen anyone matching a tall cloaked figure. "
        "Answer carefully.",
    ),
    ("player", "The bartender greeted you. Order a drink."),
]


def _print_history(world: World) -> None:
    print("--- world.history ---")
    for h in world.history:
        print(f"  {h.id} (t={h.t}) participants={h.participants} {h.description!r}")


def main() -> None:
    load_dotenv()
    model = model_from_env()
    agent = build_character_agent(model)

    world = World()
    vale_inn(world)

    rng = random.Random(0)
    for actor_id, hint in _HINTS:
        print(f"\n=== {actor_id}  ({hint!r}) ===")
        prose, deps = run_character(agent, world, actor_id, arbiter_hint=hint, rng=rng)
        print(prose)
        if deps.intents:
            print(f"  [intents declared: {deps.intents}]")
        if deps.cycle_history_ids:
            print(f"  [history minted: {deps.cycle_history_ids}]")

    print()
    _print_history(world)


if __name__ == "__main__":
    main()
