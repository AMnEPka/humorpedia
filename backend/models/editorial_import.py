"""Editor-only source import commands; public content is created only on approval."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal
from models.content import PersonBio

SourceId = Literal['24smi', 'vokrugtv', 'gostandup', 'zhaba']


class ImportPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=300)
    slug: str = Field(min_length=1, max_length=180, pattern=r'^[a-z0-9]+(?:[-_][a-z0-9]+)*$')
    full_name: str = Field(default='', max_length=200)
    content: str = Field(min_length=1, max_length=200_000)
    excerpt: str = Field(default='', max_length=2000)
    bio: PersonBio = Field(default_factory=PersonBio)
    related_person_ids: list[str] = Field(default_factory=list, max_length=100)
    related_show_ids: list[str] = Field(default_factory=list, max_length=100)


class ImportURLs(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=10)


class ScanRequest(BaseModel):
    source_id: SourceId = '24smi'
    days: int = Field(default=3, ge=1, le=30)
    limit: int = Field(default=100, ge=1, le=200)


class ImportEdit(BaseModel):
    revision: int = Field(ge=1)
    payload: ImportPayload
    target_id: str | None = Field(default=None, max_length=100)
    refresh_target: bool = False


class ImportDecision(BaseModel):
    revision: int = Field(ge=1)


class ImportSettings(BaseModel):
    source_id: SourceId = '24smi'
    enabled: bool
    hour_moscow: int = Field(default=10, ge=0, le=23)
