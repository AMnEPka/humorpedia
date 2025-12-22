"""Content service - centralized content operations"""
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone

from utils.database import get_db
from services.tags import tag_service


# Collection mapping
COLLECTION_MAP = {
    "person": "people",
    "people": "people",
    "team": "teams",
    "teams": "teams",
    "show": "shows",
    "shows": "shows",
    "article": "articles",
    "articles": "articles",
    "news": "news",
    "quiz": "quizzes",
    "quizzes": "quizzes",
    "wiki": "wiki",
}


class ContentService:
    """Centralized service for content CRUD operations"""
    
    @staticmethod
    async def get_collection(content_type: str):
        """Get MongoDB collection by content type"""
        db = await get_db()
        collection_name = COLLECTION_MAP.get(content_type)
        if not collection_name:
            raise ValueError(f"Unknown content type: {content_type}")
        return getattr(db, collection_name)
    
    @staticmethod
    async def create(
        content_type: str,
        doc: Dict[str, Any],
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Universal create method for all content types.
        Handles timestamps and tag syncing automatically.
        """
        collection = await ContentService.get_collection(content_type)
        
        # Set timestamps
        now = datetime.now(timezone.utc).isoformat()
        doc["created_at"] = now
        doc["updated_at"] = now
        
        # Sync tags to tags collection
        if tags:
            await tag_service.sync_tags(tags)
        
        await collection.insert_one(doc)
        return {"id": doc["_id"], "slug": doc.get("slug")}
    
    @staticmethod
    async def update(
        content_type: str,
        item_id: str,
        update_data: Dict[str, Any],
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Universal update method for all content types.
        Handles timestamps and tag syncing automatically.
        """
        collection = await ContentService.get_collection(content_type)
        
        # Filter out None values and set timestamp
        filtered_data = {k: v for k, v in update_data.items() if v is not None}
        filtered_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Sync tags to tags collection
        if tags:
            await tag_service.sync_tags(tags)
        
        result = await collection.update_one({"_id": item_id}, {"$set": filtered_data})
        
        return {
            "id": item_id,
            "updated": result.matched_count > 0,
            "modified": result.modified_count > 0
        }
    
    @staticmethod
    async def delete(content_type: str, item_id: str) -> Dict[str, Any]:
        """Universal delete method"""
        collection = await ContentService.get_collection(content_type)
        result = await collection.delete_one({"_id": item_id})
        return {"id": item_id, "deleted": result.deleted_count > 0}
    
    @staticmethod
    async def get_by_id_or_slug(
        content_type: str,
        id_or_slug: str,
        increment_views: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Get item by ID or slug, optionally increment views"""
        collection = await ContentService.get_collection(content_type)
        
        # Try to find by ID first, then by slug
        item = await collection.find_one({"_id": id_or_slug})
        if not item:
            item = await collection.find_one({"slug": id_or_slug})
        
        if item and increment_views:
            await collection.update_one(
                {"_id": item["_id"]},
                {"$inc": {"views": 1}}
            )
        
        return item
    
    @staticmethod
    async def list_items(
        content_type: str,
        skip: int = 0,
        limit: int = 20,
        query: Optional[Dict] = None,
        sort_field: str = "created_at",
        sort_order: int = -1,
        exclude_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Universal list method with pagination"""
        collection = await ContentService.get_collection(content_type)
        
        query = query or {}
        projection = {field: 0 for field in (exclude_fields or [])}
        
        total = await collection.count_documents(query)
        cursor = collection.find(query, projection or None)\
            .skip(skip).limit(limit).sort(sort_field, sort_order)
        items = await cursor.to_list(limit)
        
        return {
            "items": items,
            "total": total,
            "skip": skip,
            "limit": limit
        }


# Singleton instance
content_service = ContentService()
