"""Models for public correction suggestions and editorial review."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field, field_validator


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CorrectionSuggestionStatus(str, Enum):
    NEW = "new"
    IN_REVIEW = "in_review"
    FIXED = "fixed"
    REJECTED = "rejected"


class CorrectionSuggestionCreate(BaseModel):
    page_title: str = Field(min_length=1, max_length=300)
    page_path: str = Field(min_length=1, max_length=500)
    section: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=3, max_length=5000)
    source: Optional[str] = Field(default=None, max_length=1000)
    email: Optional[EmailStr] = None
    website: str = Field(default="", max_length=200)  # honeypot

    @field_validator("page_title", "section", "message", "source", "website", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("page_path")
    @classmethod
    def validate_page_path(cls, value: str) -> str:
        value = value.strip()
        parsed = urlsplit(value)
        if not value.startswith("/") or value.startswith("//") or parsed.scheme or parsed.netloc:
            raise ValueError("Укажите путь страницы Humorpedia")
        return value


class CorrectionSuggestionReview(BaseModel):
    status: CorrectionSuggestionStatus
    admin_comment: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("admin_comment", mode="before")
    @classmethod
    def strip_comment(cls, value):
        return value.strip() if isinstance(value, str) else value


def build_suggestion(data: CorrectionSuggestionCreate) -> dict:
    created_at = now_iso()
    return {
        "_id": str(uuid4()),
        "page_title": data.page_title,
        "page_path": data.page_path,
        "section": data.section,
        "message": data.message,
        "source": data.source or None,
        "email": str(data.email) if data.email else None,
        "status": CorrectionSuggestionStatus.NEW.value,
        "admin_comment": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": created_at,
        "updated_at": created_at,
    }
