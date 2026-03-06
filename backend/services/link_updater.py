"""Сервис для автоматического обновления ссылок при изменении данных"""
from typing import List, Dict
from utils.database import get_db
import re


class LinkUpdater:
    """Обновляет ссылки во всех документах при изменении slug или названия"""
    
    @staticmethod
    async def update_links_for_content(
        content_type: str,
        old_slug: str,
        new_slug: str,
        old_title: str = None,
        new_title: str = None
    ):
        """
        Обновляет все ссылки на контент при изменении slug или title
        
        Args:
            content_type: Тип контента ('person', 'team', 'show', 'kvn', 'article', 'news')
            old_slug: Старый slug
            new_slug: Новый slug
            old_title: Старое название (опционально)
            new_title: Новое название (опционально)
        """
        db = await get_db()
        
        # Определяем префикс URL
        url_prefix_map = {
            'person': '/people/',
            'team': '/kvn/teams/',
            'show': '/shows/',
            'kvn': '/kvn/',
            'article': '/articles/',
            'news': '/news/'
        }
        
        if content_type not in url_prefix_map:
            return
        
        url_prefix = url_prefix_map[content_type]
        old_url = f"{url_prefix}{old_slug}"
        new_url = f"{url_prefix}{new_slug}"
        
        # Обновляем ссылки во всех коллекциях с HTML контентом
        collections_to_update = [
            db.people, db.teams, db.shows, db.kvn, 
            db.articles, db.news, db.quizzes, db.wiki
        ]
        
        for collection in collections_to_update:
            # Ищем все документы с модулями
            async for doc in collection.find({"modules": {"$exists": True}}):
                updated = False
                new_modules = []
                
                for module in doc.get('modules', []):
                    if module.get('type') == 'text_block':
                        content = module.get('data', {}).get('content', '')
                        
                        # Заменяем старый URL на новый
                        if old_url in content:
                            content = content.replace(old_url, new_url)
                            module['data']['content'] = content
                            updated = True
                        
                        # Заменяем старое название на новое (если указано)
                        if old_title and new_title and old_title in content:
                            # Используем regex для замены в тексте ссылок
                            pattern = f'<a[^>]*>{re.escape(old_title)}</a>'
                            replacement = f'<a href="{new_url}">{new_title}</a>'
                            content = re.sub(pattern, replacement, content)
                            module['data']['content'] = content
                            updated = True
                    
                    new_modules.append(module)
                
                if updated:
                    await collection.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"modules": new_modules}}
                    )
        
        # Также обновляем в description и других HTML полях
        for collection in collections_to_update:
            async for doc in collection.find({"description": {"$regex": old_url}}):
                new_description = doc.get('description', '').replace(old_url, new_url)
                await collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"description": new_description}}
                )
