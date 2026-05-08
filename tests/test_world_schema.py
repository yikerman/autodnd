"""Round-trip and sanity-load tests for engine.world schemas.

These don't exercise any logic — they catch schema typos and ensure the
shapes accept the worked-example bootstrap JSON.
"""

from autodnd.engine.world import (
    Character,
    CharacterStats,
    Event,
    Item,
    Location,
    PlayerState,
    Thread,
    WorldModel,
)


def _build_minimal_world() -> WorldModel:
    return WorldModel(
        locations={
            "inn": Location(
                id="inn", name="Crow's Foot Inn", description="Roadside inn at dusk."
            ),
        },
        items={
            "shortsword": Item(
                id="shortsword",
                name="shortsword",
                description="Plain blade, well-kept.",
            ),
        },
        characters={
            "hadrian": Character(
                id="hadrian",
                name="Hadrian",
                description="Ruddy innkeeper.",
                location_id="inn",
                stats=CharacterStats(hp=14, ac=11),
            ),
        },
        events={
            "e0": Event(
                id="e0",
                t=0,
                narrative_time="today, dusk",
                location_id="inn",
                participants=["hadrian"],
                description="Mara arrived at the inn.",
                thread_id="inn_night",
            ),
        },
        threads={
            "inn_night": Thread(
                id="inn_night",
                name="Night at Crow's Foot",
                parent_id=None,
                description="Mara stops at the inn.",
            ),
        },
        player=PlayerState(
            location_id="inn",
            stats=CharacterStats(hp=24, ac=13, mods={"persuasion": 2}),
            gold=50,
            items=["shortsword"],
            log=["You reached the inn at dusk."],
        ),
        turn=0,
        next_event_t=1,
    )


def test_round_trip_preserves_shape():
    world = _build_minimal_world()
    rebuilt = WorldModel.model_validate(world.model_dump())
    assert rebuilt == world


def test_root_thread_has_no_parent():
    thread = Thread(id="root", name="root arc", description="...")
    assert thread.parent_id is None


def test_next_event_t_defaults_to_zero():
    """Fresh WorldModel starts the event-time counter at 0."""
    world = WorldModel(
        player=PlayerState(location_id="", stats=CharacterStats(hp=0, ac=0)),
        turn=-1,
    )
    assert world.next_event_t == 0


def test_loads_worked_example_shaped_payload():
    """Stripped-down bootstrap JSON exercising every field a bootstrapped world
    would land in after the Director's tool calls."""
    payload = {
        "locations": {
            "inn": {
                "id": "inn",
                "name": "Crow's Foot Inn",
                "description": "Roadside inn at dusk.",
            },
            "vellor_capital": {
                "id": "vellor_capital",
                "name": "Vellor capital",
                "description": "Walled city on the river.",
            },
        },
        "items": {
            "sealed_letter": {
                "id": "sealed_letter",
                "name": "sealed letter",
                "description": "Wax-sealed parchment.",
            },
            "persuasion_skill": {
                "id": "persuasion_skill",
                "name": "persuasion (skill)",
                "description": "Trained ability — Mara can read a room.",
                "effects": {"persuasion": 2},
            },
        },
        "characters": {
            "hadrian": {
                "id": "hadrian",
                "name": "Hadrian",
                "location_id": "inn",
                "description": "Ruddy innkeeper.",
                "stats": {"hp": 14, "ac": 11, "mods": {}},
            },
        },
        "events": {
            "e_treaty": {
                "id": "e_treaty",
                "t": 0,
                "narrative_time": "year 1043, spring",
                "location_id": "vellor_capital",
                "participants": [],
                "description": "Vellor and Sken signed the Treaty of Three Rivers.",
                "thread_id": "tensions",
            },
            "e_arrival": {
                "id": "e_arrival",
                "t": 5,
                "narrative_time": "today, dusk",
                "location_id": "inn",
                "participants": ["hadrian"],
                "description": "Mara arrived at the inn.",
                "thread_id": "inn_night",
            },
        },
        "threads": {
            "tensions": {
                "id": "tensions",
                "name": "Vellor–Sken tensions",
                "parent_id": None,
                "description": "Uneasy peace.",
            },
            "inn_night": {
                "id": "inn_night",
                "name": "Night at Crow's Foot",
                "parent_id": "tensions",
                "description": "Mara stops at the inn.",
            },
        },
        "player": {
            "location_id": "inn",
            "stats": {"hp": 24, "ac": 13, "mods": {"persuasion": 2}},
            "gold": 50,
            "items": ["sealed_letter", "persuasion_skill"],
            "log": ["You reached the Crow's Foot Inn at dusk."],
        },
        "turn": 0,
        "next_event_t": 6,
    }
    world = WorldModel.model_validate(payload)
    assert world.player.stats.mods["persuasion"] == 2
    assert world.events["e_treaty"].t == 0
    assert world.threads["inn_night"].parent_id == "tensions"
    assert world.player.log[0] == "You reached the Crow's Foot Inn at dusk."
    assert world.items["persuasion_skill"].effects["persuasion"] == 2
    assert world.player.gold == 50
    assert world.next_event_t == 6
