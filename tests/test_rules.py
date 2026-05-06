"""Tests for engine.rules — dice, checks, attack, save, damage."""

import random

import pytest

from autodnd.engine.rules import (
    apply_damage,
    resolve_attack,
    resolve_check,
    resolve_save,
    roll,
)
from autodnd.engine.world import CharacterStats


class _FixedRng(random.Random):
    """A Random subclass that returns predetermined randint values in order."""

    def __init__(self, faces: list[int]) -> None:
        super().__init__()
        self._queue = list(faces)

    def randint(self, a: int, b: int) -> int:  # type: ignore[override]
        return self._queue.pop(0)


# ---------- roll() ----------


def test_roll_parses_simple_d20():
    rng = _FixedRng([7])
    assert roll("1d20", rng) == 7


def test_roll_implicit_count():
    rng = _FixedRng([13])
    assert roll("d20", rng) == 13


def test_roll_with_modifier():
    rng = _FixedRng([4, 6])
    assert roll("2d6+3", rng) == 4 + 6 + 3


def test_roll_with_negative_modifier():
    rng = _FixedRng([8])
    assert roll("1d8 - 2", rng) == 6


def test_roll_rejects_invalid_spec():
    with pytest.raises(ValueError):
        roll("not a roll", random.Random(0))


def test_roll_rejects_non_positive_dice():
    with pytest.raises(ValueError):
        roll("0d6", random.Random(0))


def test_roll_seeded_is_deterministic():
    a = roll("3d8+2", random.Random(42))
    b = roll("3d8+2", random.Random(42))
    assert a == b


# ---------- resolve_check ----------


def test_check_success_when_total_meets_dc():
    rng = _FixedRng([8])  # 8 + 2 = 10, DC 10 → success
    res = resolve_check("persuasion", dc=10, mods={"persuasion": 2}, rng=rng)
    assert res.outcome == "success"
    assert res.roll == 8
    assert res.modifier == 2
    assert res.total == 10
    assert res.target == 10


def test_check_failure_when_total_below_dc():
    rng = _FixedRng([5])  # 5 + 2 = 7, DC 15 → failure
    res = resolve_check("persuasion", dc=15, mods={"persuasion": 2}, rng=rng)
    assert res.outcome == "failure"


def test_check_critical_success_on_nat_20_regardless_of_dc():
    rng = _FixedRng([20])
    res = resolve_check("persuasion", dc=99, mods={"persuasion": 0}, rng=rng)
    assert res.outcome == "critical_success"
    assert res.roll == 20


def test_check_critical_failure_on_nat_1_regardless_of_mod():
    rng = _FixedRng([1])
    res = resolve_check("persuasion", dc=5, mods={"persuasion": 10}, rng=rng)
    assert res.outcome == "critical_failure"


def test_check_unknown_skill_uses_zero_mod():
    rng = _FixedRng([15])
    res = resolve_check("unknown_skill", dc=10, mods={}, rng=rng)
    assert res.modifier == 0
    assert res.outcome == "success"


# ---------- resolve_attack ----------


def test_attack_hit_when_total_meets_ac():
    rng = _FixedRng([10])  # 10 + 3 = 13 vs AC 13 → success (hit)
    res = resolve_attack(attack_mod=3, target_ac=13, rng=rng)
    assert res.outcome == "success"
    assert res.kind == "attack"


def test_attack_critical_hit_on_nat_20():
    rng = _FixedRng([20])
    res = resolve_attack(attack_mod=0, target_ac=99, rng=rng)
    assert res.outcome == "critical_success"


# ---------- resolve_save ----------


def test_save_success_meets_dc():
    rng = _FixedRng([12])
    res = resolve_save("dex", dc=14, mods={"dex": 2}, rng=rng)
    assert res.kind == "save"
    assert res.outcome == "success"
    assert res.total == 14


# ---------- apply_damage ----------


def test_apply_damage_reduces_hp():
    stats = CharacterStats(hp=24, ac=13)
    new_stats = apply_damage(stats, 6)
    assert new_stats.hp == 18
    assert stats.hp == 24  # original unchanged


def test_apply_damage_clamps_at_zero():
    stats = CharacterStats(hp=5, ac=13)
    assert apply_damage(stats, 100).hp == 0


def test_apply_damage_negative_heals():
    stats = CharacterStats(hp=10, ac=13)
    assert apply_damage(stats, -7).hp == 17


def test_apply_damage_preserves_other_fields():
    stats = CharacterStats(hp=10, ac=13, mods={"persuasion": 2})
    new_stats = apply_damage(stats, 4)
    assert new_stats.ac == 13
    assert new_stats.mods == {"persuasion": 2}
