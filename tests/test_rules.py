"""Dice mechanics: deterministic given an injected RNG."""

from __future__ import annotations

import random

import pytest

from autodnd.engine.rules import resolve_attack, resolve_check, resolve_save, roll


def test_roll_simple() -> None:
    rng = random.Random(0)
    # 2d6+3 with seed 0; just assert range.
    result = roll("2d6+3", rng)
    assert 5 <= result <= 15


def test_roll_d20() -> None:
    rng = random.Random(0)
    result = roll("1d20", rng)
    assert 1 <= result <= 20


def test_roll_negative_modifier() -> None:
    rng = random.Random(0)
    result = roll("1d4-2", rng)
    assert -1 <= result <= 2


def test_roll_invalid_spec() -> None:
    rng = random.Random(0)
    with pytest.raises(ValueError):
        roll("garbage", rng)
    with pytest.raises(ValueError):
        roll("0d6", rng)
    with pytest.raises(ValueError):
        roll("1d1", rng)


def test_check_succeeds_when_total_meets_dc() -> None:
    rng = random.Random(0)
    # Force d20=15 by pre-seeding; assert outcome matches arithmetic.
    res = resolve_check(skill="perception", dc=10, modifier=3, rng=rng)
    assert res.kind == "check"
    assert 1 <= res.roll <= 20
    assert res.total == res.roll + 3
    if res.roll == 20:
        assert res.outcome == "critical_success"
    elif res.roll == 1:
        assert res.outcome == "critical_failure"
    elif res.total >= 10:
        assert res.outcome == "success"
    else:
        assert res.outcome == "failure"


def test_attack_returns_resolution() -> None:
    rng = random.Random(0)
    res = resolve_attack(attack_mod=5, target_ac=14, rng=rng)
    assert res.kind == "attack"
    assert res.target == 14
    assert res.modifier == 5


def test_save_returns_resolution() -> None:
    rng = random.Random(0)
    res = resolve_save(save_kind="wisdom", dc=12, modifier=1, rng=rng)
    assert res.kind == "save"
    assert res.target == 12


def test_dice_deterministic_with_seed() -> None:
    """Same seed → same result."""
    rng_a = random.Random(42)
    rng_b = random.Random(42)
    assert roll("3d8+2", rng_a) == roll("3d8+2", rng_b)
    res_a = resolve_check(skill="x", dc=10, modifier=0, rng=rng_a)
    res_b = resolve_check(skill="x", dc=10, modifier=0, rng=rng_b)
    assert res_a == res_b


def test_critical_success_on_natural_20() -> None:
    # Find a seed that rolls 20 first.
    for seed in range(200):
        rng = random.Random(seed)
        res = resolve_check(skill="x", dc=99, modifier=0, rng=rng)
        if res.roll == 20:
            assert res.outcome == "critical_success"
            return
    pytest.fail("no natural 20 in 200 seeds — RNG is suspicious")


def test_critical_failure_on_natural_1() -> None:
    for seed in range(200):
        rng = random.Random(seed)
        res = resolve_check(skill="x", dc=0, modifier=100, rng=rng)
        if res.roll == 1:
            assert res.outcome == "critical_failure"
            return
    pytest.fail("no natural 1 in 200 seeds — RNG is suspicious")
