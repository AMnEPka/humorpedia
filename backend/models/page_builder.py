"""Контракты локального конструктора; публичные документы остаются стандартными."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Materials(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    birth_date: str = Field(default='', max_length=40)
    birth_place: str = Field(default='', max_length=200)
    occupation: str = Field(default='', max_length=300)
    notes: str = Field(default='', max_length=30000)
    achievements: str = Field(default='', max_length=10000)
    sources: str = Field(default='', max_length=10000)


class DraftCreate(StrictModel):
    kind: Literal['person', 'team', 'show']
    materials: Materials


class Revision(StrictModel):
    revision: int = Field(ge=1)


class DraftUpdate(Revision):
    materials: Materials
    page: dict[str, Any]
    relations: list[dict[str, Any]] = Field(default_factory=list, max_length=100)


class AcceptVersion(Revision):
    version_id: str


class GeneratedSection(StrictModel):
    heading: str = Field(min_length=1, max_length=200)
    paragraphs: list[str] = Field(min_length=1, max_length=30)
    fact_ids: list[str] = Field(max_length=100)


class GeneratedResult(StrictModel):
    sections: list[GeneratedSection] = Field(min_length=1, max_length=30)
    warnings: list[str] = Field(max_length=100)
    questions: list[str] = Field(max_length=100)


class ApplyPackage(StrictModel):
    hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    reviewed: bool = False
    omit_relations: list[str] = Field(default_factory=list, max_length=100)
