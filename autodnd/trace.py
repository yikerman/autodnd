"""Per-session human-readable trace log for every LLM call.

One ``trace/<timestamp>.log`` per session. Each call is bracketed by a banner
and a closing banner with latency and token counts. Inside, one labeled block
per pydantic-ai message part: ``[system]``, ``[user]``, ``[tool]``, ``[text]``,
``[think]``, ``[retry]``.

Enable via :func:`init`. When ``init`` hasn't been called, :func:`trace_run`
is a no-op — wrap every agent run regardless.
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
_STEP = 0


def init(directory: str | Path = "trace") -> Path:
    """Open a per-session trace file. Returns the path."""
    global _TRACE_FILE, _STEP
    _STEP = 0
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


def trace_run(
    agent_name: str,
    result: Any,
    latency_ms: float,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one trace block for an agent run. No-op when tracing is disabled."""
    global _STEP
    if _TRACE_FILE is None:
        return
    _STEP += 1
    bits = [f"step {_STEP}", agent_name]
    if extra:
        bits.extend(f"{k}={v!r}" for k, v in extra.items())
    _write("=== " + " · ".join(bits) + " ===\n")

    for tag, body in _walk(result.new_messages()):
        _write_block(tag, body)

    usage = result.usage()
    in_tok = getattr(usage, "input_tokens", 0) or 0
    out_tok = getattr(usage, "output_tokens", 0) or 0
    closing = [
        f"step {_STEP} end",
        f"{round(latency_ms)}ms",
        f"{in_tok}→{out_tok} tokens",
    ]
    _write("\n=== " + " · ".join(closing) + " ===\n\n")


# ---------- internals ----------


def _walk(messages: Iterable[ModelMessage]) -> Iterator[tuple[str, str]]:
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


def _format_args(args: Any) -> str:
    if args is None:
        return "(none)"
    if isinstance(args, str):
        return args
    return json.dumps(args, ensure_ascii=False, default=str)


def _stringify(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)


def _write_block(tag: str, body: str) -> None:
    if not body.strip():
        _write(f"\n{tag}\n")
        return
    indented = "\n".join("  " + line for line in body.splitlines())
    _write(f"\n{tag}\n{indented}\n")


def _write(text: str) -> None:
    if _TRACE_FILE is None:
        return
    with _TRACE_FILE.open("a", encoding="utf-8") as f:
        f.write(text)
