"""Hardcoded bootstrap fixtures used by tests and the REPL before the
Director is wired up.

:func:`inn_scene_bootstrap` is the worked example from ``plan/example.md``:
Mara is a courier from Vellor carrying spymaster Korel's sealed letter to
Olwen across the Sken border. She's stopping at the Crow's Foot Inn for the
night. The innkeeper Hadrian is secretly a bandit-crew informant. Bootstrap
mints all canon up to her arrival at dusk; play begins from there.
"""

from autodnd.engine.delta import Beat, BootstrapDirective, EntitiesToCreate
from autodnd.engine.world import (
    Character,
    CharacterStats,
    Event,
    Item,
    KnowledgeEntry,
    Location,
    PlayerState,
    Thread,
)


def inn_scene_bootstrap() -> BootstrapDirective:
    return BootstrapDirective(
        entities=EntitiesToCreate(
            locations=[
                Location(
                    id="vellor_capital",
                    name="Vellor capital",
                    description=(
                        "Walled city on the river. Seat of Vellor's court "
                        "and the spymaster's office."
                    ),
                ),
                Location(
                    id="north_road",
                    name="the north road",
                    description=(
                        "Main route from Vellor capital to the Sken border. "
                        "Quiet lately; some traffic to the southern fork."
                    ),
                ),
                Location(
                    id="inn",
                    name="Crow's Foot Inn",
                    description=(
                        "Roadside inn at dusk. Smoky common room, four trestle tables, "
                        "stewpot over coals. The candle-on-the-outer-windowsill is the "
                        "local bandit-crew's signal."
                    ),
                ),
                Location(
                    id="heavyfall_pass",
                    name="Heavyfall Pass",
                    description=(
                        "Mountain pass on the disputed Vellor–Sken border. "
                        "Site of the 1047 skirmish."
                    ),
                ),
                Location(
                    id="sken_border_town",
                    name="Mawley",
                    description="Sken-side market town. Olwen's residence.",
                ),
                Location(
                    id="bandit_camp",
                    name="bandit camp",
                    description=(
                        "Half a mile north of the inn, behind a stand of pines. "
                        "Six bandits under Grell."
                    ),
                ),
            ],
            characters=[
                Character(
                    id="hadrian",
                    name="Hadrian",
                    location_id="inn",
                    stats=CharacterStats(
                        hp=14,
                        hp_max=14,
                        ac=11,
                        strength=11,
                        dexterity=10,
                        constitution=12,
                        intelligence=11,
                        wisdom=12,
                        charisma=14,
                    ),
                    description=(
                        "Ruddy innkeeper in his fifties, talkative, generous with stew. "
                        "Informant for Grell's bandit crew; sizes up travellers and "
                        "signals an ambush if any are worth robbing."
                    ),
                ),
                Character(
                    id="korel",
                    name="Spymaster Korel",
                    location_id="vellor_capital",
                    stats=CharacterStats(
                        hp=18,
                        hp_max=18,
                        ac=12,
                        strength=10,
                        dexterity=12,
                        constitution=11,
                        intelligence=16,
                        wisdom=14,
                        charisma=15,
                    ),
                    description=(
                        "Vellor's spymaster. Sent Mara north with the sealed letter; "
                        "the letter contains coded intelligence on Sken troop movements."
                    ),
                ),
                Character(
                    id="olwen",
                    name="Olwen",
                    location_id="sken_border_town",
                    stats=CharacterStats(
                        hp=16,
                        hp_max=16,
                        ac=12,
                        strength=10,
                        dexterity=13,
                        constitution=12,
                        intelligence=14,
                        wisdom=13,
                        charisma=14,
                    ),
                    description="Vellor agent embedded in Sken. Awaits Korel's letter.",
                ),
                Character(
                    id="mara_father",
                    name="Tomas (deceased)",
                    location_id="heavyfall_pass",
                    stats=CharacterStats(hp=0, hp_max=0, ac=0),
                    description="Mara's father. Killed at Heavyfall Pass in the 1047 skirmish.",
                ),
                Character(
                    id="grell",
                    name="Grell",
                    location_id="bandit_camp",
                    stats=CharacterStats(
                        hp=22,
                        hp_max=22,
                        ac=14,
                        strength=15,
                        dexterity=12,
                        constitution=14,
                        intelligence=10,
                        wisdom=11,
                        charisma=10,
                    ),
                    description="Bandit chief. Awaits Hadrian's signal candle.",
                ),
            ],
            items=[
                Item(
                    id="sealed_letter",
                    name="sealed letter",
                    description=(
                        "Wax-sealed parchment, addressed to Olwen. Contents: coded "
                        "Sken troop intelligence (Mara doesn't know)."
                    ),
                ),
                Item(
                    id="gold_pouch",
                    name="gold pouch",
                    description=(
                        "Mara's purse. Heavier than she'd like — three weeks' courier "
                        "wages plus expense money. Contains 50 gp."
                    ),
                ),
                Item(
                    id="shortsword",
                    name="shortsword",
                    description="Plain blade, well-kept.",
                ),
                Item(
                    id="persuasion_skill",
                    name="persuasion (skill)",
                    description="Trained ability — Mara can read a room.",
                    effects={"persuasion": 2},
                ),
            ],
        ),
        threads=[
            Thread(
                id="vellor_sken_tensions",
                parent_id=None,
                name="Vellor–Sken tensions",
                description=(
                    "Vellor and Sken have an uneasy peace since the Treaty of Three Rivers (1043). "
                    "Border skirmishes recur. Sken troop movements have been observed lately."
                ),
            ),
            Thread(
                id="courier_mission",
                parent_id="vellor_sken_tensions",
                name="Mara's courier mission",
                description=(
                    "Deliver Korel's sealed letter to Olwen in Mawley within seven days. "
                    "Discretion paramount; no copies."
                ),
            ),
            Thread(
                id="inn_night",
                parent_id="courier_mission",
                name="Night at Crow's Foot",
                description=(
                    "Mara stops at Crow's Foot Inn. If she reveals wealth, Hadrian likely "
                    "tips the bandits — ambush at dawn on the north road. If unobtrusive, "
                    "she passes."
                ),
            ),
        ],
        backstory_events=[
            Event(
                id="e_treaty",
                t=0,
                narrative_time="year 1043, spring",
                location_id="vellor_capital",
                participants=[],
                description="Vellor and Sken signed the Treaty of Three Rivers, ending open war.",
                thread_id="vellor_sken_tensions",
            ),
            Event(
                id="e_skirmish",
                t=1,
                narrative_time="year 1047, summer",
                location_id="heavyfall_pass",
                participants=["mara_father"],
                description="Border skirmish at Heavyfall Pass. Mara's father Tomas killed.",
                thread_id="vellor_sken_tensions",
            ),
            Event(
                id="e_recruitment",
                t=2,
                narrative_time="year 1048, autumn",
                location_id="vellor_capital",
                participants=[],
                description="Mara took up courier work to pay off Tomas's debts.",
                thread_id="courier_mission",
            ),
            Event(
                id="e_briefing",
                t=3,
                narrative_time="year 1049, three weeks ago",
                location_id="vellor_capital",
                participants=["korel"],
                description=(
                    "Korel handed Mara the sealed letter. Said: 'Discretion. No copies.' "
                    "Did not disclose contents."
                ),
                thread_id="courier_mission",
            ),
            Event(
                id="e_departure",
                t=4,
                narrative_time="year 1049, yesterday morning",
                location_id="vellor_capital",
                participants=[],
                description="Mara departed the capital northbound.",
                thread_id="courier_mission",
            ),
            Event(
                id="e_arrival",
                t=5,
                narrative_time="today, dusk",
                location_id="inn",
                participants=["hadrian"],
                description=(
                    "Mara arrived at Crow's Foot Inn at dusk. Hadrian welcomed her with "
                    "stew. Mara has not yet shown wealth."
                ),
                thread_id="inn_night",
            ),
        ],
        initial_knowledge=[
            KnowledgeEntry(
                event_id="e_skirmish",
                text=(
                    "Two summers ago, your father Tomas died in the skirmish at "
                    "Heavyfall Pass. You wear the loss like a second cloak."
                ),
                learned_at=-1,
            ),
            KnowledgeEntry(
                event_id="e_recruitment",
                text="You took courier work after his death — his debts wouldn't pay themselves.",
                learned_at=-1,
            ),
            KnowledgeEntry(
                event_id="e_briefing",
                text=(
                    "Three weeks ago, Spymaster Korel handed you a sealed letter for "
                    "one Olwen, in Mawley. 'Discretion,' he said. 'No copies.' He didn't "
                    "say what was in it."
                ),
                learned_at=-1,
            ),
            KnowledgeEntry(
                event_id="e_departure",
                text="You left the capital yesterday morning.",
                learned_at=-1,
            ),
            KnowledgeEntry(
                event_id="e_arrival",
                text=(
                    "You reached the Crow's Foot Inn at dusk. The innkeeper, Hadrian, "
                    "welcomed you in with stew."
                ),
                learned_at=-1,
            ),
        ],
        initial_player_state=PlayerState(
            location_id="inn",
            stats=CharacterStats(
                hp=24,
                hp_max=24,
                ac=13,
                strength=11,
                dexterity=14,
                constitution=13,
                intelligence=12,
                wisdom=13,
                charisma=14,
                # persuasion +2 lives on the persuasion_skill item's effects
            ),
            items=["sealed_letter", "gold_pouch", "shortsword", "persuasion_skill"],
        ),
        opening_beats=[
            Beat(
                kind="observation",
                text=(
                    "Two summers since Heavyfall — the loss still sits on Mara's "
                    "shoulders like a second cloak."
                ),
            ),
            Beat(
                kind="observation",
                text=(
                    "Three weeks after Korel pressed the sealed letter into her hand "
                    "with 'discretion, no copies', she is within a day's ride of the "
                    "Sken border."
                ),
            ),
            Beat(
                kind="observation",
                text=(
                    "The Crow's Foot Inn meets her at dusk: smoky common room, "
                    "four trestle tables, a stewpot muttering over coals."
                ),
            ),
            Beat(
                kind="action",
                text="Hadrian — broad-faced, ruddy, fifties — waves her in with a generous spoon.",
            ),
            Beat(
                kind="dialogue",
                speaker="Hadrian",
                text="Settle in, traveller.",
            ),
        ],
    )
