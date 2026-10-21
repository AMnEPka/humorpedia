"""Shared visibility rules for public content GET endpoints."""

from fastapi import HTTPException

from models.base import ContentStatus
from utils.auth import EDITOR_ROLES


async def editor_can_view_archived(request, get_current_user) -> bool:
    """Direct route calls without a Request retain public visibility semantics."""
    if request is None:
        return False
    user = await get_current_user(request)
    return bool(user and user.get("role") in EDITOR_ROLES)


def visible_query(query: dict | None, editor: bool) -> dict:
    """Add the public archive exclusion without mutating the caller's query."""
    query = dict(query or {})
    if editor:
        return query
    public_status = {"status": {"$ne": ContentStatus.ARCHIVED.value}}
    return {"$and": [query, public_status]} if query else public_status


def require_visible(document: dict | None, editor: bool, not_found: str) -> dict:
    if not document or (document.get("status") == ContentStatus.ARCHIVED.value and not editor):
        raise HTTPException(status_code=404, detail=not_found)
    return document
