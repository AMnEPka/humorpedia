"""Comments management routes"""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional
from datetime import datetime, timezone

from models.user import Comment, CommentCreate, CommentUpdate
from utils.database import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/comments", tags=["comments"])


@router.post("", response_model=dict)
async def create_comment(data: CommentCreate, request: Request):
    """Create a new comment"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    
    if user.get("banned"):
        raise HTTPException(status_code=403, detail="Вы заблокированы")
    
    db = await get_db()
    
    # Calculate level if reply
    level = 0
    if data.parent_id:
        parent = await db.comments.find_one({"_id": data.parent_id})
        if parent:
            level = parent.get("level", 0) + 1
    
    comment = Comment(
        resource_type=data.resource_type,
        resource_id=data.resource_id,
        user_id=user["_id"],
        author_name=user.get("username", "Аноним"),
        author_avatar=user.get("profile", {}).get("avatar"),
        text=data.text,
        parent_id=data.parent_id,
        level=level
    )
    
    doc = comment.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    await db.comments.insert_one(doc)
    
    # Update comments count on resource
    collection_map = {
        "person": "people",
        "team": "teams",
        "show": "shows",
        "article": "articles",
        "news": "news",
        "quiz": "quizzes",
        "wiki": "wiki"
    }
    
    if data.resource_type in collection_map:
        coll = db[collection_map[data.resource_type]]
        await coll.update_one(
            {"_id": data.resource_id},
            {"$inc": {"comments_count": 1}}
        )
    
    # Update user stats
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$inc": {"stats.comments_count": 1}}
    )
    
    return {"id": doc["_id"], "created": True}


@router.get("", response_model=dict)
async def list_comments(
    resource_type: str,
    resource_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """Get comments for a resource"""
    db = await get_db()
    
    query = {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "deleted": False,
        "approved": True
    }
    
    total = await db.comments.count_documents(query)
    cursor = db.comments.find(query).skip(skip).limit(limit).sort("created_at", 1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/recent", response_model=list)
async def recent_comments(limit: int = Query(10, ge=1, le=50)):
    """Get recent comments across all content"""
    db = await get_db()
    
    cursor = db.comments.find(
        {"deleted": False, "approved": True}
    ).sort("created_at", -1).limit(limit)
    
    return await cursor.to_list(limit)


@router.put("/{comment_id}", response_model=dict)
async def update_comment(comment_id: str, data: CommentUpdate, request: Request):
    """Update own comment"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    
    db = await get_db()
    
    comment = await db.comments.find_one({"_id": comment_id})
    if not comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")
    
    # Only author or admin can edit
    if comment["user_id"] != user["_id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Нет прав на редактирование")
    
    await db.comments.update_one(
        {"_id": comment_id},
        {"$set": {
            "text": data.text,
            "edited": True,
            "edited_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"id": comment_id, "updated": True}


@router.delete("/{comment_id}")
async def delete_comment(comment_id: str, request: Request):
    """Delete own comment (soft delete)"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    
    db = await get_db()
    
    comment = await db.comments.find_one({"_id": comment_id})
    if not comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")
    
    # Only author or admin can delete
    if comment["user_id"] != user["_id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Нет прав на удаление")
    
    await db.comments.update_one(
        {"_id": comment_id},
        {"$set": {"deleted": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Update comments count on resource
    collection_map = {
        "person": "people",
        "team": "teams",
        "show": "shows",
        "article": "articles",
        "news": "news",
        "quiz": "quizzes",
        "wiki": "wiki"
    }
    
    if comment["resource_type"] in collection_map:
        coll = db[collection_map[comment["resource_type"]]]
        await coll.update_one(
            {"_id": comment["resource_id"]},
            {"$inc": {"comments_count": -1}}
        )
    
    return {"id": comment_id, "deleted": True}


@router.post("/{comment_id}/like")
async def like_comment(comment_id: str, request: Request):
    """Like a comment"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    
    db = await get_db()
    
    result = await db.comments.update_one(
        {"_id": comment_id},
        {"$inc": {"likes": 1}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Комментарий не найден")
    
    return {"id": comment_id, "liked": True}


# === MODERATION ===

@router.get("/pending", response_model=dict)
async def list_pending_comments(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """List comments pending moderation"""
    user = await get_current_user(request)
    if not user or user.get("role") not in ["admin", "moderator"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    db = await get_db()
    
    query = {"approved": False, "deleted": False}
    
    total = await db.comments.count_documents(query)
    cursor = db.comments.find(query).skip(skip).limit(limit).sort("created_at", 1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/{comment_id}/approve")
async def approve_comment(comment_id: str, request: Request):
    """Approve a comment"""
    user = await get_current_user(request)
    if not user or user.get("role") not in ["admin", "moderator"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    db = await get_db()
    
    result = await db.comments.update_one(
        {"_id": comment_id},
        {"$set": {"approved": True}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Комментарий не найден")
    
    return {"id": comment_id, "approved": True}


@router.post("/{comment_id}/reject")
async def reject_comment(comment_id: str, request: Request):
    """Reject and delete a comment"""
    user = await get_current_user(request)
    if not user or user.get("role") not in ["admin", "moderator"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    db = await get_db()
    
    result = await db.comments.update_one(
        {"_id": comment_id},
        {"$set": {"deleted": True}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Комментарий не найден")
    
    return {"id": comment_id, "rejected": True}
