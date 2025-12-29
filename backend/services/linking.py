"""Linking service - manages relationships between content and people"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from uuid import uuid4

from utils.database import get_db
from models.modules import PageModule, ModuleType


class LinkingService:
    """Service for managing content-person relationships"""
    
    @staticmethod
    async def update_person_links(content_type: str, content_id: str, person_ids: Optional[List[str]]) -> None:
        """
        Update person links when content is created/updated.
        Ensures humor_chronicles module exists on person pages.
        
        Args:
            content_type: 'news', 'article', or 'show'
            content_id: ID of the content item
            person_ids: List of person IDs to link
        """
        if not person_ids:
            return
        
        db = await get_db()
        collection_map = {
            'news': db.news,
            'article': db.articles,
            'show': db.shows
        }
        
        collection = collection_map.get(content_type)
        if not collection:
            return
        
        # Update content document with person_ids
        await collection.update_one(
            {"_id": content_id},
            {"$set": {"related_person_ids": person_ids}}
        )
        
        # For each person, ensure humor_chronicles module exists
        for person_id in person_ids:
            await LinkingService.ensure_chronicles_module(person_id)
    
    @staticmethod
    async def get_linked_content(
        person_id: str,
        content_types: Optional[List[str]] = None,
        limit: int = 20
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all content linked to a person.
        
        Args:
            person_id: Person ID
            content_types: List of content types to fetch ('news', 'article', 'show')
            limit: Maximum items per type
        
        Returns:
            Dictionary with content types as keys and lists of content items as values
        """
        if not content_types:
            content_types = ['news', 'article', 'show']
        
        db = await get_db()
        collection_map = {
            'news': db.news,
            'article': db.articles,
            'show': db.shows
        }
        
        result = {}
        
        for content_type in content_types:
            collection = collection_map.get(content_type)
            if not collection:
                continue
            
            # Find published content linked to this person
            query = {
                "related_person_ids": person_id,
                "status": "published"
            }
            
            cursor = collection.find(
                query,
                {"modules": 0}  # Exclude modules for performance
            ).sort("published_at", -1).limit(limit)
            
            items = await cursor.to_list(limit)
            
            # Convert MongoDB _id to id for consistency
            for item in items:
                item["id"] = item.pop("_id", item.get("id"))
            
            result[content_type] = items
        
        return result
    
    @staticmethod
    async def ensure_chronicles_module(person_id: str) -> None:
        """
        Ensure humor_chronicles module exists on person page.
        Creates it if missing, does nothing if already exists.
        
        Args:
            person_id: Person ID
        """
        db = await get_db()
        
        person = await db.people.find_one({"_id": person_id})
        if not person:
            return
        
        modules = person.get("modules", [])
        
        # Check if humor_chronicles module already exists
        has_chronicles = any(
            m.get("type") == ModuleType.HUMOR_CHRONICLES.value
            for m in modules
        )
        
        if not has_chronicles:
            # Create new humor_chronicles module
            new_module = {
                "id": str(uuid4()),
                "type": ModuleType.HUMOR_CHRONICLES.value,
                "order": len(modules),  # Add at the end
                "title": "Юмористические хроники",
                "visible": True,
                "data": {}  # Empty data, will be filled dynamically
            }
            
            modules.append(new_module)
            
            # Update person document
            await db.people.update_one(
                {"_id": person_id},
                {
                    "$set": {
                        "modules": modules,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )


# Singleton instance
linking_service = LinkingService()

