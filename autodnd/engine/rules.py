"""Dice mechanics. Deterministic given an injected RNG.

Free-form rolls return ints; skill checks / attacks / saves return `Resolution`.
The arbiter calls these tools and embeds the outcome into a minted history record.
"""

from __future__ import annotations

import random
import re

from autodnd.engine.resolution import Outcome, Resolution

_DICE_SPEC = re.compile(r"\s*(\d+)d(\d+)\s*([+-]\s*\d+)?\s*")


def roll(spec: str, rng: random.Random) -> int:
    """Sum dice from a spec like '2d6+3' or '1d20'.

    Raises ``ValueError`` on malformed input.
    """
    match = _DICE_SPEC.fullmatch(spec)
    if not match:
        raise ValueError(f"invalid dice spec: {spec!r}")
    n = int(match.group(1))
    sides = int(match.group(2))
    if n < 1 or sides < 2:
        raise ValueError(f"invalid dice spec: {spec!r}")
    total = sum(rng.randint(1, sides) for _ in range(n))
    mod = match.group(3)
    if mod is not None:
        total += int(mod.replace(" ", ""))
    return total


def _outcome(d20: int, succeeded: bool) -> Outcome:
    if d20 == 20:
        return "critical_success"
    if d20 == 1:
        return "critical_failure"
    return "success" if succeeded else "failure"


def resolve_check(
    *, skill: str, dc: int, modifier: int, rng: random.Random
) -> Resolution:
    d20 = rng.randint(1, 20)
    total = d20 + modifier
    outcome = _outcome(d20, total >= dc)
    detail = (
        f"{skill} check: 1d20({d20}) {modifier:+d} = {total} vs DC {dc} → {outcome}"
    )
    return Resolution(
        kind="check",
        outcome=outcome,
        roll=d20,
        modifier=modifier,
        total=total,
        target=dc,
        detail=detail,
    )


def resolve_attack(
    *, attack_mod: int, target_ac: int, rng: random.Random
) -> Resolution:
    d20 = rng.randint(1, 20)
    total = d20 + attack_mod
    outcome = _outcome(d20, total >= target_ac)
    detail = (
        f"attack: 1d20({d20}) {attack_mod:+d} = {total} vs AC {target_ac} → {outcome}"
    )
    return Resolution(
        kind="attack",
        outcome=outcome,
        roll=d20,
        modifier=attack_mod,
        total=total,
        target=target_ac,
        detail=detail,
    )


def resolve_save(
    *, save_kind: str, dc: int, modifier: int, rng: random.Random
) -> Resolution:
    d20 = rng.randint(1, 20)
    total = d20 + modifier
    outcome = _outcome(d20, total >= dc)
    detail = (
        f"{save_kind} save: 1d20({d20}) {modifier:+d} = {total} vs DC {dc} → {outcome}"
    )
    return Resolution(
        kind="save",
        outcome=outcome,
        roll=d20,
        modifier=modifier,
        total=total,
        target=dc,
        detail=detail,
    )
