"""Hardcoded inn-scene fixture used by tests and the demo REPL path.

:func:`seed_inn_scene` mints the worked example from ``plan/example.md``:
Mara is a courier from Vellor carrying spymaster Korel's sealed letter to
Olwen across the Sken border. She's stopping at the Crow's Foot Inn for the
night. The innkeeper Hadrian is secretly a bandit-crew informant. The seed
mints all canon up to her arrival at dusk; play begins from there.

Mutates the supplied (empty, ``turn == -1``) :class:`WorldModel` in place
and returns the opening prose ready for printing.
"""

from autodnd.engine.delta import (
    ValidationError,
    apply_add_player_item,
    apply_append_player_log,
    apply_create_character,
    apply_create_item,
    apply_create_location,
    apply_create_thread,
    apply_mint_event,
    apply_move_player,
    apply_update_player_stats,
)
from autodnd.engine.world import CharacterStats, WorldModel

_OPENING_PROSE = (
    "Two summers since Heavyfall, and the loss still rides on your shoulders "
    "like a second cloak. You took the courier wages because Tomas's debts "
    "wouldn't pay themselves — and now, three weeks after Spymaster Korel "
    'pressed a sealed letter into your hand and murmured "discretion, no copies," '
    "you've come within a day's ride of the Sken border. The Crow's Foot Inn "
    "meets you at dusk: smoky common room, four trestle tables, a stewpot "
    "muttering over the coals. The innkeeper — broad-faced, ruddy, fifties — "
    "waves you in with a generous spoon.\n\n"
    '"Settle in, traveller."'
)

# (id, name, description)
_LOCATIONS: tuple[tuple[str, str, str], ...] = (
    (
        "vellor_capital",
        "Vellor capital",
        "Walled city on the river. Seat of Vellor's court and the spymaster's office.",
    ),
    (
        "north_road",
        "the north road",
        "Main route from Vellor capital to the Sken border. Quiet lately; some traffic to the southern fork.",
    ),
    (
        "inn",
        "Crow's Foot Inn",
        "Roadside inn at dusk. Smoky common room, four trestle tables, stewpot over coals. The candle-on-the-outer-windowsill is the local bandit-crew's signal.",
    ),
    (
        "heavyfall_pass",
        "Heavyfall Pass",
        "Mountain pass on the disputed Vellor–Sken border. Site of the 1047 skirmish.",
    ),
    ("sken_border_town", "Mawley", "Sken-side market town. Olwen's residence."),
    (
        "bandit_camp",
        "bandit camp",
        "Half a mile north of the inn, behind a stand of pines. Six bandits under Grell.",
    ),
)

# (id, name, parent_id, description)
_THREADS: tuple[tuple[str, str, str | None, str], ...] = (
    (
        "vellor_sken_tensions",
        "Vellor–Sken tensions",
        None,
        "Vellor and Sken have an uneasy peace since the Treaty of Three Rivers (1043). Border skirmishes recur. Sken troop movements have been observed lately.",
    ),
    (
        "courier_mission",
        "Mara's courier mission",
        "vellor_sken_tensions",
        "Deliver Korel's sealed letter to Olwen in Mawley within seven days. Discretion paramount; no copies.",
    ),
    (
        "inn_night",
        "Night at Crow's Foot",
        "courier_mission",
        "Mara stops at Crow's Foot Inn. If she reveals wealth, Hadrian likely tips the bandits — ambush at dawn on the north road. If unobtrusive, she passes.",
    ),
)

# (id, name, location_id, hp, ac, description)
_CHARACTERS: tuple[tuple[str, str, str, int, int, str], ...] = (
    (
        "hadrian",
        "Hadrian",
        "inn",
        14,
        11,
        "Ruddy innkeeper in his fifties, talkative, generous with stew. Informant for Grell's bandit crew; sizes up travellers and signals an ambush if any are worth robbing.",
    ),
    (
        "korel",
        "Spymaster Korel",
        "vellor_capital",
        18,
        12,
        "Vellor's spymaster. Sent Mara north with the sealed letter; the letter contains coded intelligence on Sken troop movements.",
    ),
    (
        "olwen",
        "Olwen",
        "sken_border_town",
        16,
        12,
        "Vellor agent embedded in Sken. Awaits Korel's letter.",
    ),
    (
        "mara_father",
        "Tomas (deceased)",
        "heavyfall_pass",
        0,
        0,
        "Mara's father. Killed at Heavyfall Pass in the 1047 skirmish.",
    ),
    (
        "grell",
        "Grell",
        "bandit_camp",
        22,
        14,
        "Bandit chief. Awaits Hadrian's signal candle.",
    ),
)

