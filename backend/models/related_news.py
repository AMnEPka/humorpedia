"""Global settings for contextual fresh-news blocks."""

from typing import Literal

from pydantic import BaseModel, Field


class RelatedNewsTargets(BaseModel):
    people: bool = True
    kvn_teams: bool = True
    show_teams: bool = True
    shows: bool = True


class RelatedNewsSettings(BaseModel):
    enabled: bool = True
    freshness_days: int = Field(default=183, ge=1, le=3650)
    max_items: int = Field(default=3, ge=1, le=3)
    apply_to: RelatedNewsTargets = Field(default_factory=RelatedNewsTargets)


RelatedNewsEntityType = Literal["person", "team", "show"]
