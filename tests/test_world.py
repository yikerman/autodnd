"""Atoms instantiate, defaults are sensible, History is immutable."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from autodnd.engine.world import (
    Abilities,
    AtLocation,
    Character,
    HeldBy,
    History,
    Item,
    Location,
    World,
)


def test_world_defaults_are_empty() -> None:
    w = World()
    assert w.locations == {}
    assert w.characters == {}
    assert w.items == {}
    assert w.history == []
    assert w.next_t == 0
    assert w.narrative_time == "Day 1, dawn"


def test_abilities_default_to_ten() -> None:
    a = Abilities()
    assert a.strength == 10
    assert a.dexterity == 10
    assert a.constitution == 10
    assert a.intelligence == 10
    assert a.wisdom == 10
    assert a.charisma == 10


def test_character_holds_skill_mods_and_inventory_unstored() -> None:
    c = Character(
        id="player",
        name="Fox",
        description="A scout.",
        location_id="inn",
        hp=10,
        hp_max=10,
        ac=12,
        skill_mods={"perception": 3},
    )
    assert c.skill_mods == {"perception": 3}
    assert c.gold == 0


def test_item_position_is_discriminated_union() -> None:
    held = Item(
        id="sword",
        name="sword",
        description="x",
        position=HeldBy(character_id="player"),
    )
    assert isinstance(held.position, HeldBy)
    assert held.position.character_id == "player"

    on_floor = Item(
        id="rock",
        name="rock",
        description="x",
        position=AtLocation(location_id="cave"),
    )
    assert isinstance(on_floor.position, AtLocation)
    assert on_floor.position.location_id == "cave"


def test_history_is_frozen() -> None:
    h = History(
        id="h0",
        t=0,
        narrative_time="Day 1, dawn",
        participants=["player"],
        description="x",
    )
    with pytest.raises(ValidationError):
        h.description = "tampered"  # type: ignore[misc]


def test_location_minimal() -> None:
    Location(id="x", name="X", description="x")
