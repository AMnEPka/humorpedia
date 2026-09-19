"""
Universal CRUD helpers for content routes.

All content types share these functions for consistent
create / read / update / delete / list / slug operations.
"""
from fastapi import HTTPException
from typing import Optional
from datetime import datetime, timezone
import logging
import re

from utils.database import get_db
from utils.search import literal_search_pattern
from services.tags import tag_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Slug helpers
# ---------------------------------------------------------------------------

async def check_slug_unique(collection_name: str, slug: str, exclude_id: str = None):
    """Check if slug is unique in collection"""
    db = await get_db()
    collection = getattr(db, collection_name)
    query = {"slug": slug}
    if exclude_id:
        # For KVN, exclude by 'id' field (UUID) or _id
        if collection_name == "kvn":
            doc = await collection.find_one({"id": exclude_id})
            if not doc:
                doc = await collection.find_one({"_id": exclude_id})
            if doc:
                query["_id"] = {"$ne": doc["_id"]}
        else:
            query["_id"] = {"$ne": exclude_id}
    existing = await collection.find_one(query)
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")


async def generate_unique_slug(collection_name: str, base_slug: str, parent_path: str = None) -> str:
    """
    Generate unique slug by appending _1, _2, etc. if needed.
    For hierarchical content (KVN, sections), also checks full_path uniqueness.
    """
    db = await get_db()
    collection = getattr(db, collection_name)

    async def is_slug_unique(slug_to_check: str, expected_full_path: str = None) -> bool:
        existing_by_slug = await collection.find_one({"slug": slug_to_check})
        if existing_by_slug:
            return False
        if expected_full_path:
            existing_by_path = await collection.find_one({"full_path": expected_full_path})
            if existing_by_path:
                return False
        return True

    expected_full_path = f"{parent_path}/{base_slug}" if parent_path else base_slug
    if await is_slug_unique(base_slug, expected_full_path):
        return base_slug

    counter = 1
    while True:
        new_slug = f"{base_slug}_{counter}"
        expected_full_path = f"{parent_path}/{new_slug}" if parent_path else new_slug
        if await is_slug_unique(new_slug, expected_full_path):
            return new_slug
        counter += 1
        if counter > 1000:
            raise HTTPException(status_code=500, detail="Could not generate unique slug")


# ---------------------------------------------------------------------------
#  Primary-tag helpers (People / Teams)
# ---------------------------------------------------------------------------

async def sync_primary_tag_to_tags(doc: dict) -> dict:
    """
    Automatically add primary_tag to the tags list if missing (case-insensitive).
    Modifies doc in place and returns the updated tags list.
    """
    primary_tag = doc.get("primary_tag")
    if not primary_tag:
        return doc.get("tags", [])

    tags = doc.get("tags", [])
    tag_exists = any(tag.lower() == primary_tag.lower() for tag in tags)
    if not tag_exists:
        tags.append(primary_tag)
        doc["tags"] = tags
    return tags


async def check_primary_tag_duplicate(
    collection_name: str,
    primary_tag: Optional[str],
    exclude_id: str = None
) -> None:
    """Raise 400 if primary_tag is already taken by another person/team (case-insensitive)."""
    if not primary_tag:
        return
    if collection_name not in ["people", "teams"]:
        return

    db = await get_db()
    collection = getattr(db, collection_name)
    query = {"primary_tag": {"$regex": f"^{re.escape(primary_tag)}$", "$options": "i"}}
    if exclude_id:
        query["_id"] = {"$ne": exclude_id}

    existing = await collection.find_one(query)
    if existing:
        item_name = existing.get("full_name") or existing.get("name") or existing.get("title", "Неизвестно")
        item_type = "человека" if collection_name == "people" else "команды"
        raise HTTPException(
            status_code=400,
            detail=f"Базовый тег '{primary_tag}' уже используется {item_type} '{item_name}'. "
                   f"Пожалуйста, выберите уникальный тег (например, '{primary_tag} (команда X)')."
        )


