"""Tags management routes"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone

from models.user import Tag, TagCreate
from utils.database import get_db
from utils.slugify import generate_slug

router = APIRouter(prefix="/tags", tags=["tags"])


@router.post("", response_model=dict)
async def create_tag(data: TagCreate):
    """Create a new tag"""
    db = await get_db()
    
    slug = data.slug or generate_slug(data.name)
    
    existing = await db.tags.find_one({"$or": [{"name": data.name}, {"slug": slug}]})
    if existing:
        raise HTTPException(status_code=400, detail="Тег уже существует")
    
    tag = Tag(
        name=data.name,
        slug=slug
    )
    
    doc = tag.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    
    await db.tags.insert_one(doc)
    return {"id": doc["_id"], "name": tag.name, "slug": tag.slug}


@router.get("", response_model=dict)
async def list_tags(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = None,
    sort_by: str = Query("usage", regex="^(usage|name|created)$")
):
    """List all tags"""
    db = await get_db()
    
    query = {}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    
    sort_field = {
        "usage": ("usage_count", -1),
        "name": ("name", 1),
        "created": ("created_at", -1)
    }.get(sort_by, ("usage_count", -1))
    
    total = await db.tags.count_documents(query)
    cursor = db.tags.find(query).skip(skip).limit(limit).sort(*sort_field)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/popular", response_model=list)
async def get_popular_tags(limit: int = Query(20, ge=1, le=100)):
    """Get most popular tags"""
    db = await get_db()
    
    cursor = db.tags.find().sort("usage_count", -1).limit(limit)
    items = await cursor.to_list(limit)
    
    return items


@router.get("/{id_or_slug}", response_model=dict)
async def get_tag(id_or_slug: str):
    """Get tag by ID or slug"""
    db = await get_db()
    
    query = {"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}
    tag = await db.tags.find_one(query)
    
    if not tag:
        raise HTTPException(status_code=404, detail="Тег не найден")
    
    return tag


@router.put("/{id}", response_model=dict)
async def update_tag(id: str, data: TagCreate):
    """Update tag"""
    db = await get_db()
    
    slug = data.slug or generate_slug(data.name)
    
    # Check uniqueness
    existing = await db.tags.find_one({
        "$or": [{"name": data.name}, {"slug": slug}],
        "_id": {"$ne": id}
    })
    if existing:
        raise HTTPException(status_code=400, detail="Тег с таким именем уже существует")
    
    result = await db.tags.update_one(
        {"_id": id},
        {"$set": {"name": data.name, "slug": slug}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Тег не найден")
    
    return {"id": id, "updated": True}


@router.delete("/{id}")
async def delete_tag(id: str):
    """Delete tag"""
    db = await get_db()
    
    result = await db.tags.delete_one({"_id": id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Тег не найден")
    
    return {"id": id, "deleted": True}


@router.post("/update-counts")
async def update_tag_counts():
    """Recalculate tag usage counts (admin task)"""
    db = await get_db()
    
    # Get all tags
    tags = await db.tags.find().to_list(10000)
    
    collections = ["people", "teams", "shows", "articles", "news", "quizzes", "wiki"]
    
    for tag in tags:
        count = 0
        for coll_name in collections:
            coll = db[coll_name]
            count += await coll.count_documents({"tags": tag["name"]})
        
        await db.tags.update_one(
            {"_id": tag["_id"]},
            {"$set": {"usage_count": count}}
        )
    
    return {"updated": len(tags)}
