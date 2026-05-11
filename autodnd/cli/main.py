"""REPL entry point.

Each free-text input triggers an arbiter cycle. The arbiter conducts the
moment, invoking characters and the narrator in dramatic order; their prose
blocks are concatenated in invocation order and printed to the player.

Slash commands:
- ``/help`` — this banner
- ``/hp``, ``/log``, ``/inv`` — sidebar shortcuts
- ``/ask <question>`` — free-form sidebar query
- ``/save <path>`` — snapshot WorldDB + prose log to ``path``
- ``/quit`` — exit

Initial world: ``--demo-scene vale`` or ``--demo-scene waymeet`` loads a
hardcoded fixture; ``--load <path>`` resumes a saved session; no flag
falls through to the one-shot bootstrapper.
"""

from __future__ import annotations

import argparse
import random
import readline  # noqa: F401  # imported for side effect: arrow-key line editing
from pathlib import Path

from dotenv import load_dotenv

from autodnd import trace as trace_module
from autodnd.cli.output import print_block, print_status, read_input
from autodnd.engine.persistence import (
    CycleProseEntry,
    append_prose,
    load_world,
    read_prose_log,
    save_world,
)
from autodnd.engine.world import World
from autodnd.fixtures import vale_inn, waymeet_scene
from autodnd.llm.arbiter import build_arbiter_agent, run_cycle
from autodnd.llm.bootstrapper import build_bootstrapper_agent, run_bootstrapper
from autodnd.llm.character import build_character_agent
from autodnd.llm.client import model_from_env
from autodnd.llm.narrator import build_narrator_agent
from autodnd.llm.sidebar import SLASH_QUERIES, build_sidebar_agent, run_sidebar

BANNER = """\
AutoDND — fictional world simulator. Type your action, or:
  /hp        — show HP, AC, abilities
  /log       — show recent memory
  /inv       — show inventory and gold
  /ask Q     — free-form sidebar question
  /save FILE — snapshot to FILE (resume with --load FILE)
  /help      — this banner
  /quit      — exit
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="autodnd", description=__doc__)
    start = parser.add_mutually_exclusive_group()
    start.add_argument(
        "--demo-scene",
        choices=["vale", "waymeet"],
        help="seed a hardcoded fixture instead of running the bootstrapper",
    )
    start.add_argument(
        "--load",
        metavar="FILE",
        type=Path,
        help="resume a session previously written by /save",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="write a human-readable trace to trace/<timestamp>.log",
    )
    return parser.parse_args(argv)


def _seed_demo(world: World, name: str) -> None:
    if name == "vale":
        vale_inn(world)
    elif name == "waymeet":
        waymeet_scene(world)
    else:
        raise ValueError(f"unknown demo scene: {name}")


def main() -> None:
    load_dotenv()
    args = parse_args()
    rng = random.Random()

    trace_path = trace_module.init() if args.trace else None
    print_block(BANNER, kind="banner")
    if trace_path is not None:
        print_status(f"Trace log: {trace_path}")

    print_status("Building agents…")
    model = model_from_env()
    arbiter = build_arbiter_agent(model)
    character = build_character_agent(model)
    narrator = build_narrator_agent(model)
    sidebar = build_sidebar_agent(model)

    world = World()
    save_path: Path | None = None
    needs_opening = False
    in_game = False

    if args.load is not None:
        print_status(f"Loading session from {args.load}…")
        try:
            world = load_world(args.load)
        except (OSError, ValueError) as e:
            print_block(f"Load failed: {e}", kind="error")
            return
        save_path = args.load
        # Replay last cycle's prose so the player has context.
        entries = read_prose_log(args.load)
        if entries:
            print_status(f"(resuming after {len(entries)} cycles)")
            for block in entries[-1].blocks:
                print_block(block, kind="prose")
        in_game = True
    elif args.demo_scene is not None:
        print_status(f"Seeding demo scene: {args.demo_scene}")
        _seed_demo(world, args.demo_scene)
        needs_opening = True
    else:
        print_status("No fixture or save selected — entering bootstrapper interview.")
        print_status("Type your replies; an empty line aborts.")
        bootstrapper = build_bootstrapper_agent(model)
        ready = run_bootstrapper(
            bootstrapper,
            world,
            read_input=read_input,
            on_agent_message=lambda s: print_block(s, kind="prose"),
        )
        if not ready:
            print_block("(bootstrapper did not finish — exiting)", kind="error")
            return
        needs_opening = True

    if needs_opening:
        try:
            deps = run_cycle(
                arbiter, character, narrator, world, "[opening scene]", rng=rng
            )
        except Exception as e:  # noqa: BLE001
            print_block(f"Opening cycle aborted: {e}", kind="error")
            return
        for prose in deps.prose_blocks:
            print_block(prose, kind="prose")
        for warning in deps.leak_warnings:
            print_status(warning)
        in_game = True

    while True:
        line = read_input()
        if line is None:
            return
        if not line:
            continue
        if line.startswith("/"):
            should_quit, save_path = _handle_slash(
                line, world, sidebar, save_path, in_game=in_game
            )
            if should_quit:
                return
            continue

        try:
            deps = run_cycle(arbiter, character, narrator, world, line, rng=rng)
        except Exception as e:  # noqa: BLE001
            print_block(f"Cycle aborted: {e}", kind="error")
            continue

        for prose in deps.prose_blocks:
            print_block(prose, kind="prose")
        for warning in deps.leak_warnings:
            print_status(warning)
        if save_path is not None:
            append_prose(
                save_path,
                CycleProseEntry(trigger=line, blocks=list(deps.prose_blocks)),
            )


def _handle_slash(
    line: str,
    world: World,
    sidebar,  # Agent[None, str]
    save_path: Path | None,
    *,
    in_game: bool,
) -> tuple[bool, Path | None]:
    """Returns (should_quit, updated_save_path)."""
    cmd, _, rest = line.partition(" ")
    match cmd:
        case "/help":
            print_block(BANNER, kind="banner")
        case "/quit" | "/exit":
            return True, save_path
        case "/save":
            if not in_game:
                print_block(
                    "Cannot save — the opening scene hasn't started yet.",
                    kind="error",
                )
                return False, save_path
            target = rest.strip()
            if not target:
                print_block("Usage: /save <file>", kind="error")
                return False, save_path
            path = Path(target)
            try:
                save_world(world, path)
            except OSError as e:
                print_block(f"Save failed: {e}", kind="error")
                return False, save_path
            print_status(f"Saved to {path}. Resume with: autodnd --load {path}")
            save_path = path
        case "/hp" | "/log" | "/inv":
            question = SLASH_QUERIES[cmd]
            answer = run_sidebar(sidebar, world, question)
            print_block(answer, kind="prose")
        case "/ask":
            question = rest.strip()
            if not question:
                print_block("Usage: /ask <question>", kind="error")
                return False, save_path
            answer = run_sidebar(sidebar, world, question)
            print_block(answer, kind="prose")
        case _:
            print_block(f"Unknown command: {cmd}. Try /help.", kind="error")
    return False, save_path


if __name__ == "__main__":
    main()
