"""WorldDB — the single source of truth.

Four atoms: Location, Character, Item, History. Player is `characters["player"]`
(no special atom). Knowledge / beliefs / log / disposition are derived from
history filtered by `participants` — never stored as separate fields.

`Character.description` is PUBLIC identity only (race, appearance, manner, voice,
role). Anything spoilable — secrets, plans, stances, private history — lives in
History records with the character as participant.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


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


class Character(BaseModel):
    id: str
    name: str
    description: str
    location_id: str
    hp: int
    hp_max: int
    ac: int
    abilities: Abilities = Field(default_factory=Abilities)
    skill_mods: dict[str, int] = Field(default_factory=dict)
    gold: int = 0


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
    locations: dict[str, Location] = Field(default_factory=dict)
    characters: dict[str, Character] = Field(default_factory=dict)
    items: dict[str, Item] = Field(default_factory=dict)
    history: list[History] = Field(default_factory=list)
    next_t: int = 0
    narrative_time: str = "Day 1, dawn"
