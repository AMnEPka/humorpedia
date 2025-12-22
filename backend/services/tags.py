"""Tag service - centralized tag management"""
from typing import List, Optional
from datetime import datetime, timezone
from uuid import uuid4

from utils.database import get_db


# Transliteration map for cyrillic -> latin slugs
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def transliterate_slug(text: str) -> str:
    """Convert cyrillic text to latin slug"""
    slug = text.lower().replace(" ", "-").replace(".", "").replace(",", "")
    return ''.join(TRANSLIT_MAP.get(char, char) for char in slug)


class TagService:
    """Centralized service for tag operations"""
    
    @staticmethod
    async def sync_tags(tags: Optional[List[str]]) -> None:
        """
        Sync content tags to the tags collection.
        Creates new tags if they don't exist, increments usage count if they do.
        """
        if not tags:
            return
        
        db = await get_db()
        
        for tag_name in tags:
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            
            # Check if tag already exists (case-insensitive)
            existing = await db.tags.find_one({
                "name": {"$regex": f"^{tag_name}$", "$options": "i"}
            })
            
            if not existing:
                # Create new tag
                tag_doc = {
                    "_id": str(uuid4()),
                    "name": tag_name,
                    "slug": transliterate_slug(tag_name),
                    "old_id": None,
                    "usage_count": 1,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                try:
                    await db.tags.insert_one(tag_doc)
                except Exception:
                    pass  # Ignore duplicates
            else:
                # Increment usage count
                await db.tags.update_one(
                    {"_id": existing["_id"]},
                    {"$inc": {"usage_count": 1}}
                )
    
    @staticmethod
    async def get_all_tags(limit: int = 1000) -> List[str]:
        """Get all tag names"""
        db = await get_db()
        cursor = db.tags.find({}, {"name": 1, "_id": 0}).limit(limit)
        tags = await cursor.to_list(limit)
        return [t["name"] for t in tags]
    
    @staticmethod
    async def search_tags(query: str, limit: int = 20) -> List[str]:
        """Search tags by name"""
        db = await get_db()
        cursor = db.tags.find(
            {"name": {"$regex": query, "$options": "i"}},
            {"name": 1, "_id": 0}
        ).limit(limit)
        tags = await cursor.to_list(limit)
        return [t["name"] for t in tags]


# Singleton instance
tag_service = TagService()
