"""User management routes"""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from datetime import datetime, timezone

from models.user import User, UserUpdate, UserAdminUpdate, UserRole
from utils.database import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


async def require_admin(request: Request):
    """Require admin role"""
    user = await get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user


async def require_moderator(request: Request):
    """Require moderator or admin role"""
    user = await get_current_user(request)
    if not user or user.get("role") not in ["admin", "moderator", "editor"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return user


@router.get("", response_model=dict)
async def list_users(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    role: Optional[str] = None,
    search: Optional[str] = None,
    banned: Optional[bool] = None
):
    """List users (admin only)"""
    await require_admin(request)
    
    db = await get_db()
    
    query = {}
    if role:
        query["role"] = role
    if search:
        query["$or"] = [
            {"username": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    if banned is not None:
        query["banned"] = banned
    
    total = await db.users.count_documents(query)
    cursor = db.users.find(
        query,
        {"password_hash": 0}  # Exclude password
    ).skip(skip).limit(limit).sort("created_at", -1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{user_id}", response_model=dict)
async def get_user(user_id: str, request: Request):
    """Get user by ID (admin only)"""
    await require_admin(request)
    
    db = await get_db()
    user = await db.users.find_one({"_id": user_id}, {"password_hash": 0})
    
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return user


@router.put("/me", response_model=dict)
async def update_me(data: UserUpdate, request: Request):
    """Update current user profile"""
    current_user = await get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    db = await get_db()
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    
    # Check username uniqueness
    if "username" in update_data:
        existing = await db.users.find_one({
            "username": update_data["username"],
            "_id": {"$ne": current_user["_id"]}
        })
        if existing:
            raise HTTPException(status_code=400, detail="Имя пользователя занято")
    
    # Check email uniqueness
    if "email" in update_data:
        existing = await db.users.find_one({
            "email": update_data["email"],
            "_id": {"$ne": current_user["_id"]}
        })
        if existing:
            raise HTTPException(status_code=400, detail="Email уже используется")
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.users.update_one({"_id": current_user["_id"]}, {"$set": update_data})
    
    return {"id": current_user["_id"], "updated": True}


@router.put("/{user_id}", response_model=dict)
async def admin_update_user(user_id: str, data: UserAdminUpdate, request: Request):
    """Update user (admin only)"""
    await require_admin(request)
    
    db = await get_db()
    
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.users.update_one({"_id": user_id}, {"$set": update_data})
    
    return {"id": user_id, "updated": True}


@router.post("/{user_id}/ban", response_model=dict)
async def ban_user(user_id: str, request: Request):
    """Ban user (admin only)"""
    await require_admin(request)
    
    db = await get_db()
    
    result = await db.users.update_one(
        {"_id": user_id},
        {"$set": {"banned": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return {"id": user_id, "banned": True}


@router.post("/{user_id}/unban", response_model=dict)
async def unban_user(user_id: str, request: Request):
    """Unban user (admin only)"""
    await require_admin(request)
    
    db = await get_db()
    
    result = await db.users.update_one(
        {"_id": user_id},
        {"$set": {"banned": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return {"id": user_id, "banned": False}


@router.delete("/{user_id}", response_model=dict)
async def delete_user(user_id: str, request: Request):
    """Delete user (admin only)"""
    await require_admin(request)
    
    db = await get_db()
    
    result = await db.users.delete_one({"_id": user_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return {"id": user_id, "deleted": True}
