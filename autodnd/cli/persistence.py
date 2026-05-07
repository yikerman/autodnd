"""JSON snapshot of a REPL session: world + accumulated prose.

The pair matches what ``cli.main`` carries in locals between turns; restoring
it lets ``--load`` resume mid-session without re-bootstrapping the Director.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from autodnd.engine.world import WorldModel


class SessionSnapshot(BaseModel):
    world: WorldModel
    prior_prose: list[str]


def save_session(
    path: Path,
    *,
    world: WorldModel,
    prior_prose: list[str],
) -> None:
    snap = SessionSnapshot(world=world, prior_prose=prior_prose)
    path.write_text(snap.model_dump_json(indent=2), encoding="utf-8")


def load_session(path: Path) -> SessionSnapshot:
    return SessionSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