# (id, name, description, effects)
_ITEMS: tuple[tuple[str, str, str, dict[str, int]], ...] = (
    (
        "sealed_letter",
        "sealed letter",
        "Wax-sealed parchment, addressed to Olwen. Contents: coded Sken troop intelligence (Mara doesn't know).",
        {},
    ),
    (
        "gold_pouch",
        "gold pouch",
        "Mara's purse. Heavier than she'd like — three weeks' courier wages plus expense money. Contains 50 gp.",
        {},
    ),
    ("shortsword", "shortsword", "Plain blade, well-kept.", {}),
    (
        "persuasion_skill",
        "persuasion (skill)",
        "Trained ability — Mara can read a room.",
        {"persuasion": 2},
    ),
)

# (id, narrative_time, location_id, participants, description, thread_id)
_EVENTS: tuple[tuple[str, str, str, list[str], str, str], ...] = (
    (
        "e_treaty",
        "year 1043, spring",
        "vellor_capital",
        [],
        "Vellor and Sken signed the Treaty of Three Rivers, ending open war.",
        "vellor_sken_tensions",
    ),
    (
        "e_skirmish",
        "year 1047, summer",
        "heavyfall_pass",
        ["mara_father"],
        "Border skirmish at Heavyfall Pass. Mara's father Tomas killed.",
        "vellor_sken_tensions",
    ),
    (
        "e_recruitment",
        "year 1048, autumn",
        "vellor_capital",
        [],
        "Mara took up courier work to pay off Tomas's debts.",
        "courier_mission",
    ),
    (
        "e_briefing",
        "year 1049, three weeks ago",
        "vellor_capital",
        ["korel"],
        "Korel handed Mara the sealed letter. Said: 'Discretion. No copies.' Did not disclose contents.",
        "courier_mission",
    ),
    (
        "e_departure",
        "year 1049, yesterday morning",
        "vellor_capital",
        [],
        "Mara departed the capital northbound.",
        "courier_mission",
    ),
    (
        "e_arrival",
        "today, dusk",
        "inn",
        ["hadrian"],
        "Mara arrived at Crow's Foot Inn at dusk. Hadrian welcomed her with stew. Mara has not yet shown wealth.",
        "inn_night",
    ),
)

_PLAYER_ITEMS = ("sealed_letter", "gold_pouch", "shortsword", "persuasion_skill")

_PLAYER_LOG = (
    "Two summers ago, your father Tomas died in the skirmish at Heavyfall Pass. You wear the loss like a second cloak.",
    "You took courier work after his death — his debts wouldn't pay themselves.",
    "Three weeks ago, Spymaster Korel handed you a sealed letter for one Olwen, in Mawley. 'Discretion,' he said. 'No copies.' He didn't say what was in it.",
    "You left the capital yesterday morning.",
    "You reached the Crow's Foot Inn at dusk. The innkeeper, Hadrian, welcomed you in with stew.",
)


def _check(err: ValidationError | None) -> None:
    if err is not None:
        raise RuntimeError(
            f"inn_scene seed failed: {err.code} at {err.field_path}: {err.detail}"
        )


def seed_inn_scene(world: WorldModel) -> str:
    """Seed ``world`` with the worked-example bootstrap state. Returns opening prose."""
    assert world.turn == -1, "seed_inn_scene requires a fresh world (turn=-1)"

    for id, name, desc in _LOCATIONS:
        _check(apply_create_location(world, id=id, name=name, description=desc))
    for id, name, parent_id, desc in _THREADS:
        _check(
            apply_create_thread(
                world, id=id, name=name, parent_id=parent_id, description=desc
            )
        )
    for id, name, loc, hp, ac, desc in _CHARACTERS:
        _check(
            apply_create_character(
                world,
                id=id,
                name=name,
                location_id=loc,
                stats=CharacterStats(hp=hp, hp_max=hp, ac=ac),
                description=desc,
            )
        )
    for id, name, desc, effects in _ITEMS:
        _check(
            apply_create_item(
                world, id=id, name=name, description=desc, effects=effects
            )
        )
    for id, narrative_time, loc, parts, desc, thread in _EVENTS:
        _check(
            apply_mint_event(
                world,
                id=id,
                narrative_time=narrative_time,
                location_id=loc,
                participants=parts,
                description=desc,
                thread_id=thread,
            )
        )

    _check(apply_move_player(world, location_id="inn"))
    _check(
        apply_update_player_stats(world, stats=CharacterStats(hp=24, hp_max=24, ac=13))
    )
    for item_id in _PLAYER_ITEMS:
        _check(apply_add_player_item(world, item_id=item_id))
    for entry in _PLAYER_LOG:
        _check(apply_append_player_log(world, text=entry))

    world.turn = 0
    return _OPENING_PROSE
