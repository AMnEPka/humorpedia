"""Public rating API models."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, StrictInt


class RatingEntityType(str, Enum):
    ARTICLE = "article"
    PERSON = "person"
    TEAM = "team"
    SHOW = "show"


class RatingVoteRequest(BaseModel):
    score: StrictInt = Field(ge=1, le=10)


class RatingResponse(BaseModel):
    average: Optional[float] = None
    votes_label: Optional[str] = None
    my_score: Optional[int] = None
