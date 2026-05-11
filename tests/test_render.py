"""Renderers: determinism + the per-character firewall.

The firewall is the load-bearing test of this layer: ``render_for_character``
must NEVER include a history record where the character is not in
``participants``. Any leakage here propagates to the LLM prompt.
"""

from __future__ import annotations

from autodnd.engine.delta import mint_history
from autodnd.engine.render import (
    render_arbiter,
    render_for_character,
    render_for_narrator,
    render_for_player,
)
from autodnd.engine.world import World
from autodnd.fixtures import vale_inn


def _world() -> World:
    w = World()
    vale_inn(w)
    return w


# ---------- Determinism ----------


def test_render_for_player_deterministic() -> None:
    w = _world()
    assert render_for_player(w) == render_for_player(w)


def test_render_for_character_deterministic() -> None:
    w = _world()
    assert render_for_character(w, "brona") == render_for_character(w, "brona")


def test_render_for_narrator_deterministic() -> None:
    w = _world()
    assert render_for_narrator(w) == render_for_narrator(w)


def test_render_arbiter_deterministic() -> None:
    w = _world()
    assert render_arbiter(w, "trigger") == render_arbiter(w, "trigger")


# ---------- Firewall ----------


def test_brona_render_omits_player_private_thought() -> None:
    """The fixture has a player-only thought. Brona's render must not contain it."""
    w = _world()
    _system, user = render_for_character(w, "brona")
    assert "thought about the road ahead" not in user
    assert "restless" not in user


def test_player_render_omits_brona_private_resolution() -> None:
    """Brona's private resolution must not appear in player-facing renders."""
    w = _world()
    rendered = render_for_player(w)
    assert "send word to Korel" not in rendered
    assert "fits the description" not in rendered


def test_brona_render_includes_her_own_resolution() -> None:
    """Brona DOES see her own private resolution."""
    w = _world()
    _system, user = render_for_character(w, "brona")
    assert "send word to Korel" in user


def test_player_render_includes_player_thought() -> None:
    w = _world()
    rendered = render_for_player(w)
    assert "thought about the road ahead" in rendered


def test_render_for_character_excludes_records_where_char_not_in_participants() -> None:
    """Adversarial: mint a third-party private record, ensure neither sees it."""
    w = _world()
    # Add a third character so we have someone uninvolved.
    from autodnd.engine.delta import create_character

    create_character(
        w,
        character_id="thrag",
        name="Thrag",
        description="An orc scout, scarred and watchful.",
        location_id="vale_inn",
        hp=12,
        hp_max=12,
        ac=13,
    )
    # Mint a record only Thrag knows.
    mint_history(
        w,
        participants=["thrag"],
        description="Thrag noticed the player's posture and recognized the gait of an elf-trained scout.",
        location_id="vale_inn",
    )
    # Brona must not see it.
    _system, brona_view = render_for_character(w, "brona")
    assert "elf-trained" not in brona_view
    assert "recognized" not in brona_view
    # Player must not see it.
    player_view = render_for_player(w)
    assert "elf-trained" not in player_view
    # Thrag DOES see it.
    _system, thrag_view = render_for_character(w, "thrag")
    assert "elf-trained" in thrag_view


# ---------- Other-character descriptions in scene are public-safe ----------


def test_brona_render_includes_player_public_description() -> None:
    """Descriptions are public-only by commitment, so safe to include in scene."""
    w = _world()
    _system, user = render_for_character(w, "brona")
    # Player's description should appear in "Present in this scene".
    assert "wandering scout" in user


# ---------- Arbiter sees everything ----------


def test_arbiter_sees_all_history() -> None:
    w = _world()
    _system, user = render_arbiter(w, "trigger")
    assert "send word to Korel" in user  # Brona's private resolution
    assert "thought about the road ahead" in user  # Player's private thought


# ---------- Narrator scope ----------


def test_narrator_sees_player_perceived_history_only() -> None:
    w = _world()
    _system, user = render_for_narrator(w)
    # Brona's resolution: player not in participants → not in narrator view.
    assert "send word to Korel" not in user
