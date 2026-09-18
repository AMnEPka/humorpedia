"""Poll definitions and API payloads."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .base import generate_uuid, utc_now


class PollOption(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(default_factory=generate_uuid)
    text: str = Field(min_length=1, max_length=300)
    historical_votes: int = Field(default=0, ge=0)


class PollBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=3, max_length=500)
    options: list[PollOption] = Field(min_length=2, max_length=20)
    status: Literal["draft", "published", "archived"] = "draft"
    show_results_before_vote: bool = False

    @model_validator(mode="after")
    def unique_options(self):
        ids = [option.id for option in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("Идентификаторы вариантов ответа должны быть уникальны")
        texts = [option.text.strip().casefold() for option in self.options]
        if len(texts) != len(set(texts)):
            raise ValueError("Варианты ответа не должны повторяться")
        return self


class PollCreate(PollBase):
    pass


class PollUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: Optional[str] = Field(None, min_length=3, max_length=500)
    options: Optional[list[PollOption]] = Field(None, min_length=2, max_length=20)
    status: Optional[Literal["draft", "published", "archived"]] = None
    show_results_before_vote: Optional[bool] = None

    @model_validator(mode="after")
    def unique_options(self):
        if self.options is None:
            return self
        ids = [option.id for option in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("Идентификаторы вариантов ответа должны быть уникальны")
        texts = [option.text.strip().casefold() for option in self.options]
        if len(texts) != len(set(texts)):
            raise ValueError("Варианты ответа не должны повторяться")
        return self


class Poll(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=generate_uuid, alias="_id")
    question: str
    options: list[PollOption]
    status: Literal["draft", "published", "archived"] = "draft"
    show_results_before_vote: bool = False
    old_id: Optional[int] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PollVoteCreate(BaseModel):
    option_id: str = Field(min_length=1, max_length=100)
