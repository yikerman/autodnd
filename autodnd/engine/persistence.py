"""Save/load WorldDB and the prose log.

WorldDB serializes via Pydantic to a single JSON file. The prose log — what
was rendered to the player, by cycle — is a separate ``.jsonl`` next to it
so reloads can display recent context without re-running cycles.

Per the design, WorldDB is the canonical source of truth. The prose log is a
rendering archive; it is not used to reconstruct world state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from autodnd.engine.world import World


@dataclass
class CycleProseEntry:
    """One cycle's player-facing output. Stored in ``<session>.prose.jsonl``."""

    trigger: str
    blocks: list[str]


def save_world(world: World, path: Path | str) -> None:
    """Write WorldDB to ``path`` as pretty-printed JSON. Overwrites."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(world.model_dump_json(indent=2), encoding="utf-8")


def load_world(path: Path | str) -> World:
    """Read WorldDB from ``path``. Raises if the file doesn't exist or is malformed."""
    p = Path(path)
    return World.model_validate_json(p.read_text(encoding="utf-8"))


def prose_log_path(world_path: Path | str) -> Path:
    """Resolve the prose log path for a given world save path."""
    p = Path(world_path)
    return p.with_suffix(p.suffix + ".prose.jsonl")


def append_prose(world_path: Path | str, entry: CycleProseEntry) -> None:
    """Append one cycle's prose to the prose log next to the world save."""
    log = prose_log_path(world_path)
    log.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {"trigger": entry.trigger, "blocks": entry.blocks},
        ensure_ascii=False,
    )
    with log.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_prose_log(world_path: Path | str) -> list[CycleProseEntry]:
    """Load every cycle's prose from the prose log. Missing log → empty list."""
    log = prose_log_path(world_path)
    if not log.exists():
        return []
    entries: list[CycleProseEntry] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        entries.append(
            CycleProseEntry(trigger=data["trigger"], blocks=list(data["blocks"]))
        )
    return entries
