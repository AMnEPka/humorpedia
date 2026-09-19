"""Global settings for the public "Читайте также" block."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


RecommendationResultType = Literal[
    "article",
    "person",
    "kvn_team",
    "show_team",
    "show",
    "city",
    "kvn",
    "quiz",
    "news",
]

DEFAULT_RECOMMENDATION_TYPES: list[RecommendationResultType] = [
    "article",
    "person",
    "kvn_team",
    "show_team",
    "show",
    "city",
    "kvn",
    "quiz",
]


class RecommendationTargets(BaseModel):
    articles: bool = True
    news: bool = True
    people: bool = True
    kvn_teams: bool = True
    show_teams: bool = True
    shows: bool = True
    cities: bool = True
    kvn: bool = True


class RecommendationSettings(BaseModel):
    enabled: bool = True
    max_items: int = Field(default=3, ge=1, le=12)
    result_types: list[RecommendationResultType] = Field(
        default_factory=lambda: list(DEFAULT_RECOMMENDATION_TYPES),
        min_length=1,
    )
    apply_to: RecommendationTargets = Field(default_factory=RecommendationTargets)

    @field_validator("result_types")
    @classmethod
    def unique_result_types(cls, value: list[RecommendationResultType]) -> list[RecommendationResultType]:
        return list(dict.fromkeys(value))


RecommendationSourceType = Literal["article", "news", "person", "team", "show", "city", "kvn"]
