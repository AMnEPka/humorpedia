"""Sections/Projects API routes - hierarchical content structure"""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional, List
from datetime import datetime, timezone

from models.section import Section, SectionCreate, SectionUpdate, SectionTree
from models.base import ContentStatus
from utils.database import get_db
from services.tags import tag_service

router = APIRouter(prefix="/sections", tags=["sections"])


async def build_full_path(parent_id: Optional[str], slug: str, db) -> tuple[str, int]:
    """
    Build full path and calculate level for a section based on parent.
    Returns: (full_path, level)
    """
    if not parent_id:
        return f"/{slug}", 0
    
    parent = await db.sections.find_one({"_id": parent_id})
    if not parent:
        raise HTTPException(status_code=404, detail="Parent section not found")
    
    parent_path = parent.get("full_path", "")
    parent_level = parent.get("level", 0)
    
    return f"{parent_path}/{slug}", parent_level + 1


async def update_children_paths(section_id: str, new_path: str, db):
    """
    Recursively update full_path for all children when parent path changes.
    """
    children = await db.sections.find({"parent_id": section_id}).to_list(1000)
    
    for child in children:
        child_slug = child["slug"]
        child_full_path = f"{new_path}/{child_slug}"
        
        await db.sections.update_one(
            {"_id": child["_id"]},
            {"$set": {"full_path": child_full_path, "parent_path": new_path}}
        )
        
        # Recursively update grandchildren
        await update_children_paths(child["_id"], child_full_path, db)


async def check_circular_reference(section_id: str, new_parent_id: Optional[str], db) -> bool:
    """
    Check if setting new_parent_id would create a circular reference.
    Returns True if circular, False if safe.
    """
    if not new_parent_id:
        return False
    
    if section_id == new_parent_id:
        return True
    
    # Traverse up the parent chain
    current_id = new_parent_id
    visited = set()
    
    while current_id:
        if current_id in visited:
            return True  # Circular reference detected
        
        if current_id == section_id:
            return True  # Would create a loop
        
        visited.add(current_id)
        parent = await db.sections.find_one({"_id": current_id})
        
        if not parent:
            break
        
        current_id = parent.get("parent_id")
    
    return False


@router.post("/", response_model=dict)
async def create_section(data: SectionCreate, request: Request):
    """Create a new section"""
    db = request.app.state.db
    
    # Check slug uniqueness at the same level
    if data.parent_id:
        existing = await db.sections.find_one({
            "slug": data.slug,
            "parent_id": data.parent_id
        })
    else:
        existing = await db.sections.find_one({
            "slug": data.slug,
            "parent_id": None
        })
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Section with this slug already exists at this level"
        )
    
    # Build full path
    full_path, level = await build_full_path(data.parent_id, data.slug, db)
    
    # Get parent path for breadcrumbs
    parent_path = None
    if data.parent_id:
        parent = await db.sections.find_one({"_id": data.parent_id})
        parent_path = parent.get("full_path") if parent else None
    
    # Create section
    section = Section(
        title=data.title,
        slug=data.slug,
        full_path=full_path,
        description=data.description,
        cover_image=data.cover_image,
        parent_id=data.parent_id,
        parent_path=parent_path,
        level=level,
        order=data.order,
        in_main_menu=data.in_main_menu,
        menu_title=data.menu_title,
        modules=data.modules,
        child_types=data.child_types,
        show_children_list=data.show_children_list,
        seo=data.seo or {},
        tags=data.tags,
        status=data.status
    )
    
    doc = section.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    # Sync tags
    if data.tags:
        await tag_service.sync_tags(data.tags)
    
    await db.sections.insert_one(doc)
    
    return {"id": doc["_id"], "slug": doc["slug"], "full_path": full_path}


