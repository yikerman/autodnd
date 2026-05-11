"""Firewall verification against the Waymeet scene from ``test.json``.

These are structural assertions, not LLM behavior tests. They prove the
information channels we expect to exist actually exist, and the ones we
expect to be closed are closed.

If any of these fail, the legacy Director's failure modes can recur — a
character's LLM prompt would contain information their character has no
canon reason to know.
"""

from __future__ import annotations

from autodnd.engine.render import (
    render_arbiter,
    render_for_character,
    render_for_player,
)
from autodnd.engine.world import World
from autodnd.fixtures import waymeet_scene


def _world() -> World:
    w = World()
    waymeet_scene(w)
    return w


# ---------- Fox's restricted archive knowledge ----------


def test_player_render_includes_archive_readings() -> None:
    """Fox knows what he read. His own view (sidebar) reflects it."""
    rendered = render_for_player(_world())
    assert "Lirien" in rendered
    assert "mountain is not stone" in rendered


def test_brona_render_excludes_player_archive_readings() -> None:
    """Brona has no canon reason to know about Fox's classified archive readings."""
    _system, user = render_for_character(_world(), "brona")
    assert "Lirien" not in user
    assert "mountain is not stone" not in user
    assert "restricted archive" not in user.lower()
    assert "substance resonance" not in user.lower()


def test_thrag_render_excludes_player_archive_readings() -> None:
    _system, user = render_for_character(_world(), "thrag")
    assert "Lirien" not in user
    assert "mountain is not stone" not in user
    assert "substance resonance" not in user.lower()


def test_torgal_render_includes_lirien_because_she_was_his_daughter() -> None:
    """Torgal DOES know Lirien — she was his daughter. His render reflects it."""
    _system, user = render_for_character(_world(), "old_torgal")
    assert "Lirien" in user


def test_torgal_render_excludes_fox_archive_readings() -> None:
    """Torgal knows Lirien, but does NOT know Fox read the archive log.
    Fox has not told him yet (in the fixture state)."""
    _system, user = render_for_character(_world(), "old_torgal")
    # The specific log entry text only exists in Fox's private record.
    assert "mountain is not stone" not in user
    # 'substance resonance' is in Fox's reading record too.
    assert "substance resonance" not in user.lower()


# ---------- Silan's surveillance brief ----------


def test_brona_render_excludes_silan_whisperer_brief() -> None:
    """Brona has no idea Silan is a Whisperer."""
    _system, user = render_for_character(_world(), "brona")
    assert "Whisperer" not in user
    assert "intelligence service" not in user.lower()
    # The cover story bit ("scholar of human customs") could legitimately
    # appear in Silan's public description, but the brief itself shouldn't.
    assert "ensure he does not speak" not in user


def test_thrag_render_excludes_silan_brief() -> None:
    _system, user = render_for_character(_world(), "thrag")
    assert "Whisperer" not in user


def test_player_render_excludes_silan_brief() -> None:
    """Fox can see Silan in the crowd but doesn't know who she is."""
    rendered = render_for_player(_world())
    assert "Whisperer" not in rendered
    assert "thin blade in her sleeve" not in rendered


def test_silan_render_includes_her_brief() -> None:
    _system, user = render_for_character(_world(), "silan")
    assert "Whisperer" in user
    assert "intelligence service" in user.lower()


# ---------- Brona's cellar evidence + dwarf ultimatum ----------


def test_player_render_excludes_brona_cellar_evidence() -> None:
    rendered = render_for_player(_world())
    assert "loose floorboard" not in rendered
    assert "price-fixing" not in rendered


def test_thrag_render_excludes_brona_dwarf_ultimatum() -> None:
    _system, user = render_for_character(_world(), "thrag")
    assert "emergency vote" not in user
    assert "12 days" not in user


def test_brona_render_includes_her_own_secrets() -> None:
    _system, user = render_for_character(_world(), "brona")
    assert "loose floorboard" in user
    assert "emergency vote" in user


# ---------- Torgal's warm stone + field log fragment ----------


def test_player_render_excludes_torgals_warm_stone() -> None:
    rendered = render_for_player(_world())
    assert "warm to the touch" not in rendered


def test_thrag_render_excludes_torgals_field_log() -> None:
    _system, user = render_for_character(_world(), "thrag")
    assert "inner chamber" not in user
    assert "field log" not in user.lower()


def test_torgal_render_includes_warm_stone() -> None:
    _system, user = render_for_character(_world(), "old_torgal")
    assert "smooth dark stone" in user
    assert "inner chamber" in user


# ---------- The recent in-scene shared record IS visible to all present ----------


def test_thrag_render_includes_recent_in_scene_arrival() -> None:
    """Thrag's arrival was witnessed by player, brona, and thrag — all see it."""
    _system, user = render_for_character(_world(), "thrag")
    assert "This seat taken?" in user


def test_brona_render_includes_thrags_arrival() -> None:
    _system, user = render_for_character(_world(), "brona")
    assert "This seat taken?" in user


def test_player_render_includes_thrags_arrival() -> None:
    rendered = render_for_player(_world())
    assert "This seat taken?" in rendered


# ---------- Arbiter sees everything ----------


def test_arbiter_render_includes_all_private_secrets() -> None:
    """The arbiter is god-mode: every spoilable fact must be in its prompt."""
    _system, user = render_arbiter(_world(), "trigger")
    assert "Lirien" in user
    assert "Whisperer" in user
    assert "loose floorboard" in user
    assert "smooth dark stone" in user


# ---------- Mira's recruitment intent ----------


def test_mira_render_includes_recruitment_intent() -> None:
    _system, user = render_for_character(_world(), "mira_lawless")
    assert "extra set of eyes" in user


def test_player_render_excludes_mira_recruitment() -> None:
    rendered = render_for_player(_world())
    assert "extra set of eyes" not in rendered


# ---------- Kastor's awareness of his own rigging ----------


def test_kastor_render_includes_his_awareness() -> None:
    _system, user = render_for_character(_world(), "kastor_vel")
    assert "price-adjustment clauses" in user


def test_brona_render_excludes_kastor_awareness() -> None:
    """Brona suspects, but doesn't have explicit Kastor-knows-it-is-rigged record."""
    _system, user = render_for_character(_world(), "brona")
    assert "Kastor Vel knows" not in user
