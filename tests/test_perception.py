"""Perception helpers and the defensive name-leak check."""

from __future__ import annotations

from autodnd.engine.perception import (
    names_leaked_in_description,
    passive_perception,
    who_is_in,
)
from autodnd.engine.world import Character, World
from autodnd.fixtures import vale_inn


def test_who_is_in_sorted() -> None:
    w = World()
    vale_inn(w)
    assert who_is_in(w, "vale_inn") == ["brona", "player"]
    assert who_is_in(w, "nowhere") == []


def test_passive_perception_default_ten() -> None:
    c = Character(
        id="x",
        name="x",
        description="x",
        location_id="inn",
        hp=1,
        hp_max=1,
        ac=10,
    )
    assert passive_perception(c) == 10


def test_passive_perception_with_skill_mod() -> None:
    c = Character(
        id="x",
        name="x",
        description="x",
        location_id="inn",
        hp=1,
        hp_max=1,
        ac=10,
        skill_mods={"perception": 5},
    )
    assert passive_perception(c) == 15


def test_names_leaked_when_character_named_outside_participants() -> None:
    w = World()
    vale_inn(w)
    leaked = names_leaked_in_description(
        "Brona scowled at the player.", participants=["player"], world=w
    )
    assert "brona" in leaked


def test_names_leaked_by_id() -> None:
    w = World()
    vale_inn(w)
    leaked = names_leaked_in_description(
        "brona stood up suddenly.", participants=[], world=w
    )
    assert "brona" in leaked


def test_names_leaked_word_boundary() -> None:
    """Substrings without word boundaries don't trigger."""
    w = World()
    vale_inn(w)
    # "Foxglove" contains "Fox" (player's name) but is a different word.
    leaked = names_leaked_in_description(
        "The foxglove bloomed.", participants=[], world=w
    )
    assert "player" not in leaked


def test_names_leaked_skips_participants() -> None:
    """Names that ARE in participants are not flagged."""
    w = World()
    vale_inn(w)
    leaked = names_leaked_in_description(
        "Brona scowled at the player.",
        participants=["brona", "player"],
        world=w,
    )
    assert leaked == []


def test_names_leaked_case_insensitive() -> None:
    w = World()
    vale_inn(w)
    leaked = names_leaked_in_description(
        "BRONA's voice rumbled.", participants=[], world=w
    )
    assert "brona" in leaked
