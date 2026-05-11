"""Resolution — the structured outcome of a dice resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ResolutionKind = Literal["check", "attack", "save"]
Outcome = Literal["success", "failure", "critical_success", "critical_failure"]


@dataclass(frozen=True)
class Resolution:
    kind: ResolutionKind
    outcome: Outcome
    roll: int  # the d20
    modifier: int  # bonus added to the roll
    total: int  # roll + modifier
    target: int  # DC or AC
    detail: str  # human-readable summary
