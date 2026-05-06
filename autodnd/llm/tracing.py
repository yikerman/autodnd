"""Per-session JSONL trace log for every Agent.run_sync call.

Captures the full conversation (system + user + tool calls + tool returns +
final response) plus the parsed output, world turn, agent name, and latency.
One line per agent call. View with ``jq`` or any text editor.

Disabled when ``AUTODND_TRACE`` is set to ``0``/``false``/``no``.

Usage from the REPL::

    from autodnd.llm.tracing import init
    path = init()
    if path:
        print(f"Trace log: {path}")

Usage from a ``run_*`` wrapper::

    start = time.monotonic()
    result = agent.run_sync(prompt, deps=...)
    log_agent_call(
        agent="turn_director",
        world_turn=world.turn,
        result=result,
        latency_ms=(time.monotonic() - start) * 1000,
    )
    return result.output
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_core import to_jsonable_python

_TRACE_FILE: Path | None = None
_STEP_COUNTER = 0
_DISABLED_VALUES = {"0", "false", "no", "off", ""}


def init(directory: str | Path = "traces") -> Path | None:
    """Open a per-session trace file. Returns the path, or ``None`` if disabled
    via ``AUTODND_TRACE``. Subsequent calls reset the counter and re-open."""
    global _TRACE_FILE, _STEP_COUNTER
    _STEP_COUNTER = 0
    if os.getenv("AUTODND_TRACE", "1").strip().lower() in _DISABLED_VALUES:
        _TRACE_FILE = None
        return None
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    _TRACE_FILE = d / f"{timestamp}.jsonl"
    _TRACE_FILE.touch()
    return _TRACE_FILE


def is_enabled() -> bool:
    return _TRACE_FILE is not None


def current_path() -> Path | None:
    return _TRACE_FILE


def log_agent_call(
    *,
    agent: str,
    world_turn: int | None,
    result: Any,
    latency_ms: float,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one trace record. ``result`` is a PydanticAI ``AgentRunResult``-like
    object exposing ``.output`` and ``.all_messages()``. No-op if tracing disabled."""
    global _STEP_COUNTER
    if _TRACE_FILE is None:
        return
    _STEP_COUNTER += 1

    output_repr = to_jsonable_python(result.output)
    messages = to_jsonable_python(result.all_messages())

    record: dict[str, Any] = {
        "step": _STEP_COUNTER,
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "world_turn": world_turn,
        "latency_ms": round(latency_ms, 2),
        "output": output_repr,
        "messages": messages,
    }
    if extra:
        record.update(extra)

    with _TRACE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def reset_for_tests() -> None:
    """Reset module state. Tests use this to ensure isolation."""
    global _TRACE_FILE, _STEP_COUNTER
    _TRACE_FILE = None
    _STEP_COUNTER = 0
