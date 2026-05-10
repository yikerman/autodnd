"""Per-session human-readable trace log for every Agent.run_sync call.

One ``trace/<timestamp>.log`` file per session. Each agent call is bracketed
by ``=== step N · agent · turn T ===`` and
``=== step N end · LATENCYms · IN→OUT tokens ===`` banners. Inside, one
labeled block per pydantic-ai message part: ``[system]``, ``[user]``,
``[tool]`` (call + return paired by ``tool_call_id``), ``[retry]``,
``[think]``, ``[text]``.

Enabled via the ``--trace`` CLI flag in :mod:`autodnd.cli.main`, which calls
:func:`init`. When ``init`` hasn't been called, :func:`start_run` and
:func:`end_run` no-op.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

_TRACE_FILE: Path | None = None
_STEP_COUNTER = 0


def init(directory: str | Path = "trace") -> Path:
    """Open a per-session trace file at ``<directory>/<timestamp>.log``,
    creating ``<directory>`` if missing. Resets the step counter."""
    global _TRACE_FILE, _STEP_COUNTER
    _STEP_COUNTER = 0
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    _TRACE_FILE = d / f"{timestamp}.log"
    _TRACE_FILE.touch()
    return _TRACE_FILE


def is_enabled() -> bool:
    return _TRACE_FILE is not None


def current_path() -> Path | None:
    return _TRACE_FILE


def start_run(
    *,
    agent: str,
    world_turn: int | None,
    extra: dict[str, Any] | None = None,
) -> int:
    """Increment the step counter, write the opening banner, return the step
    ID. Returns 0 when tracing is not initialized — pass that 0 back to
    :func:`end_run` and it'll skip too."""
    global _STEP_COUNTER
    if _TRACE_FILE is None:
        return 0
    _STEP_COUNTER += 1
    step = _STEP_COUNTER
    bits = [f"step {step}", agent, f"turn {world_turn}"]
    if extra:
        bits.extend(f"{k}={v!r}" for k, v in extra.items())
    _write("=== " + " · ".join(bits) + " ===\n")
    return step


def end_run(
    *,
    step: int,
    agent: str,
    world_turn: int | None,
    result: Any,
    latency_ms: float,
) -> None:
    """Walk ``result.new_messages()`` emitting one block per part, then the
    closing banner with latency + token counts. No-op when tracing not
    initialized or ``step == 0``."""
    if _TRACE_FILE is None or step == 0:
        return
    for tag_line, body in _walk(result.new_messages()):
        _write_block(tag_line, body)

    usage = result.usage()
    in_tok = getattr(usage, "input_tokens", 0) or 0
    out_tok = getattr(usage, "output_tokens", 0) or 0
    bits = [
        f"step {step} end",
        f"{round(latency_ms)}ms",
        f"{in_tok}→{out_tok} tokens",
    ]
    _write("\n=== " + " · ".join(bits) + " ===\n\n")


# ---------- internals ----------


def _walk(messages: Iterable[ModelMessage]) -> Iterator[tuple[str, str]]:
    """Yield (tag_line, body) for each loggable part. Pairs each ToolCallPart
    with its ToolReturnPart (by tool_call_id) into one ``[tool]`` block."""
    returns_by_id: dict[str, ToolReturnPart] = {}
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, ToolReturnPart):
                    returns_by_id[part.tool_call_id] = part

    paired: set[str] = set()
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, SystemPromptPart):
                    yield "[system]", part.content
                elif isinstance(part, UserPromptPart):
                    yield "[user]", _stringify(part.content)
                elif isinstance(part, RetryPromptPart):
                    head = part.tool_name or "(no tool)"
                    yield f"[retry] {head}", _stringify(part.content)
                elif isinstance(part, ToolReturnPart):
                    if part.tool_call_id in paired:
                        continue
                    # orphan return: matching call wasn't in new_messages
                    yield (
                        f"[tool-return] {part.tool_name}",
                        f"ret: {_stringify(part.content)}",
                    )
        elif isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    ret = returns_by_id.get(part.tool_call_id)
                    if ret is not None:
                        paired.add(part.tool_call_id)
                    yield (
                        f"[tool] {part.tool_name}",
                        f"args: {_format_args(part.args)}\n"
                        f"ret:  {_stringify(ret.content) if ret else '(no return)'}",
                    )
                elif isinstance(part, ThinkingPart):
                    if part.content.strip():
                        yield "[think]", part.content
                elif isinstance(part, TextPart):
                    if part.content.strip():
                        yield "[text]", part.content


def _format_args(args: str | dict[str, Any] | None) -> str:
    if args is None:
        return "(none)"
    if isinstance(args, str):
        return args
    return json.dumps(args, ensure_ascii=False, default=str)


def _stringify(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)


def _write_block(tag_line: str, body: str) -> None:
    if not body.strip():
        _write(f"\n{tag_line}\n")
        return
    indented = "\n".join("  " + line for line in body.splitlines())
    _write(f"\n{tag_line}\n{indented}\n")


def _write(text: str) -> None:
    if _TRACE_FILE is None:
        return
    with _TRACE_FILE.open("a", encoding="utf-8") as f:
        f.write(text)
