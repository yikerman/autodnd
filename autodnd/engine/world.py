"""WorldDB — the single source of truth.

Four world atoms: Location, Player, Character, Item, History. The player has
their own field because player agency is not parallel to NPC agency. NPCs live
in ``characters``; the reserved participant token ``"player"`` refers to
``world.player`` in history and item ownership.

Knowledge / beliefs / log / disposition are derived from history filtered by
``participants`` — never stored as separate fields.

``Player.description`` and ``Character.description`` are PUBLIC identity only
(race, appearance, manner, voice, role). Anything spoilable — secrets, plans,
stances, private history — lives in History records with the knower as
participant.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

PLAYER = "player"


class Abilities(BaseModel):
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10


class Location(BaseModel):
    id: str
    name: str
    description: str


class ActorState(BaseModel):
    name: str
    description: str
    location_id: str
    hp: int
    hp_max: int
    ac: int
    abilities: Abilities = Field(default_factory=Abilities)
    skill_mods: dict[str, int] = Field(default_factory=dict)
    gold: int = 0


class Player(ActorState):
    pass


class Character(ActorState):
    id: str


class AtLocation(BaseModel):
    kind: Literal["at_location"] = "at_location"
    location_id: str


class HeldBy(BaseModel):
    kind: Literal["held_by"] = "held_by"
    character_id: str


ItemPosition = Annotated[AtLocation | HeldBy, Field(discriminator="kind")]


class Item(BaseModel):
    id: str
    name: str
    description: str
    effects: dict[str, int] = Field(default_factory=dict)
    position: ItemPosition


class History(BaseModel):
    """A single historical record — happening, speech, inference, resolution, or backstory.

    Immutable once minted (no edits). `participants` defines who perceived /
    knows. False beliefs are records of communication that don't match world
    state — the record of the telling is true; what was told may not be.
    """

    model_config = {"frozen": True}

    id: str
    t: int
    narrative_time: str
    location_id: str | None = None
    participants: list[str] = Field(default_factory=list)
    description: str


class World(BaseModel):
    player: Player | None = None
    locations: dict[str, Location] = Field(default_factory=dict)
    characters: dict[str, Character] = Field(default_factory=dict)
    items: dict[str, Item] = Field(default_factory=dict)
    history: list[History] = Field(default_factory=list)
    next_t: int = 0
    narrative_time: str = "Day 1, dawn"
