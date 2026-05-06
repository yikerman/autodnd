"""REPL entry point for AutoDND.

Per turn: free-text input → Director (omniscient + dice tools) → validator/apply →
Narrator (no world access; restyles beats) → prose. Slash commands route to
the Sidebar (read-only Q&A over the player's own state).

On validator failure, the Director gets one retry with the errors appended;
a second failure aborts the turn with a brief error message.
"""

from __future__ import annotations

import argparse
import random
import readline  # noqa: F401  # imported for its side effect: arrow-key line editing in input()
import sys

from blessed import Terminal
from dotenv import load_dotenv

from autodnd.engine.delta import (
    BootstrapDirective,
    apply_bootstrap,
    apply_world_delta,
)
from autodnd.engine.world import CharacterStats, PlayerState, WorldModel
from autodnd.fixtures import inn_scene_bootstrap
from autodnd.llm import tracing
from autodnd.llm.director import run_bootstrap_director, run_turn_director
from autodnd.llm.narrator import run_narrator
from autodnd.llm.sidebar import run_sidebar

T = Terminal()

BANNER = """\
AutoDND — solo one-shot DM. Type your action, or:
  /hp       — show your HP
  /log      — show recent events
  /inv      — show inventory
  /ask Q    — free-form sidebar question
  /help     — this banner
  /quit     — exit
"""

SLASH_FAST_QUERIES = {
    "/hp": "What's my HP, AC, and ability scores?",
    "/log": (
        "List the events I've experienced so far in chronological order, one line each. "
        "Story timeline only — do NOT include HP, stats, modifiers, location, or inventory."
    ),
    "/inv": "What's in my inventory?",
}


def _empty_world() -> WorldModel:
    return WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)),
        turn=-1,
    )


def initialize_session(
    *, demo_scene: bool, rng: random.Random
) -> tuple[WorldModel, BootstrapDirective]:
    world = _empty_world()
    directive = inn_scene_bootstrap() if demo_scene else run_bootstrap_director(rng=rng)
    errors = apply_bootstrap(world, directive)
    if errors:
        msg = "Bootstrap rejected:\n" + "\n".join(
            f"  - {e.code} at {e.field_path}: {e.detail}" for e in errors
        )
        raise SystemExit(msg)
    return world, directive


def run_turn(
    world: WorldModel,
    player_input: str,
    prior_prose: str,
    narration_history: list[str],
    rng: random.Random,
) -> str:
    directive = run_turn_director(world, player_input, prior_prose, rng)
    errors = apply_world_delta(world, directive.world_delta)
    if errors:
        retry_input = (
            f"{player_input}\n\n"
            "## Your previous directive was rejected\n\n"
            + "\n".join(f"- {e.code} at `{e.field_path}`: {e.detail}" for e in errors)
            + "\n\nRevise and emit a valid directive."
        )
        directive = run_turn_director(world, retry_input, prior_prose, rng)
        errors = apply_world_delta(world, directive.world_delta)
        if errors:
            return "[DM error: directive invalid after retry; please rephrase]"

    if not directive.beats:
        return "[the DM pauses, awaiting clearer intent]"

    return run_narrator(directive.beats, narration_history, world_turn=world.turn)


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
            query = rest.strip() or "What's my current status?"
            return run_sidebar(
                world.player, query, items=world.items, world_turn=world.turn
            )
        case _:
            return f"Unknown command: {cmd}. Try /help."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="autodnd", description=__doc__)
    parser.add_argument(
        "--demo-scene",
        action="store_true",
        help="use the hardcoded Crow's Foot Inn fixture instead of LLM bootstrap",
    )
    return parser.parse_args(argv)


def _is_status_message(text: str) -> bool:
    """True for the bracket-prefixed engine messages run_turn returns when there's
    nothing to narrate — used to style them differently from real prose."""
    return text.startswith("[") and text.endswith("]") and "\n" not in text


def _print_block(text: str, *, kind: str = "prose") -> None:
    """Print a standalone output block with appropriate color."""
    if kind == "banner":
        styled = T.cyan(text)
    elif kind == "sidebar":
        styled = T.yellow(text)
    elif kind == "error":
        styled = T.bright_red(text)
    elif kind == "status":
        styled = T.bright_black(text)
    else:  # prose
        styled = text
    print()
    print(styled)
    print()


def _rl_safe(seq: str) -> str:
    """Wrap an ANSI escape so readline counts it as zero-width when computing
    cursor positions during line editing / history recall."""
    return f"\001{seq}\002"


# Prompt = bold-green "> "; readline-safe escape transition into bold-cyan so
# the user's keystrokes echo in cyan until we reset on Enter.
_PROMPT = _rl_safe(str(T.bold_green)) + "> " + _rl_safe(str(T.bold_cyan))


def _read_input() -> str | None:
    """Prompt the user. Returns None on EOF / Ctrl-C. Arrow keys + history come
    free from `readline` having been imported at module top."""
    try:
        line = input(_PROMPT)
    except EOFError, KeyboardInterrupt:
        sys.stdout.write(str(T.normal))
        sys.stdout.flush()
        print()
        return None
    sys.stdout.write(str(T.normal))
    sys.stdout.flush()
    return line.strip()


def main() -> None:
    load_dotenv()
    args = parse_args()
    rng = random.Random()

    trace_path = tracing.init()

    _print_block(BANNER, kind="banner")
    if trace_path:
        print(T.bright_black(f"Trace log: {trace_path}"), file=sys.stderr)
    print(T.bright_black("Initializing world…"), file=sys.stderr)
    world, directive = initialize_session(demo_scene=args.demo_scene, rng=rng)
    opening_prose = run_narrator(directive.opening_beats, [], world_turn=world.turn)
    narration_history: list[str] = [opening_prose]
    prior_prose = opening_prose

    _print_block(opening_prose, kind="prose")

    while True:
        line = _read_input()
        if line is None:
            return
        if not line:
            continue
        try:
            if line.startswith("/"):
                output = handle_slash(line, world)
                kind = "banner" if line in {"/help"} else "sidebar"
                _print_block(output, kind=kind)
            else:
                output = run_turn(world, line, prior_prose, narration_history, rng)
                if _is_status_message(output):
                    _print_block(
                        output,
                        kind="error" if "error" in output.lower() else "status",
                    )
                else:
                    prior_prose = output
                    narration_history.append(output)
                    _print_block(output, kind="prose")
        except SystemExit:
            return


if __name__ == "__main__":
    main()