@router.get("/", response_model=dict)
async def list_sections(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    parent_id: Optional[str] = None,
    level: Optional[int] = None,
    status: Optional[ContentStatus] = None,
    in_main_menu: Optional[bool] = None,
    search: Optional[str] = None
):
    """List sections with pagination and filters"""
    db = request.app.state.db
    
    query = {}
    
    if parent_id is not None:
        if parent_id == "null" or parent_id == "":
            query["parent_id"] = None
        else:
            query["parent_id"] = parent_id
    
    if level is not None:
        query["level"] = level
    
    if status:
        query["status"] = status.value
    
    if in_main_menu is not None:
        query["in_main_menu"] = in_main_menu
    
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    
    total = await db.sections.count_documents(query)
    cursor = db.sections.find(query, {"modules": 0}).skip(skip).limit(limit).sort("order", 1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/tree", response_model=List[SectionTree])
async def get_sections_tree(request: Request, status: Optional[ContentStatus] = None):
    """Get hierarchical tree of all sections"""
    db = request.app.state.db
    
    query = {}
    if status:
        query["status"] = status.value
    
    # Get all sections
    all_sections = await db.sections.find(query).sort("order", 1).to_list(1000)
    
    # Build tree structure
    sections_map = {}
    root_sections = []
    
    # First pass: create map
    for section in all_sections:
        section_tree = SectionTree(
            id=section["_id"],
            title=section["title"],
            slug=section["slug"],
            full_path=section["full_path"],
            level=section["level"],
            order=section.get("order", 0),
            status=section["status"],
            in_main_menu=section.get("in_main_menu", False),
            children=[]
        )
        sections_map[section["_id"]] = section_tree
        
        if not section.get("parent_id"):
            root_sections.append(section_tree)
    
    # Second pass: build hierarchy
    for section in all_sections:
        parent_id = section.get("parent_id")
        if parent_id and parent_id in sections_map:
            sections_map[parent_id].children.append(sections_map[section["_id"]])
    
    return root_sections


@router.get("/{id_or_slug}", response_model=dict)
async def get_section(id_or_slug: str, request: Request, increment_views: bool = True):
    """Get section by ID, slug, or full path"""
    db = request.app.state.db
    
    # Try to find by ID, slug, or full_path
    section = await db.sections.find_one({"_id": id_or_slug})
    if not section:
        section = await db.sections.find_one({"slug": id_or_slug})
    if not section:
        section = await db.sections.find_one({"full_path": f"/{id_or_slug}"})
    if not section:
        section = await db.sections.find_one({"full_path": id_or_slug})
    
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Increment views
    if increment_views:
        await db.sections.update_one({"_id": section["_id"]}, {"$inc": {"views": 1}})
    
    # Get children count
    children_count = await db.sections.count_documents({"parent_id": section["_id"]})
    section["children_count"] = children_count
    
    # Get breadcrumbs
    breadcrumbs = []
    if section.get("parent_id"):
        current_parent_id = section["parent_id"]
        while current_parent_id:
            parent = await db.sections.find_one({"_id": current_parent_id})
            if parent:
                breadcrumbs.insert(0, {
                    "id": parent["_id"],
                    "title": parent["title"],
                    "full_path": parent["full_path"]
                })
                current_parent_id = parent.get("parent_id")
            else:
                break
    
    section["breadcrumbs"] = breadcrumbs
    
    return section


@router.get("/{section_id}/children", response_model=dict)
async def get_section_children(
    section_id: str,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[ContentStatus] = None
):
    """Get all direct children of a section"""
    db = request.app.state.db
    
    # Verify parent exists
    parent = await db.sections.find_one({"_id": section_id})
    if not parent:
        raise HTTPException(status_code=404, detail="Section not found")
    
    query = {"parent_id": section_id}
    if status:
        query["status"] = status.value
    
    total = await db.sections.count_documents(query)
    cursor = db.sections.find(query, {"modules": 0}).skip(skip).limit(limit).sort("order", 1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "parent": {
            "id": parent["_id"],
            "title": parent["title"],
            "full_path": parent["full_path"]
        }
    }


@router.put("/{id}", response_model=dict)
async def update_section(id: str, data: SectionUpdate, request: Request):
    """Update section"""
    db = request.app.state.db
    
    # Check if section exists
    section = await db.sections.find_one({"_id": id})
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Check for circular reference if parent_id is being changed
    if "parent_id" in update_data:
        is_circular = await check_circular_reference(id, update_data["parent_id"], db)
        if is_circular:
            raise HTTPException(
                status_code=400,
                detail="Cannot set parent: would create circular reference"
            )
        
        # Rebuild full path if parent or slug changed
        new_slug = update_data.get("slug", section["slug"])
        new_parent_id = update_data.get("parent_id")
        
        new_full_path, new_level = await build_full_path(new_parent_id, new_slug, db)
        update_data["full_path"] = new_full_path
        update_data["level"] = new_level
        
        # Update parent_path
        if new_parent_id:
            parent = await db.sections.find_one({"_id": new_parent_id})
            update_data["parent_path"] = parent.get("full_path") if parent else None
        else:
            update_data["parent_path"] = None
        
        # Update all children paths
        await update_children_paths(id, new_full_path, db)
    
    elif "slug" in update_data:
        # Just slug changed, rebuild path
        new_slug = update_data["slug"]
        parent_id = section.get("parent_id")
        
        new_full_path, new_level = await build_full_path(parent_id, new_slug, db)
        update_data["full_path"] = new_full_path
        update_data["level"] = new_level
        
        # Update children paths
        await update_children_paths(id, new_full_path, db)
    
    # Sync tags
    if data.tags:
        await tag_service.sync_tags(data.tags)
    
    result = await db.sections.update_one({"_id": id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Section not found")
    
    return {"id": id, "updated": True}


@router.delete("/{id}")
async def delete_section(id: str, request: Request, cascade: bool = Query(False)):
    """
    Delete section. 
    If cascade=True, deletes all children recursively.
    If cascade=False and section has children, returns error.
    """
    db = request.app.state.db
    
    # Check if section exists
    section = await db.sections.find_one({"_id": id})
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Check for children
    children_count = await db.sections.count_documents({"parent_id": id})
    
    if children_count > 0 and not cascade:
        raise HTTPException(
            status_code=400,
            detail=f"Section has {children_count} children. Use cascade=true to delete all."
        )
    
    if cascade and children_count > 0:
        # Recursively delete all children
        children = await db.sections.find({"parent_id": id}).to_list(1000)
        for child in children:
            await delete_section(child["_id"], request, cascade=True)
    
    # Delete the section
    result = await db.sections.delete_one({"_id": id})
    
    return {"id": id, "deleted": True, "cascaded": cascade}


@router.get("/path/{path:path}", response_model=dict)
async def get_section_by_path(path: str, request: Request):
    """Get section by full path (e.g., /kvn/vysshaya-liga/2005)"""
    db = request.app.state.db
    
    # Normalize path
    if not path.startswith("/"):
        path = f"/{path}"
    
    section = await db.sections.find_one({"full_path": path})
    
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Increment views
    await db.sections.update_one({"_id": section["_id"]}, {"$inc": {"views": 1}})
    
    # Get children count
    children_count = await db.sections.count_documents({"parent_id": section["_id"]})
    section["children_count"] = children_count
    
    # Get breadcrumbs
    breadcrumbs = []
    if section.get("parent_id"):
        current_parent_id = section["parent_id"]
        while current_parent_id:
            parent = await db.sections.find_one({"_id": current_parent_id})
            if parent:
                breadcrumbs.insert(0, {
                    "id": parent["_id"],
                    "title": parent["title"],
                    "full_path": parent["full_path"]
                })
                current_parent_id = parent.get("parent_id")
            else:
                break
    
    section["breadcrumbs"] = breadcrumbs
    
    return section
