"""Cities API routes - CRUD for geography/cities"""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

from models.base import ContentStatus
from models.city import City, CityCreate, CityUpdate
from utils.database import get_db
from services.tags import tag_service

router = APIRouter(prefix="/cities", tags=["cities"])


# === HELPER FUNCTIONS ===

async def check_slug_unique(slug: str, exclude_id: str = None):
    """Check if slug is unique in cities collection"""
    db = await get_db()
    query = {"slug": slug}
    if exclude_id:
        query["_id"] = {"$ne": exclude_id}
    existing = await db.cities.find_one(query)
    if existing:
        raise HTTPException(status_code=400, detail="City with this slug already exists")


# === CRUD ENDPOINTS ===

@router.post("/", response_model=dict)
async def create_city(data: CityCreate, request: Request):
    """Create a new city"""
    db = request.app.state.db
    
    # Check slug uniqueness
    existing = await db.cities.find_one({"slug": data.slug})
    if existing:
        raise HTTPException(status_code=400, detail="City with this slug already exists")
    
    city = City(
        title=data.title,
        slug=data.slug,
        name=data.name,
        poster=data.poster,
        description=data.description,
        facts=data.facts or {},
        facts_order=data.facts_order or [],
        modules=data.modules,
        tags=data.tags,
        seo=data.seo or {},
        status=data.status,
        related_person_ids=data.related_person_ids or [],
        related_team_ids=data.related_team_ids or []
    )
    
    doc = city.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    # Sync tags
    if data.tags:
        await tag_service.sync_tags(data.tags)
    
    await db.cities.insert_one(doc)
    
    return {"id": doc["_id"], "slug": doc["slug"]}


@router.get("/", response_model=dict)
async def list_cities(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[ContentStatus] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    letter: Optional[str] = None,
    sort_by: str = Query("title", enum=["title", "created_at", "views", "rating"]),
    sort_order: int = Query(1, ge=-1, le=1)
):
    """List cities with pagination and filters"""
    db = request.app.state.db
    
    query = {}
    
    if status:
        query["status"] = status.value
    if tag:
        query["tags"] = tag
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    if letter:
        query["title"] = {"$regex": f"^{letter}", "$options": "i"}
    
    total = await db.cities.count_documents(query)
    
    # Sort order
    sort_dir = 1 if sort_order >= 0 else -1
    cursor = db.cities.find(query, {"modules": 0}).skip(skip).limit(limit).sort(sort_by, sort_dir)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{id_or_slug}", response_model=dict)
async def get_city(id_or_slug: str, request: Request, increment_views: bool = True):
    """Get city by ID or slug"""
    db = request.app.state.db
    
    # Try to find by ID or slug
    city = await db.cities.find_one({"_id": id_or_slug})
    if not city:
        city = await db.cities.find_one({"slug": id_or_slug})
    
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    
    # Increment views
    if increment_views:
        await db.cities.update_one({"_id": city["_id"]}, {"$inc": {"views": 1}})
    
    return city


@router.put("/{id}", response_model=dict)
async def update_city(id: str, data: CityUpdate, request: Request):
    """Update city"""
    db = request.app.state.db
    
    # Check if city exists
    city = await db.cities.find_one({"_id": id})
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    
    # Check slug uniqueness if changing
    if data.slug and data.slug != city.get("slug"):
        existing = await db.cities.find_one({"slug": data.slug, "_id": {"$ne": id}})
        if existing:
            raise HTTPException(status_code=400, detail="City with this slug already exists")
    
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Sync tags
    if data.tags:
        await tag_service.sync_tags(data.tags)
    
    result = await db.cities.update_one({"_id": id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="City not found")
    
    return {"id": id, "updated": True}


@router.delete("/{id}")
async def delete_city(id: str, request: Request):
    """Delete city"""
    db = request.app.state.db
    
    result = await db.cities.delete_one({"_id": id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="City not found")
    
    return {"id": id, "deleted": True}


@router.get("/{city_id}/related-people", response_model=dict)
async def get_city_related_people(
    city_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100)
):
    """Get people related to a city"""
    db = request.app.state.db
    
    city = await db.cities.find_one({"_id": city_id})
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    
    person_ids = city.get("related_person_ids", [])
    if not person_ids:
        return {"items": [], "total": 0}
    
    people = await db.people.find(
        {"_id": {"$in": person_ids}},
        {"modules": 0}
    ).limit(limit).to_list(limit)
    
    return {"items": people, "total": len(people)}


@router.get("/{city_id}/related-teams", response_model=dict)
async def get_city_related_teams(
    city_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100)
):
    """Get teams related to a city"""
    db = request.app.state.db
    
    city = await db.cities.find_one({"_id": city_id})
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    
    team_ids = city.get("related_team_ids", [])
    if not team_ids:
        return {"items": [], "total": 0}
    
    teams = await db.teams.find(
        {"_id": {"$in": team_ids}},
        {"modules": 0}
    ).limit(limit).to_list(limit)
    
    return {"items": teams, "total": len(teams)}



# === LINKING ENDPOINTS ===

@router.post("/link-all", response_model=dict)
async def link_all_cities_endpoint(request: Request):
    """
    Связывает все города с людьми и командами на основе:
    - Люди: facts["Место рождения"] совпадает с названием города
    - Команды: facts["Город"] совпадает с названием города
    
    Рекомендуется запускать после импорта данных или периодически.
    """
    from services.city_linking import link_all_cities
    
    db = request.app.state.db
    result = await link_all_cities(db)
    
    return result


@router.post("/{city_id}/link", response_model=dict)
async def link_city_endpoint(city_id: str, request: Request):
    """
    Связывает конкретный город с людьми и командами.
    """
    from services.city_linking import link_city
    
    db = request.app.state.db
    result = await link_city(db, city_id)
    
    return result
