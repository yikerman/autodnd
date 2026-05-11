"""Perception helpers and the defensive name-leak check.

The arbiter composes these with dice tools to decide who-perceived-what
when minting history records. Engine helpers are deterministic; the judgment
of *whether* a perception roll is needed remains the arbiter's NL call.
"""

from __future__ import annotations

import re

from autodnd.engine.world import PLAYER, Character, World


def who_is_in(world: World, location_id: str) -> list[str]:
    """Participant ids currently at ``location_id``, sorted for determinism."""
    ids = [cid for cid, c in world.characters.items() if c.location_id == location_id]
    if world.player is not None and world.player.location_id == location_id:
        ids.append(PLAYER)
    return sorted(ids)


def passive_perception(character: Character) -> int:
    """5e-style passive perception: 10 + perception skill modifier (0 if unset)."""
    return 10 + character.skill_mods.get("perception", 0)


def names_leaked_in_description(
    description: str, participants: list[str], world: World
) -> list[str]:
    """Return character ids whose name or id is mentioned in ``description`` but
    are NOT in ``participants``.

    A non-empty result is a leak warning: a record describing what character X
    did/said should have X in participants. Used as a defensive check after
    every ``mint_history`` call.

    Word-boundary regex on both id and name. False positives are possible for
    very common names but acceptable for a warning.
    """
    leaked: list[str] = []
    participants_set = set(participants)
    if (
        world.player is not None
        and PLAYER not in participants_set
        and re.search(
            rf"\b{re.escape(world.player.name)}\b", description, re.IGNORECASE
        )
    ):
        leaked.append(PLAYER)
    for cid, char in world.characters.items():
        if cid in participants_set:
            continue
        for token in (cid, char.name):
            if re.search(rf"\b{re.escape(token)}\b", description, re.IGNORECASE):
                leaked.append(cid)
                break
    return leaked
