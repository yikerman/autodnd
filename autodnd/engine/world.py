"""World Model schemas for AutoDND.

Source of truth: ``plan/PLAN.md`` "World Model" section.

Three layers:

- Atoms: :class:`Location`, :class:`Item`, :class:`Event`
- Organization: :class:`Character` (NPC only), :class:`Thread` (forest via ``parent_id``)
- Perspective: :class:`KnowledgeEntry`, :class:`PlayerState`

Mutation lives in ``engine/delta.py``; these schemas are pure data. Per-field
mutability policy is enforced by the validator there, not by these models.
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
    t: int
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


class KnowledgeEntry(BaseModel):
    event_id: str | None = None
    text: str
    learned_at: int


class PlayerState(BaseModel):
    location_id: str
    stats: CharacterStats
    items: list[str] = Field(default_factory=list)
    knowledge: list[KnowledgeEntry] = Field(default_factory=list)


class WorldModel(BaseModel):
    locations: dict[str, Location] = Field(default_factory=dict)
    items: dict[str, Item] = Field(default_factory=dict)
    characters: dict[str, Character] = Field(default_factory=dict)
    events: dict[str, Event] = Field(default_factory=dict)
    threads: dict[str, Thread] = Field(default_factory=dict)
    player: PlayerState
    turn: int
