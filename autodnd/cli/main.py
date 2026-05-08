"""REPL entry point for AutoDND.

Per turn: free-text input → Director (omniscient + dice/mutation tools) → prose.
Slash commands route to the Sidebar (read-only Q&A over the player's own state).
"""

from __future__ import annotations

import argparse
import random
import readline  # noqa: F401  # imported for its side effect: arrow-key line editing in input()
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai.messages import ModelMessage

from autodnd.cli.output import print_block, print_status, read_input
from autodnd.cli.persistence import load_session, save_session
from autodnd.engine.world import CharacterStats, PlayerState, WorldModel
from autodnd.fixtures import seed_inn_scene
from autodnd.llm import tracing
from autodnd.llm.bootstrapper import bootstrap_user_message, run_bootstrapper
from autodnd.llm.director import run_director, turn_user_message
from autodnd.llm.sidebar import run_sidebar

BANNER = """\
AutoDND — solo one-shot DM. Type your action, or:
  /hp        — show your HP
  /log       — show recent events
  /inv       — show inventory and gold
  /ask Q     — free-form sidebar question
  /save FILE — snapshot session to FILE (resume later with --load FILE)
  /help      — this banner
  /quit      — exit
"""

SLASH_FAST_QUERIES = {
    "/hp": "Show my HP, AC, ability scores, and modifiers.",
    "/log": "Show my story log in chronological order.",
    "/inv": "Show my inventory and gold.",
}


def _empty_world() -> WorldModel:
    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)),
        turn=-1,
    )


def initialize_session(*, demo_scene: bool) -> tuple[WorldModel, str]:
    """Returns (seeded world, opening prose).

    Demo path uses the hardcoded fixture. LLM path runs the Bootstrapper in a
    Q&A loop until it calls ``begin_play`` (which flips ``world.turn`` to 0);
    the prose from that final turn is the opening narration.
    """
    world = _empty_world()
    if demo_scene:
        return world, seed_inn_scene(world)

    history: list[ModelMessage] = []
    user_msg = bootstrap_user_message()
    while True:
        prose, history = run_bootstrapper(
            world, user_msg, message_history=history
        )
        _print_block(prose, kind="prose")
        if world.turn == 0:
            return world, prose
        line = _read_input()
        if line is None:
            raise SystemExit(0)
        if line in ("/quit", "/exit"):
            raise SystemExit(0)
        # Bootstrap doesn't route slash commands — Sidebar has no canon to
        # read yet, and /save mid-bootstrap is out of scope.
        user_msg = line


def run_turn(
    world: WorldModel,
    player_input: str,
    prior_prose: list[str],
    rng: random.Random,
) -> str:
    prose = run_director(
        world,
        turn_user_message(world, player_input, prior_prose),
        rng,
    )
    world.turn += 1
    return prose


def handle_slash(line: str, world: WorldModel) -> str:
    cmd, _, rest = line.partition(" ")
    match cmd:
        case "/help":
            return BANNER
        case "/quit" | "/exit":
            raise SystemExit(0)
        case "/hp" | "/log" | "/inv":
            return run_sidebar(
                world.player,
                SLASH_FAST_QUERIES[cmd],
                items=world.items,
                world_turn=world.turn,
            )
        case "/ask":
            query = rest.strip() or "Show my current status."
            return run_sidebar(
                world.player, query, items=world.items, world_turn=world.turn
            )
        case _:
            return f"Unknown command: {cmd}. Try /help."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="autodnd", description=__doc__)
    start = parser.add_mutually_exclusive_group()
    start.add_argument(
        "--demo-scene",
        action="store_true",
        help="use the hardcoded Crow's Foot Inn fixture instead of LLM bootstrap",
    )
    start.add_argument(
        "--load",
        metavar="FILE",
        type=Path,
        help="resume a session previously written by /save",
    )
    return parser.parse_args(argv)


def _is_status_message(text: str) -> bool:
    """True for the bracket-prefixed engine messages run_turn returns when there's
    nothing to narrate — used to style them differently from real prose."""
    return text.startswith("[") and text.endswith("]") and "\n" not in text


def _print_block(text: str, *, kind: str = "prose") -> None:
    print_block(text, kind=kind)


def _read_input() -> str | None:
    return read_input()


def main() -> None:
    load_dotenv()
    args = parse_args()
    rng = random.Random()

    trace_path = tracing.init()

    _print_block(BANNER, kind="banner")
    if trace_path:
        print_status(f"Trace log: {trace_path}")

    if args.load is not None:
        print_status(f"Loading session from {args.load}…")
        snap = load_session(args.load)
        world, prior_prose = snap.world, snap.prior_prose
        if prior_prose:
            _print_block(prior_prose[-1], kind="prose")
    else:
        print_status("Initializing world…")
        world, opening_prose = initialize_session(demo_scene=args.demo_scene)
        prior_prose = [opening_prose]
        # Demo path prints opening here. LLM path's bootstrapper loop already
        # printed each turn (including the opening), so suppress duplicate.
        if args.demo_scene:
            _print_block(opening_prose, kind="prose")

    while True:
        line = _read_input()
        if line is None:
            return
        if not line:
            continue
        try:
            if line.startswith("/save"):
                _, _, rest = line.partition(" ")
                target = rest.strip()
                if not target:
                    _print_block("Usage: /save <file>", kind="error")
                    continue
                path = Path(target)
                try:
                    save_session(
                        path,
                        world=world,
                        prior_prose=prior_prose,
                    )
                except OSError as e:
                    _print_block(f"Save failed: {e}", kind="error")
                    continue
                _print_block(
                    f"Saved to {path}. Resume later with: autodnd --load {path}",
                    kind="status",
                )
                continue
            if line.startswith("/"):
                output = handle_slash(line, world)
                kind = "banner" if line == "/help" else "sidebar"
                _print_block(output, kind=kind)
            else:
                output = run_turn(world, line, prior_prose, rng)
                if _is_status_message(output):
                    _print_block(
                        output,
                        kind="error" if "error" in output.lower() else "status",
                    )
                else:
                    prior_prose.append(output)
                    _print_block(output, kind="prose")
        except SystemExit:
            return


if __name__ == "__main__":
    main()