async def update_tags_everywhere(
    db, old_primary_tag: Optional[str], new_primary_tag: Optional[str]
):
    """Replace old_primary_tag with new_primary_tag across all collections' tags arrays."""
    if old_primary_tag == new_primary_tag:
        return
    if not old_primary_tag:
        return

    collections_with_tags = [
        "people", "teams", "shows", "articles", "news",
        "quizzes", "wiki", "kvn"
    ]
    total_updated = 0

    for collection_name in collections_with_tags:
        collection = getattr(db, collection_name)
        documents = await collection.find({
            "tags": {"$regex": f"^{re.escape(old_primary_tag)}$", "$options": "i"}
        }).to_list(None)

        updated_in_collection = 0
        for doc in documents:
            doc_id = doc.get("_id")
            tags = doc.get("tags", [])
            updated_tags = []
            tag_updated = False

            for tag in tags:
                if tag.lower() == old_primary_tag.lower():
                    tag_updated = True
                    if new_primary_tag:
                        tag_exists = any(t.lower() == new_primary_tag.lower() for t in updated_tags)
                        if not tag_exists:
                            updated_tags.append(new_primary_tag)
                    continue
                updated_tags.append(tag)

            if tag_updated:
                if collection_name == "kvn":
                    sorted_tags = sorted(updated_tags, key=lambda x: (0 if x == "КВН" else 1, x.lower()))
                else:
                    sorted_tags = updated_tags

                await collection.update_one(
                    {"_id": doc_id},
                    {"$set": {"tags": sorted_tags, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                await tag_service.sync_tags(sorted_tags)
                updated_in_collection += 1

        if updated_in_collection > 0:
            logger.info(f"Обновлено {updated_in_collection} документов в коллекции {collection_name}")
            total_updated += updated_in_collection

    if total_updated > 0:
        logger.info(f"Всего обновлено {total_updated} документов при замене тега '{old_primary_tag}' на '{new_primary_tag}'")


# ---------------------------------------------------------------------------
#  Query builder
# ---------------------------------------------------------------------------

OTHER_ALPHABET_FILTER = "other"
CYRILLIC_ALPHABET_RANGES = "\u0400-\u052F\u2DE0-\u2DFF\uA640-\uA69F"


def alphabet_letter_pattern(letter: str) -> str:
    """Return a first-character filter, including one group for all non-Cyrillic names."""
    if letter == OTHER_ALPHABET_FILTER:
        return rf"^\s*[^{CYRILLIC_ALPHABET_RANGES}]"
    return f"^{re.escape(letter)}"


def build_query(
    status=None,
    tag: str = None,
    search: str = None,
    search_fields: list = None,
    letter: str = None,
    letter_field: str = "title",
    extra: dict = None
) -> dict:
    """Build MongoDB query from common filters."""
    query = {}
    if status:
        query["status"] = status.value if hasattr(status, "value") else status
    if tag:
        query["tags"] = tag
    if search and search_fields:
        search_pattern = literal_search_pattern(search)
        query["$or"] = [{f: {"$regex": search_pattern, "$options": "i"}} for f in search_fields]
    if letter:
        query[letter_field] = {"$regex": alphabet_letter_pattern(letter), "$options": "i"}
    if extra:
        query.update(extra)
    return query


# ---------------------------------------------------------------------------
#  Serialization
# ---------------------------------------------------------------------------

def convert_objectids_to_strings(obj):
    """Recursively convert ObjectId to string for JSON serialization."""
    try:
        from bson import ObjectId
    except ImportError:
        ObjectId = None

    if ObjectId and isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: convert_objectids_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectids_to_strings(item) for item in obj]
    elif hasattr(obj, '__class__') and 'ObjectId' in str(type(obj)):
        return str(obj)
    return obj


# ---------------------------------------------------------------------------
#  Universal CRUD operations
# ---------------------------------------------------------------------------

async def create_content(
    collection_name: str,
    model_instance,
    tags: list = None,
    *,
    published_status=None,
):
    """Universal create handler.

    Args:
        collection_name: MongoDB collection name
        model_instance: Pydantic model instance to insert
        tags: Tags to sync (fallback: doc["tags"])
        published_status: If set and matches data.status, set published_at
    """
    db = await get_db()
    collection = getattr(db, collection_name)

    doc = model_instance.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()

    # For KVN, generate a separate UUID 'id' field
    if collection_name == "kvn":
        import uuid
        if "id" not in doc or not doc.get("id"):
            doc["id"] = str(uuid.uuid4())

    # Auto-set published_at when status is published
    if published_status and doc.get("status") == published_status:
        doc["published_at"] = datetime.now(timezone.utc).isoformat()

    # Проверка на дубликаты primary_tag для людей и команд
    primary_tag = doc.get("primary_tag")
    if primary_tag and collection_name in ["people", "teams"]:
        await check_primary_tag_duplicate(collection_name, primary_tag)

    # Синхронизация primary_tag в tags для людей и команд
    if collection_name in ["people", "teams"]:
        updated_tags = await sync_primary_tag_to_tags(doc)
        if updated_tags != doc.get("tags", []):
            doc["tags"] = updated_tags

    # Sync tags
    final_tags = doc.get("tags", [])
    if final_tags:
        await tag_service.sync_tags(final_tags)

    await collection.insert_one(doc)

    if collection_name == "kvn":
        return {"id": doc.get("id"), "slug": doc.get("slug")}
    return {"id": doc["_id"], "slug": doc.get("slug")}


async def update_content(
    collection_name: str,
    item_id: str,
    data,
    not_found_msg: str,
    *,
    published_status=None,
):
    """Universal update handler.

    Args:
        published_status: If data.status matches this value and published_at is not set, set it now.
    """
    db = await get_db()
    collection = getattr(db, collection_name)

    current_item = await collection.find_one({"_id": item_id})
    if not current_item:
        raise HTTPException(status_code=404, detail=not_found_msg)

    old_primary_tag = current_item.get("primary_tag")

    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Auto-set published_at when status changes to published
    if published_status and getattr(data, 'status', None) == published_status:
        if not current_item.get("published_at"):
            update_data["published_at"] = datetime.now(timezone.utc).isoformat()

    # Default primary_tag logic
    if hasattr(data, 'primary_tag') and 'primary_tag' not in update_data:
        if not old_primary_tag:
            if collection_name == "teams":
                default_tag = current_item.get("name") or current_item.get("title")
            elif collection_name == "people":
                def swap_name_order(name):
                    if not name:
                        return name
                    parts = name.strip().split()
                    if len(parts) == 2:
                        return f"{parts[1]} {parts[0]}"
                    return name
                title = current_item.get("title") or current_item.get("full_name")
                default_tag = swap_name_order(title)
            else:
                default_tag = None
            if default_tag:
                update_data["primary_tag"] = default_tag
                old_primary_tag = None

    # Check primary_tag duplicate
    new_primary_tag = update_data.get("primary_tag")
    if new_primary_tag and collection_name in ["people", "teams"]:
        if new_primary_tag != old_primary_tag:
            await check_primary_tag_duplicate(collection_name, new_primary_tag, exclude_id=item_id)

    # Sync primary_tag in tags for people/teams
    if collection_name in ["people", "teams"]:
        merged_item = {**current_item, **update_data}
        if hasattr(data, 'tags') and data.tags is not None:
            merged_item["tags"] = data.tags
        else:
            merged_item["tags"] = current_item.get("tags", [])
        updated_tags = await sync_primary_tag_to_tags(merged_item)
        if updated_tags != merged_item.get("tags", []):
            update_data["tags"] = updated_tags

    # Sync tags if present
    if hasattr(data, 'tags') and data.tags:
        await tag_service.sync_tags(data.tags)
    elif "tags" in update_data:
        await tag_service.sync_tags(update_data["tags"])

    result = await collection.update_one({"_id": item_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=not_found_msg)

    # Update tags everywhere if primary_tag changed
    final_new_primary_tag = update_data.get("primary_tag") or old_primary_tag
    if hasattr(data, 'primary_tag') and final_new_primary_tag != old_primary_tag:
        await update_tags_everywhere(db, old_primary_tag, final_new_primary_tag)

    return {"id": item_id, "updated": True}


async def delete_content(collection_name: str, item_id: str, not_found_msg: str):
    """Universal delete handler."""
    db = await get_db()
    collection = getattr(db, collection_name)
    result = await collection.delete_one({"_id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=not_found_msg)
    return {"id": item_id, "deleted": True}


async def get_by_id_or_slug(collection_name: str, id_or_slug: str, not_found_msg: str, increment_views: bool = True):
    """Universal get by ID or slug handler."""
    db = await get_db()
    collection = getattr(db, collection_name)

    if collection_name == "kvn":
        query = {"$or": [{"_id": id_or_slug}, {"id": id_or_slug}, {"slug": id_or_slug}]}
    else:
        query = {"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}

    item = await collection.find_one(query)
    if not item:
        raise HTTPException(status_code=404, detail=not_found_msg)

    if increment_views:
        from services.views_counter import views_counter
        views_counter.increment(collection_name, item["_id"])

    item = convert_objectids_to_strings(item)
    if "_id" in item:
        item["_id"] = str(item["_id"])
    return item


async def list_content(
    collection_name: str,
    skip: int,
    limit: int,
    query: dict = None,
    sort_field: str = "created_at",
    sort_order: int = -1,
    exclude_modules: bool = True
):
    """Universal list handler."""
    db = await get_db()
    collection = getattr(db, collection_name)

    query = query or {}
    projection = {"modules": 0} if exclude_modules else None

    total = await collection.count_documents(query)
    cursor = collection.find(query, projection).skip(skip).limit(limit).sort(sort_field, sort_order)
    items = await cursor.to_list(limit)

    return {"items": items, "total": total, "skip": skip, "limit": limit}


def build_alphabetical_pipeline(
    query: dict,
    skip: int,
    limit: int,
    sort_fields: list[str],
    exclude_modules: bool = True,
) -> list[dict]:
    """Build a stable Cyrillic -> Latin -> other-symbols list pipeline."""
    if not sort_fields:
        raise ValueError("sort_fields must not be empty")

    sort_value = ""
    for field in reversed(sort_fields):
        field_value = {"$ifNull": [f"${field}", ""]}
        sort_value = {
            "$cond": [
                {"$gt": [
                    {"$strLenCP": {"$trim": {"input": field_value}}},
                    0,
                ]},
                field_value,
                sort_value,
            ]
        }

    pipeline = [
        {"$match": query or {}},
        {"$set": {
            "_alphabet_sort_value": {
                "$trim": {"input": {"$ifNull": [sort_value, ""]}}
            }
        }},
        {"$set": {
            "_alphabet_sort_group": {
                "$switch": {
                    "branches": [
                        {
                            "case": {"$regexMatch": {
                                "input": "$_alphabet_sort_value",
                                "regex": "^[\u0400-\u052F\u2DE0-\u2DFF\uA640-\uA69F]",
                            }},
                            "then": 0,
                        },
                        {
                            "case": {"$regexMatch": {
                                "input": "$_alphabet_sort_value",
                                "regex": "^[A-Za-z]",
                            }},
                            "then": 1,
                        },
                    ],
                    "default": 2,
                }
            }
        }},
        {"$sort": {
            "_alphabet_sort_group": 1,
            "_alphabet_sort_value": 1,
            "_id": 1,
        }},
        {"$skip": skip},
        {"$limit": limit},
    ]
    projection = {"_alphabet_sort_value": 0, "_alphabet_sort_group": 0}
    if exclude_modules:
        projection["modules"] = 0
    pipeline.append({"$project": projection})
    return pipeline


async def list_alphabetical_content(
    collection_name: str,
    skip: int,
    limit: int,
    query: dict = None,
    sort_fields: list[str] = None,
    exclude_modules: bool = True,
):
    """List content alphabetically before pagination using Russian collation."""
    db = await get_db()
    collection = getattr(db, collection_name)
    query = query or {}
    total = await collection.count_documents(query)
    pipeline = build_alphabetical_pipeline(
        query,
        skip,
        limit,
        sort_fields or ["title", "name"],
        exclude_modules,
    )
    cursor = collection.aggregate(
        pipeline,
        collation={"locale": "ru", "strength": 2},
    )
    items = await cursor.to_list(limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}
