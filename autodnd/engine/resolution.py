"""Resolution — the structured result of a deterministic rules call.

Every dice/check/attack/save returns a :class:`Resolution`. The Director
reads it and authors beats and a `WorldDelta` consistent with it; the
Director cannot author a success it didn't roll.
"""

from typing import Literal

from pydantic import BaseModel

ResolutionKind = Literal["raw_roll", "check", "attack", "save"]
Outcome = Literal["success", "failure", "critical_success", "critical_failure"]


class Resolution(BaseModel):
    kind: ResolutionKind
    outcome: Outcome | None = None  # None for raw_roll (no DC/target)
    roll: int  # the d20 face value (or sum for raw_roll)
    modifier: int = 0
    total: int  # roll + modifier
    target: int | None = None  # DC for check/save; AC for attack
    detail: str = ""  # human-readable summary
