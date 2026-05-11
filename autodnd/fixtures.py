"""Hardcoded fixtures for tests and slice demos.

- ``vale_inn(world)`` — tiny: one location, two characters, three records.
  Used for unit tests of the firewall and conductor.
- ``waymeet_scene(world)`` — ports atoms from ``test.json``, with secrets
  pulled out of character descriptions into private history records. Used
  to A/B against the legacy Director's failure modes (Slice 4).
"""

from __future__ import annotations

from autodnd.engine.delta import (
    create_character,
    create_item,
    create_location,
    mint_history,
)
from autodnd.engine.world import HeldBy, World


def vale_inn(world: World) -> None:
    """Seed ``world`` with the vale-inn scene. Mutates in place."""
    create_location(
        world,
        location_id="vale_inn",
        name="The Vale Inn",
        description=(
            "A warm tavern by the road, smoke-streaked beams overhead. "
            "Long bar of dark oak, three tables, a hearth at the back."
        ),
    )
    create_character(
        world,
        character_id="player",
        name="Fox",
        description=(
            "A wandering scout, lean and quiet, with watchful eyes and "
            "road-stained leathers."
        ),
        location_id="vale_inn",
        hp=10,
        hp_max=10,
        ac=12,
        skill_mods={"perception": 3, "stealth": 4, "athletics": 2},
    )
    create_character(
        world,
        character_id="brona",
        name="Brona",
        description=(
            "A dwarf tavern-keeper with weathered hands and a deep, careful "
            "voice. Gray-streaked beard tucked into a leather apron."
        ),
        location_id="vale_inn",
        hp=8,
        hp_max=8,
        ac=10,
        skill_mods={"perception": 2, "insight": 3},
    )
    create_item(
        world,
        item_id="shortsword",
        name="shortsword",
        description="Worn leather grip, blade well-honed.",
        position=HeldBy(character_id="player"),
        effects={"attack": 4},
    )

    # Public arrival: both characters in participants.
    mint_history(
        world,
        participants=["player", "brona"],
        description="The player walked into the inn and took a seat at the bar.",
        location_id="vale_inn",
    )

    # Private to Brona: her own resolution. Player must NOT see this in their
    # render or any other character's render.
    mint_history(
        world,
        participants=["brona"],
        description=(
            "Brona resolved to send word to Korel by morning — the player "
            "fits the description in the warning."
        ),
        location_id="vale_inn",
    )

    # Private to player: an internal thought. Brona must NOT see this.
    mint_history(
        world,
        participants=["player"],
        description=(
            "The player thought about the road ahead — restless, sensing "
            "something off about the inn but unable to name it."
        ),
        location_id="vale_inn",
    )


