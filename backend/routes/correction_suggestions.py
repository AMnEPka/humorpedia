"""Public correction suggestions and their editorial queue."""

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from models.correction_suggestion import (
    CorrectionSuggestionCreate,
    CorrectionSuggestionReview,
    CorrectionSuggestionStatus,
    build_suggestion,
)
from utils.auth import require_editor
from utils.database import get_db
from utils.rate_limit import limiter


router = APIRouter(prefix="/correction-suggestions", tags=["correction-suggestions"])


@router.post("", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/hour")
async def create_correction_suggestion(data: CorrectionSuggestionCreate, request: Request):
    """Accept a plain-text suggestion without changing public content."""
    if data.website:
        # Bots commonly fill every input. Return the normal response without storing spam.
        return {"accepted": True}

    document = build_suggestion(data)
    await (await get_db()).correction_suggestions.insert_one(document)
    return {"accepted": True, "id": document["_id"]}


@router.get("", response_model=dict, dependencies=[Depends(require_editor)])
async def list_correction_suggestions(
    status_filter: Optional[Literal["new", "in_review", "fixed", "rejected"]] = Query(
        default=None, alias="status"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    db = await get_db()
    query = {"status": status_filter} if status_filter else {}
    total = await db.correction_suggestions.count_documents(query)
    items = await (
        db.correction_suggestions.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.patch("/{suggestion_id}", response_model=dict)
async def review_correction_suggestion(
    suggestion_id: str,
    data: CorrectionSuggestionReview,
    user: dict = Depends(require_editor),
):
    if data.status == CorrectionSuggestionStatus.NEW:
        raise HTTPException(status_code=422, detail="Вернуть предложение в статус «Новое» нельзя")

    now = datetime.now(timezone.utc).isoformat()
    changes = {
        "status": data.status.value,
        "admin_comment": data.admin_comment or None,
        "reviewed_by": user["_id"],
        "reviewed_at": now,
        "updated_at": now,
    }
    collection = (await get_db()).correction_suggestions
    result = await collection.update_one(
        {"_id": suggestion_id, "status": {"$in": ["new", "in_review"]}},
        {"$set": changes},
    )
    if result.matched_count == 0:
        existing = await collection.find_one({"_id": suggestion_id}, {"status": 1})
        if not existing:
            raise HTTPException(status_code=404, detail="Предложение не найдено")
        raise HTTPException(status_code=409, detail="Предложение уже обработано")
    return {"id": suggestion_id, "status": data.status.value}
