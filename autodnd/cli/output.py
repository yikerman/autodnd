"""Terminal output: blocks with markdown rendering and a colored input prompt."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

_STYLE_BY_KIND = {
    "banner": "cyan",
    "error": "bright_red",
    "status": "bright_black",
    "prose": "none",
}

_OUT = Console()
_ERR = Console(stderr=True)
_RESET = "\x1b[0m"


def _rl_safe(seq: str) -> str:
    """Mark ANSI escapes as zero-width for readline prompt redraw math."""
    return f"\001{seq}\002"


def _prompt() -> str:
    if not sys.stdout.isatty():
        return "> "
    return _rl_safe("\x1b[1;32m") + "> " + _rl_safe(_RESET)


def print_block(text: str, *, kind: str = "prose") -> None:
    """Print a standalone output block with markdown rendering for prose."""
    style = _STYLE_BY_KIND.get(kind, "none")
    sys.stdout.write("\n")
    if kind in ("banner", "status", "error"):
        _OUT.print(Text(text.rstrip("\n"), style=style), soft_wrap=True)
    else:
        _OUT.print(Markdown(text, style=style, hyperlinks=False))
    sys.stdout.write("\n")


def print_status(text: str) -> None:
    _ERR.print(text, style="bright_black", markup=False, highlight=False)


def read_input() -> str | None:
    """Prompt the user. Returns None on EOF / Ctrl-C."""
    try:
        line = input(_prompt())
    except EOFError, KeyboardInterrupt:
        sys.stdout.write(f"{_RESET}\n")
        sys.stdout.flush()
        return None
    sys.stdout.write(_RESET)
    sys.stdout.flush()
    return line.strip()
