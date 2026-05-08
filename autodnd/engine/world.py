"""World Model schemas for AutoDND.

Three layers:

- Atoms: :class:`Location`, :class:`Item`, :class:`Event`
- Organization: :class:`Character` (NPC only), :class:`Thread` (forest via ``parent_id``)
- Perspective: :class:`PlayerState` (with append-only NL ``log``)

Mutation lives in ``engine/delta.py``; these schemas are pure data. Per-field
mutability policy is enforced by the per-mutation ``apply_*`` functions there,
not by these models.
"""

from pydantic import BaseModel, Field


class Item(BaseModel):
    id: str
    name: str
    description: str
    effects: dict[str, int] = Field(
        default_factory=dict
    )  # bonuses granted while carried (e.g. {"persuasion": 2})


class Location(BaseModel):
    id: str
    name: str
    description: str


class CharacterStats(BaseModel):
    hp: int
    ac: int
    hp_max: int = 0  # 0 = unbounded healing; positive = max HP cap
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    mods: dict[str, int] = Field(
        default_factory=dict
    )  # ad-hoc bonuses (skills, saves, etc.)


class Character(BaseModel):
    """An NPC. The player is *not* a Character — see :class:`PlayerState`."""

    id: str
    name: str
    description: str
    location_id: str
    stats: CharacterStats


class Event(BaseModel):
    id: str
    t: int  # engine-assigned, monotonic across the session
    narrative_time: str
    location_id: str
    participants: list[str] = Field(default_factory=list)
    description: str
    thread_id: str


class Thread(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    description: str


class PlayerState(BaseModel):
    location_id: str
    stats: CharacterStats
    gold: int = 0
    items: list[str] = Field(default_factory=list)
    log: list[str] = Field(
        default_factory=list
    )  # append-only NL log of player perception


class WorldModel(BaseModel):
    locations: dict[str, Location] = Field(default_factory=dict)
    items: dict[str, Item] = Field(default_factory=dict)
    characters: dict[str, Character] = Field(default_factory=dict)
    events: dict[str, Event] = Field(default_factory=dict)
    threads: dict[str, Thread] = Field(default_factory=dict)
    player: PlayerState
    turn: int
    next_event_t: int = 0  # engine-managed; mint_event reads + increments
