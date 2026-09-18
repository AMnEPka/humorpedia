"""Poll CRUD, public state and authenticated voting."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from models.poll import Poll, PollCreate, PollUpdate, PollVoteCreate
from services.polls import poll_for_public, record_vote
from utils.auth import get_current_user, require_editor, require_user
from utils.database import get_db

router = APIRouter(prefix="/polls", tags=["polls"])


@router.get("", dependencies=[Depends(require_editor)])
@router.get("/", dependencies=[Depends(require_editor)])
async def list_polls(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
):
    response.headers["Cache-Control"] = "private, no-store"
    db = await get_db()
    query = {"status": status} if status else {}
    items = await db.polls.find(query).sort("updated_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"items": items, "total": await db.polls.count_documents(query)}


@router.post("", dependencies=[Depends(require_editor)])
@router.post("/", dependencies=[Depends(require_editor)])
async def create_poll(data: PollCreate):
    db = await get_db()
    poll = Poll(**data.model_dump()).model_dump(by_alias=True)
    poll["created_at"] = poll["created_at"].isoformat()
    poll["updated_at"] = poll["updated_at"].isoformat()
    await db.polls.insert_one(poll)
    return {"id": poll["_id"]}


@router.get("/{poll_id}")
async def get_poll(poll_id: str, request: Request, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    return await poll_for_public(await get_db(), poll_id, await get_current_user(request))


@router.get("/{poll_id}/edit", dependencies=[Depends(require_editor)])
async def get_poll_for_edit(poll_id: str, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    poll = await (await get_db()).polls.find_one({"_id": poll_id})
    if not poll:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    return poll


@router.put("/{poll_id}", dependencies=[Depends(require_editor)])
async def update_poll(poll_id: str, data: PollUpdate):
    db = await get_db()
    current = await db.polls.find_one({"_id": poll_id})
    if not current:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    changes = data.model_dump(exclude_unset=True)
    if "options" in changes:
        used = await db.poll_votes.distinct("option_id", {"poll_id": poll_id})
        historical = {
            str(option.get("id")) for option in current.get("options") or []
            if int(option.get("historical_votes") or 0) > 0
        }
        removed = (set(map(str, used)) | historical) - {str(option["id"]) for option in changes["options"]}
        if removed:
            raise HTTPException(status_code=409, detail="Нельзя удалить вариант, за который уже голосовали")
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.polls.update_one({"_id": poll_id}, {"$set": changes})
    return {"id": poll_id, "updated": True}


@router.delete("/{poll_id}", dependencies=[Depends(require_editor)])
async def archive_poll(poll_id: str):
    result = await (await get_db()).polls.update_one(
        {"_id": poll_id},
        {"$set": {"status": "archived", "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    return {"id": poll_id, "archived": True}


@router.post("/{poll_id}/vote")
async def vote(poll_id: str, data: PollVoteCreate, user: dict = Depends(require_user)):
    if "vote" not in (user.get("permissions") or []):
        raise HTTPException(status_code=403, detail="Голосование недоступно для этого аккаунта")
    return await record_vote(await get_db(), poll_id, str(user["_id"]), data.option_id)
