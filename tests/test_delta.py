"""Closed mutation API: validation paths and happy paths.

Each delta should return ``"ok: ..."`` on success and ``"error: ..."`` on
failure with the world unchanged.
"""

from __future__ import annotations

from autodnd.engine.delta import (
    advance_narrative_time,
    create_character,
    create_item,
    create_location,
    create_player,
    mint_history,
    move_player,
    transfer_item,
    update_item_description,
    update_player_stats,
)
from autodnd.engine.world import AtLocation, HeldBy, World


def _seeded() -> World:
    w = World()
    create_location(w, location_id="inn", name="Inn", description="warm")
    create_location(w, location_id="road", name="Road", description="dusty")
    create_player(
        w,
        name="Fox",
        description="scout",
        location_id="inn",
        hp=10,
        hp_max=10,
        ac=12,
    )
    create_character(
        w,
        character_id="brona",
        name="Brona",
        description="tavern-keeper",
        location_id="inn",
        hp=8,
        hp_max=8,
        ac=10,
    )
    return w


# ---------- create_location ----------


def test_create_location_happy() -> None:
    w = World()
    assert create_location(
        w, location_id="inn", name="Inn", description="warm"
    ).startswith("ok:")
    assert "inn" in w.locations


def test_create_location_duplicate_rejected() -> None:
    w = _seeded()
    result = create_location(w, location_id="inn", name="Inn2", description="x")
    assert result.startswith("error:")
    assert w.locations["inn"].name == "Inn"  # unchanged


# ---------- create_character ----------


def test_create_character_unknown_location_rejected() -> None:
    w = _seeded()
    result = create_character(
        w,
        character_id="ghost",
        name="g",
        description="x",
        location_id="nowhere",
        hp=1,
        hp_max=1,
        ac=10,
    )
    assert result.startswith("error:")
    assert "ghost" not in w.characters


def test_create_character_invalid_hp_rejected() -> None:
    w = _seeded()
    result = create_character(
        w,
        character_id="x",
        name="x",
        description="x",
        location_id="inn",
        hp=15,
        hp_max=10,
        ac=10,
    )
    assert result.startswith("error:")
    assert "x" not in w.characters


def test_create_character_negative_gold_rejected() -> None:
    w = _seeded()
    result = create_character(
        w,
        character_id="x",
        name="x",
        description="x",
        location_id="inn",
        hp=1,
        hp_max=1,
        ac=10,
        gold=-1,
    )
    assert result.startswith("error:")


# ---------- create_item ----------


def test_create_item_at_unknown_location_rejected() -> None:
    w = _seeded()
    result = create_item(
        w,
        item_id="rock",
        name="rock",
        description="a rock",
        position=AtLocation(location_id="nowhere"),
    )
    assert result.startswith("error:")


def test_create_item_held_by_unknown_character_rejected() -> None:
    w = _seeded()
    result = create_item(
        w,
        item_id="rock",
        name="rock",
        description="x",
        position=HeldBy(character_id="ghost"),
    )
    assert result.startswith("error:")


def test_create_item_happy() -> None:
    w = _seeded()
    result = create_item(
        w,
        item_id="sword",
        name="sword",
        description="sharp",
        position=HeldBy(character_id="player"),
        effects={"attack": 4},
    )
    assert result.startswith("ok:")
    assert w.items["sword"].effects == {"attack": 4}


# ---------- mint_history ----------


def test_mint_history_assigns_monotonic_t() -> None:
    w = _seeded()
    assert mint_history(w, participants=["player"], description="a").startswith("ok:")
    assert mint_history(w, participants=["brona"], description="b").startswith("ok:")
    assert [r.t for r in w.history] == [0, 1]
    assert w.next_t == 2


def test_mint_history_unknown_participant_rejected() -> None:
    w = _seeded()
    result = mint_history(w, participants=["ghost"], description="x")
    assert result.startswith("error:")
    assert w.history == []


def test_mint_history_default_narrative_time() -> None:
    w = _seeded()
    advance_narrative_time(w, new_time="Day 2, dusk")
    mint_history(w, participants=["player"], description="x")
    assert w.history[0].narrative_time == "Day 2, dusk"


def test_mint_history_empty_participants_ok() -> None:
    """Cosmic happenings nobody knows are valid."""
    w = _seeded()
    result = mint_history(
        w,
        participants=[],
        description="The dragon stirred beneath the mountain.",
    )
    assert result.startswith("ok:")
    assert w.history[0].participants == []


# ---------- move ----------


def test_move_happy() -> None:
    w = _seeded()
    assert move_player(w, location_id="road").startswith("ok:")
    assert w.player is not None
    assert w.player.location_id == "road"


def test_move_unknown_location_rejected() -> None:
    w = _seeded()
    assert move_player(w, location_id="nowhere").startswith("error:")
    assert w.player is not None
    assert w.player.location_id == "inn"


# ---------- update_stats ----------


def test_update_stats_partial_change() -> None:
    w = _seeded()
    update_player_stats(w, hp=5, gold=10)
    assert w.player is not None
    assert w.player.hp == 5
    assert w.player.gold == 10
    assert w.player.ac == 12  # unchanged


def test_update_stats_clamps_when_lowering_hp_max() -> None:
    w = _seeded()
    # player has hp=10, hp_max=10
    update_player_stats(w, hp_max=5)
    assert w.player is not None
    assert w.player.hp_max == 5
    assert w.player.hp == 5  # clamped


def test_update_stats_rejects_hp_above_max() -> None:
    w = _seeded()
    result = update_player_stats(w, hp=999)
    assert result.startswith("error:")
    assert w.player is not None
    assert w.player.hp == 10


def test_update_stats_rejects_negative() -> None:
    w = _seeded()
    assert update_player_stats(w, gold=-1).startswith("error:")
    assert update_player_stats(w, hp=-1).startswith("error:")
    assert update_player_stats(w, ac=-1).startswith("error:")


# ---------- transfer_item ----------


def test_transfer_item_happy() -> None:
    w = _seeded()
    create_item(
        w,
        item_id="sword",
        name="sword",
        description="x",
        position=HeldBy(character_id="player"),
    )
    assert transfer_item(
        w, item_id="sword", to=HeldBy(character_id="brona")
    ).startswith("ok:")
    assert isinstance(w.items["sword"].position, HeldBy)
    assert w.items["sword"].position.character_id == "brona"


def test_transfer_item_to_unknown_rejected() -> None:
    w = _seeded()
    create_item(
        w,
        item_id="sword",
        name="sword",
        description="x",
        position=HeldBy(character_id="player"),
    )
    assert transfer_item(
        w, item_id="sword", to=HeldBy(character_id="ghost")
    ).startswith("error:")


# ---------- update_item_description ----------


def test_update_item_description_happy() -> None:
    w = _seeded()
    create_item(
        w,
        item_id="sword",
        name="sword",
        description="plain",
        position=HeldBy(character_id="player"),
    )
    update_item_description(w, item_id="sword", description="now carved with FOX")
    assert w.items["sword"].description == "now carved with FOX"


# ---------- advance_narrative_time ----------


def test_advance_narrative_time_happy() -> None:
    w = _seeded()
    advance_narrative_time(w, new_time="Day 2, dawn")
    assert w.narrative_time == "Day 2, dawn"


def test_advance_narrative_time_empty_rejected() -> None:
    w = _seeded()
    result = advance_narrative_time(w, new_time="   ")
    assert result.startswith("error:")
    assert w.narrative_time == "Day 1, dawn"
