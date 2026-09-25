"""Validated request and storage models for editor-reviewed research proposals."""
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


ProposalKind = Literal["update_person", "new_person"]
ProposalStatus = Literal["new", "in_review", "accepted", "rejected", "conflict"]
ChangeStatus = Literal["pending", "accepted", "rejected", "conflict"]


class EditorialSource(BaseModel):
    url: HttpUrl
    title: str = Field(min_length=1, max_length=300)
    published_at: Optional[str] = None
    checked_at: Optional[str] = None
    excerpt: Optional[str] = Field(default=None, max_length=500)


class EditorialChangeInput(BaseModel):
    id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    field: str = Field(min_length=1, max_length=200)
    label: Optional[str] = Field(default=None, max_length=200)
    old_value: Any = None
    proposed_value: Any
    sources: list[EditorialSource] = Field(min_length=1, max_length=20)


class EditorialProposalCreate(BaseModel):
    kind: ProposalKind
    person_id: Optional[str] = None
    candidate_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=150)
    # Kept as an input alias for early clients; persisted and returned as ``slug``.
    candidate_slug: Optional[str] = Field(default=None, min_length=1, max_length=150)
    reason: Optional[str] = Field(default=None, max_length=1000)
    changes: list[EditorialChangeInput] = Field(min_length=1, max_length=100)

    @field_validator("candidate_slug")
    @classmethod
    def valid_slug(cls, value):
        if value is not None:
            import re
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
                raise ValueError("Slug должен состоять из латинских букв, цифр и дефисов")
        return value

    @field_validator("slug")
    @classmethod
    def valid_proposal_slug(cls, value):
        if value is not None:
            import re
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
                raise ValueError("Slug должен состоять из латинских букв, цифр и дефисов")
        return value


class EditorialDecision(BaseModel):
    change_id: str = Field(min_length=1, max_length=100)
    decision: Literal["accept", "reject"]
    edited_value: Any = None


class EditorialPersonIdentity(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=150)

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value):
        if value is not None:
            import re
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
                raise ValueError("Slug должен состоять из латинских букв, цифр и дефисов")
        return value


class EditorialDecisionRequest(BaseModel):
    decisions: list[EditorialDecision] = Field(min_length=1, max_length=100)
    person: Optional[EditorialPersonIdentity] = None


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
