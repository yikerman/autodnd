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
    # Parallel to prior_prose: the player input that produced each prose entry.
    # Index 0 is always "" because the opening prose has no preceding input.
    player_prompts: list[str]


def save_session(
    path: Path,
    *,
    world: WorldModel,
    prior_prose: list[str],
    player_prompts: list[str],
) -> None:
    snap = SessionSnapshot(
        world=world, prior_prose=prior_prose, player_prompts=player_prompts
    )
    path.write_text(snap.model_dump_json(indent=2), encoding="utf-8")


def load_session(path: Path) -> SessionSnapshot:
    return SessionSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
