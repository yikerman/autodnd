"""Deterministic dice / check / attack / save / damage primitives.

RNG is injected — every function takes ``rng: random.Random`` so tests can
seed for repeatability and the Director's tool calls produce the exact
results the validator and Narrator will see.

Lightweight 5e:
- d20 + modifier vs DC for checks and saves
- d20 + attack_mod vs target AC for attacks
- nat 20 = critical_success, nat 1 = critical_failure (both on the d20 face)
- damage clamps HP at 0 (no negative HP)

Spell mechanics, action economy, and RAW initiative are out of scope.
"""

import random
import re

from autodnd.engine.resolution import Resolution
from autodnd.engine.world import CharacterStats

_DICE_SPEC = re.compile(r"^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$", re.IGNORECASE)


def roll(spec: str, rng: random.Random) -> int:
    """Parse a dice spec like ``"1d20"``, ``"d20"``, ``"2d6+3"`` and return the sum."""
    match = _DICE_SPEC.match(spec)
    if not match:
        raise ValueError(f"invalid dice spec: {spec!r}")
    count_str, sides_str, modifier_str = match.groups()
    count = int(count_str) if count_str else 1
    sides = int(sides_str)
    if count <= 0 or sides <= 0:
        raise ValueError(f"non-positive dice count/sides in {spec!r}")
    modifier = int(modifier_str.replace(" ", "")) if modifier_str else 0
    total = sum(rng.randint(1, sides) for _ in range(count)) + modifier
    return total


def _d20_outcome(face: int, total: int, target: int) -> str:
    if face == 20:
        return "critical_success"
    if face == 1:
        return "critical_failure"
    return "success" if total >= target else "failure"


def resolve_check(
    skill: str, dc: int, mods: dict[str, int], rng: random.Random
) -> Resolution:
    """A skill check: d20 + ``mods.get(skill, 0)`` vs DC."""
    modifier = mods.get(skill, 0)
    face = rng.randint(1, 20)
    total = face + modifier
    outcome = _d20_outcome(face, total, dc)
    return Resolution(
        kind="check",
        outcome=outcome,  # type: ignore[arg-type]
        roll=face,
        modifier=modifier,
        total=total,
        target=dc,
        detail=f"{skill} check: d20={face} {modifier:+d} = {total} vs DC {dc} → {outcome}",
    )


def resolve_attack(attack_mod: int, target_ac: int, rng: random.Random) -> Resolution:
    """A weapon attack roll: d20 + attack_mod vs target AC."""
    face = rng.randint(1, 20)
    total = face + attack_mod
    outcome = _d20_outcome(face, total, target_ac)
    return Resolution(
        kind="attack",
        outcome=outcome,  # type: ignore[arg-type]
        roll=face,
        modifier=attack_mod,
        total=total,
        target=target_ac,
        detail=f"attack: d20={face} {attack_mod:+d} = {total} vs AC {target_ac} → {outcome}",
    )


def resolve_save(
    save_kind: str, dc: int, mods: dict[str, int], rng: random.Random
) -> Resolution:
    """A saving throw: d20 + ``mods.get(save_kind, 0)`` vs DC."""
    modifier = mods.get(save_kind, 0)
    face = rng.randint(1, 20)
    total = face + modifier
    outcome = _d20_outcome(face, total, dc)
    return Resolution(
        kind="save",
        outcome=outcome,  # type: ignore[arg-type]
        roll=face,
        modifier=modifier,
        total=total,
        target=dc,
        detail=f"{save_kind} save: d20={face} {modifier:+d} = {total} vs DC {dc} → {outcome}",
    )


def apply_damage(stats: CharacterStats, damage: int) -> CharacterStats:
    """Return a new ``CharacterStats`` with HP reduced by ``damage``, clamped at 0.

    Negative damage = healing; MVP doesn't track max HP, so no upper clamp.
    """
    new_hp = max(stats.hp - damage, 0)
    return stats.model_copy(update={"hp": new_hp})
