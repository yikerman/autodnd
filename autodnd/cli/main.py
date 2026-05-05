"""REPL entry point for AutoDND.

Reads player input line-by-line. Slash-commands route to the (future) Sidebar;
free text routes to the (future) Narrator. Both are stubbed for now so the
loop itself is exercisable end-to-end.
"""

from __future__ import annotations

from dataclasses import dataclass

from dotenv import load_dotenv


BANNER = """\
AutoDND — solo one-shot DM. Type your action, or:
  /hp       — show your HP
  /log      — show recent events
  /inv      — show inventory
  /help     — this banner
  /quit     — exit
"""


@dataclass
class ReplContext:
    """Holds session-scoped handles. Engine/LLM agents will land here."""

    turn: int = 0


def handle_slash(cmd: str, ctx: ReplContext) -> str:
    name, _, _rest = cmd.partition(" ")
    match name:
        case "/help":
            return BANNER
        case "/hp" | "/log" | "/inv":
            return f"[sidebar stub] {name} not wired yet"
        case "/quit" | "/exit":
            raise SystemExit(0)
        case _:
            return f"Unknown command: {name}. Try /help."


def handle_narration(text: str, ctx: ReplContext) -> str:
    ctx.turn += 1
    return f"[narrator stub, turn {ctx.turn}] you said: {text!r}"


def main() -> None:
    load_dotenv()
    ctx = ReplContext()
    print(BANNER)
    while True:
        try:
            line = input("> ").strip()
        except EOFError, KeyboardInterrupt:
            print()
            return
        if not line:
            continue
        try:
            out = (
                handle_slash(line, ctx)
                if line.startswith("/")
                else handle_narration(line, ctx)
            )
        except SystemExit:
            return
        print(out)


if __name__ == "__main__":
    main()