def waymeet_scene(world: World) -> None:
    """Seed ``world`` with the Waymeet setup ported from ``test.json``.

    The port pulls every spoilable fact out of character descriptions (where
    the legacy Director leaked them) and into private History records with
    only the knower as participant. This is what enables the per-character
    firewall to actually work — Brona's render doesn't include Silan's
    surveillance brief because Silan is the only participant of that record.
    """
    # ---------- Locations (public; no secrets) ----------
    create_location(
        world,
        location_id="waymeet",
        name="Waymeet",
        description=(
            "A frontier city built where the Old Dwarf Road meets the River "
            "Yarrow. Human-ruled trading hub, muddy streets, wooden walls "
            "patched a dozen times. Three districts: the Docks, the Market "
            "Square, and the Heights. A crumbling stone watchtower — the "
            "Old Yarrow Tower — stands at the city's center."
        ),
    )
    create_location(
        world,
        location_id="aelindor",
        name="The Vale of Aelindor",
        description=(
            "The ancient elven kingdom, hidden in a forested valley with its "
            "own weather. White stone spires rise above mist-laden trees. "
            "The Elven Council governs through tradition and unspoken "
            "consensus. Outsiders are tolerated only at the border post "
            "called the Last Gate."
        ),
    )
    create_location(
        world,
        location_id="khazad_mar",
        name="Khazad-Mar",
        description=(
            "The greatest dwarven hold still standing — a mountain carved "
            "into a fortress-city of iron, steam, and deep-forged fire. "
            "Master smiths who arm the human kingdoms. The High Forge still "
            "burns."
        ),
    )
    create_location(
        world,
        location_id="cinder_waste",
        name="The Cinder Waste",
        description=(
            "A scarred lowland south of Waymeet, where the ground is black "
            "and brittle for miles. Nothing grows but thornbush and "
            "ash-grass. Orc clans now roam the Waste."
        ),
    )
    create_location(
        world,
        location_id="dragons_tooth",
        name="The Dragon's Tooth",
        description=(
            "A lone mountain peak visible from Waymeet on clear days, "
            "jutting from the plain like a broken fang. Snow-capped year "
            "round. Strange blue light has been seen pulsing from its "
            "summit during thunderstorms."
        ),
    )
    create_location(
        world,
        location_id="last_gate",
        name="The Last Gate",
        description=(
            "The only official exit from the Vale of Aelindor — a white "
            "stone archway covered in silver-leaf vines. Two elven wardens "
            "stand eternal guard, spears tipped with crystal that glows "
            "softly."
        ),
    )

    # ---------- Characters: PUBLIC-ONLY descriptions ----------
    # Anything spoilable (motive, secret, plan, history) goes into History.
    create_character(
        world,
        character_id="player",
        name="Fox Arthur",
        description=(
            "A young elven scholar in road-stained traveler's leathers, with "
            "quiet manner and watchful eyes. Speaks Common with a faint "
            "Aelindorian cadence. Carries a silverwood longbow and an "
            "elven shortsword."
        ),
        location_id="waymeet",
        hp=10,
        hp_max=10,
        ac=14,
        skill_mods={"perception": 3, "stealth": 4, "insight": 2, "investigation": 4},
        gold=15,
    )
    create_character(
        world,
        character_id="brona",
        name="Brona Ironsong",
        description=(
            "A dwarf woman in her late 180s, broad-shouldered, with iron-"
            "grey braids and a permanent scowl. Runs The Anvil's Rest, a "
            "tavern in Waymeet's Market Square that serves dwarven ale and "
            "human food with equal contempt. Speaks Common with a faint "
            "Khazad-Mar lilt."
        ),
        location_id="waymeet",
        hp=18,
        hp_max=18,
        ac=15,
        skill_mods={"perception": 2, "insight": 4, "intimidation": 3},
    )
    create_character(
        world,
        character_id="kastor_vel",
        name="Kastor Vel",
        description=(
            "A human merchant in his 40s, impeccably dressed in dark wool "
            "and silver rings. Runs Vel & Sons Mercantile, the largest "
            "trading company in Waymeet. Sits on the merchant council. "
            "Charming, warm in manner, fluent in three languages."
        ),
        location_id="waymeet",
        hp=10,
        hp_max=10,
        ac=11,
        skill_mods={"persuasion": 5, "deception": 5, "insight": 4},
    )
    create_character(
        world,
        character_id="silan",
        name="Silan",
        description=(
            "An elven woman, ageless, with dark hair braided tight against "
            "her scalp and eyes the color of winter ice. Travels alone with "
            "a small leather notebook. Renting a room above Garret's "
            "Bakery in Waymeet. Quiet, deliberate, watchful."
        ),
        location_id="waymeet",
        hp=12,
        hp_max=12,
        ac=15,
        skill_mods={"stealth": 6, "perception": 5, "deception": 4},
    )
    create_character(
        world,
        character_id="thrag",
        name="Thrag",
        description=(
            "An orc scout in his late 20s, lean and sharp-eyed, with ritual "
            "scars on his cheeks. Speaks perfect Common with a low, careful "
            "voice. Travels with a heavy satchel. Has been turned away at "
            "three inns since arriving in Waymeet."
        ),
        location_id="waymeet",
        hp=14,
        hp_max=14,
        ac=14,
        skill_mods={"perception": 4, "survival": 5, "athletics": 4},
    )
    create_character(
        world,
        character_id="mira_lawless",
        name="Mira Lawless",
        description=(
            "A human woman in her 30s, sharp-faced, with a scar across her "
            "left eyebrow and a crossbow at her hip. The de facto deputy of "
            "Waymeet's undermanned watch. Practical, observant, blunt."
        ),
        location_id="waymeet",
        hp=14,
        hp_max=14,
        ac=15,
        skill_mods={"perception": 4, "investigation": 3, "intimidation": 3},
    )
    create_character(
        world,
        character_id="old_torgal",
        name="Old Torgal",
        description=(
            "A weathered human of indeterminate age living in the base of "
            "the Old Yarrow Tower. Skin like cracked leather, one eye milky "
            "blind, the other pale blue and unsettlingly sharp. Speaks in "
            "fragments. The city tolerates him because he keeps the rats "
            "down and doesn't bother anyone."
        ),
        location_id="waymeet",
        hp=8,
        hp_max=8,
        ac=10,
        skill_mods={"perception": 5, "investigation": 5, "insight": 4},
    )

    # ---------- Items ----------
    create_item(
        world,
        item_id="fox_longbow",
        name="Silverwood Longbow",
        description=(
            "A longbow crafted from Aelindorian silverwood — pale, flexible, "
            "and surprisingly light. The wood has a faint shimmer in "
            "moonlight."
        ),
        position=HeldBy(character_id="player"),
        effects={"attack": 1},
    )
    create_item(
        world,
        item_id="fox_journal",
        name="Fox's Journal",
        description=(
            "A leather-bound journal, half-filled with elegant elvish "
            "script. A charcoal sketch of the Dragon's Tooth is tucked "
            "between the back pages."
        ),
        position=HeldBy(character_id="player"),
    )
    create_item(
        world,
        item_id="fox_shortsword",
        name="Shortsword",
        description=(
            "A practical elven shortsword — straight blade, leather-wrapped "
            "grip, a small garnet in the pommel. Never drawn in anger."
        ),
        position=HeldBy(character_id="player"),
        effects={"attack": 1},
    )
    create_item(
        world,
        item_id="traveler_pack",
        name="Traveler's Pack",
        description=(
            "A worn leather backpack: bedroll, mess kit, tinderbox, 10 days "
            "of trail rations, waterskin, 50 ft hempen rope, hooded lantern."
        ),
        position=HeldBy(character_id="player"),
    )

    # ---------- Cosmic history (no character participants) ----------
    mint_history(
        world,
        participants=[],
        description=(
            "The God-Fall Wars — over 1,000 years ago. A dragon of immense "
            "size was struck down over the southern plains; its body carved "
            "a trench miles long and its blood burned the earth sterile, "
            "creating the Cinder Waste."
        ),
        location_id="cinder_waste",
        narrative_time="Age of Embers (over 1,000 years ago)",
    )
    mint_history(
        world,
        participants=[],
        description=(
            "The Aelindor Council secretly funded an expedition to the "
            "Dragon's Tooth — six elven scholars, two dwarven mountaineers, "
            "one human cartographer. They climbed in early spring. They "
            "never returned. The Council classified all records."
        ),
        location_id="dragons_tooth",
        narrative_time="500 years ago",
    )
    mint_history(
        world,
        participants=[],
        description=(
            "The Iron-and-Timber Accord was signed in Waymeet's Old Yarrow "
            "Tower. Dwarves supply ore and finished steel at fixed rates; "
            "humans supply timber, grain, and southern market access. Within "
            "decades the price-adjustment clauses had bled the mountain dry."
        ),
        location_id="waymeet",
        narrative_time="Three generations ago",
    )

    # ---------- Per-character private knowledge ----------
    # Brona
    mint_history(
        world,
        participants=["brona"],
        description=(
            "Brona left Khazad-Mar a decade ago after a bitter dispute with "
            "the clan elders over the trade treaty — she argued the mountain "
            "was being bled dry. The elders refused to listen. She has been "
            "above ground ever since."
        ),
        narrative_time="Ten years ago",
    )
    mint_history(
        world,
        participants=["brona"],
        description=(
            "Brona has been quietly collecting letters between Khazad-Mar "
            "merchants and the Waymeet council for years — proof of "
            "price-fixing. The stash is hidden beneath a loose floorboard "
            "in her tavern cellar."
        ),
        location_id="waymeet",
        narrative_time="Ongoing",
    )
    mint_history(
        world,
        participants=["brona"],
        description=(
            "A sealed letter from Brona's cousin (a clan elder in "
            "Khazad-Mar) arrived three days ago: the mountain council has "
            "called an emergency vote at the next full moon — 12 days from "
            "now — on whether to declare the Iron-and-Timber Accord void "
            "and close the passes. Brona has told no one."
        ),
        location_id="waymeet",
        narrative_time="Three days ago",
    )

    # Kastor
    mint_history(
        world,
        participants=["kastor_vel"],
        description=(
            "Kastor Vel knows perfectly well that the price-adjustment "
            "clauses he wrote into the Iron-and-Timber Accord favor human "
            "merchants over dwarves. He believes this is fair business. "
            "He has been told nothing about the dwarf emergency vote."
        ),
        narrative_time="Long-standing",
    )

    # Silan — the major secret
    mint_history(
        world,
        participants=["silan"],
        description=(
            "Silan is a Whisperer — an agent of the Elven Council's "
            "intelligence service. She was dispatched from Aelindor with "
            "orders to observe Fox Arthur after his departure, report his "
            "movements, and ensure he does not speak of the matters he "
            "uncovered in the restricted archives. Her cover is 'scholar "
            "of human customs.'"
        ),
        narrative_time="Six days ago (departure briefing)",
    )
    mint_history(
        world,
        participants=["silan"],
        description=(
            "Silan arrived in Waymeet three days before Fox, rented a room "
            "above Garret's Bakery, and has been watching from a tea stall "
            "near the well in the Market Square. She has followed Fox three "
            "times at distance. She carries a thin blade in her sleeve."
        ),
        location_id="waymeet",
        narrative_time="Past three days",
    )

    # Thrag
    mint_history(
        world,
        participants=["thrag"],
        description=(
            "Thrag was sent by his clan chieftain to Waymeet to buy "
            "medicine for a wasting sickness spreading through the clan. "
            "Human merchants overcharged him; he is sleeping in a stable "
            "because no inn will take an orc."
        ),
        location_id="waymeet",
        narrative_time="Past few days",
    )
    mint_history(
        world,
        participants=["thrag"],
        description=(
            "Thrag was woken last night by a tremor — the fourth in ten "
            "days. A fissure opened near his clan's camp in the Cinder "
            "Waste, venting hot steam. He saw a faint orange glow from the "
            "crack, pulsing like a heartbeat. He is starting to wonder "
            "whether the old stories about the dragon buried beneath the "
            "Waste are true."
        ),
        location_id="cinder_waste",
        narrative_time="Last night",
    )

    # Mira
    mint_history(
        world,
        participants=["mira_lawless"],
        description=(
            "Mira has noticed Waymeet getting tense: more dwarves refusing "
            "to trade, more elven faces watching from the crowd, more orcs "
            "turned away. She has been looking quietly for someone "
            "unaffiliated — fresh off the road, not yet entangled — to "
            "recruit as an extra set of eyes."
        ),
        location_id="waymeet",
        narrative_time="Recent weeks",
    )

    # Torgal
    mint_history(
        world,
        participants=["old_torgal"],
        description=(
            "Torgal was once a cartographer — best in the northern "
            "kingdoms. His daughter Lirien (from a marriage he does not "
            "discuss) joined the Aelindor Academy young, rose fast, and "
            "was chosen to lead the secret expedition to the Dragon's "
            "Tooth 500 years ago. She never returned. The Council "
            "classified everything. Torgal came to Waymeet to wait."
        ),
        narrative_time="60+ years ago",
    )
    mint_history(
        world,
        participants=["old_torgal"],
        description=(
            "Twenty years ago Torgal tripped over a smooth dark stone at "
            "the base of the Dragon's Tooth. It is warm to the touch, "
            "always, even in winter. Denser than its size should allow. "
            "He has kept it hidden in his coat pocket since."
        ),
        narrative_time="Twenty years ago",
    )
    mint_history(
        world,
        participants=["old_torgal"],
        description=(
            "Fifteen years ago Torgal found a torn page from the vanished "
            "expedition's field log being used as wrapping paper at a "
            "northern flea market. It describes an inner chamber that "
            "pulsed with light, walls warm to the touch, and the mountain "
            "'breathing.' Torgal keeps it hidden in his tower."
        ),
        narrative_time="Fifteen years ago",
    )

    # Player's private knowledge (the restricted archive readings)
    mint_history(
        world,
        participants=["player"],
        description=(
            "In a basement archive he was not supposed to enter, Fox read "
            "the departure log of an expedition to the Dragon's Tooth that "
            "the Aelindor Council had sealed five centuries ago. Six elven "
            "scholars, two dwarven mountaineers, an unnamed human "
            "cartographer. The log's final entry was in a hand that looked "
            "*wrong* — darker ink, uneven strokes — and read: 'The "
            "mountain is not stone. It is something else. We will "
            "proceed.'"
        ),
        narrative_time="Two years ago",
    )
    mint_history(
        world,
        participants=["player"],
        description=(
            "In a partially burned file Fox saw a redacted name preserved "
            "only as a first name: *Lirien*. He has never spoken it aloud "
            "to anyone."
        ),
        narrative_time="Two years ago",
    )
    mint_history(
        world,
        participants=["player"],
        description=(
            "After Fox asked one question too many, his thesis advisor "
            "stopped returning his correspondence. Fox understood he was "
            "no longer studying Aelindor — he was studying the walls "
            "around its silences."
        ),
        narrative_time="Last year",
    )
    mint_history(
        world,
        participants=["player"],
        description=(
            "Fox walked through the Last Gate at dawn six days ago. The "
            "elder warden recorded his name without looking up; one of the "
            "wardens glanced at him with something between pity and "
            "recognition. He has not looked back."
        ),
        location_id="last_gate",
        narrative_time="Six days ago",
    )
    mint_history(
        world,
        participants=["player"],
        description=(
            "Seeing the Dragon's Tooth from the road three days ago, Fox "
            "felt something cross his chest like a plucked string. Not "
            "fear. *Recognition*."
        ),
        narrative_time="Three days ago",
    )

    # ---------- Recent in-scene history (turn 14 context) ----------
    # Player has been in Waymeet two days, staying above Brona's tavern.
    mint_history(
        world,
        participants=["player", "brona"],
        description=(
            "Fox arrived at The Anvil's Rest two days ago and rented a "
            "room above the tavern. Brona did not bother learning his name "
            "the first night, but noticed he ate alone."
        ),
        location_id="waymeet",
        narrative_time="Two days ago",
    )
    mint_history(
        world,
        participants=["player", "old_torgal"],
        description=(
            "Old Torgal approached Fox briefly on Fox's first day in town, "
            "muttered 'The tooth remembers the jaw,' and shuffled away "
            "before Fox could respond."
        ),
        location_id="waymeet",
        narrative_time="Two days ago",
    )
    mint_history(
        world,
        participants=["old_torgal"],
        description=(
            "Torgal has watched Fox through his tower's narrow north "
            "window: Fox passed by twice yesterday, once at dawn and once "
            "at dusk, stopping in the street each time to look south "
            "toward the mountain. Torgal cannot see into rooms — only the "
            "street."
        ),
        location_id="waymeet",
        narrative_time="Yesterday",
    )
    mint_history(
        world,
        participants=["player", "brona", "thrag"],
        description=(
            "Late afternoon. Fox sits at a small table near the fire at "
            "The Anvil's Rest, his journal open to a sketch of the "
            "Dragon's Tooth. Thrag has just walked in, looked around the "
            "crowded room, and approached Fox's table — the only empty "
            "seat. Thrag's voice was low and careful: 'This seat taken?' "
            "Brona stopped wiping a cup and watched."
        ),
        location_id="waymeet",
        narrative_time="Just now",
    )
