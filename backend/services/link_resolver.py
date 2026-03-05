"""Сервис для разрешения динамических ссылок в контенте"""
import re
from typing import Dict, Optional, List
from utils.database import get_db


class LinkResolver:
    """Разрешает ссылки в HTML контенте, проверяя актуальность slug'ов"""
    
    @staticmethod
    async def resolve_links_in_html(html: str) -> str:
        """
        Обновляет ссылки в HTML, проверяя актуальность slug'ов.
        Это гарантирует, что даже если slug изменился, ссылка будет правильной.
        
        Args:
            html: HTML контент со ссылками
            
        Returns:
            HTML с обновленными ссылками
        """
        if not html:
            return html
        
        db = await get_db()
        
        # Паттерн для поиска ссылок
        link_pattern = re.compile(
            r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL
        )
        
        async def replace_link(match):
            full_tag = match.group(0)
            url = match.group(1)
            text = match.group(2)
            
            # Пропускаем внешние ссылки
            if url.startswith('http://') or url.startswith('https://') or url.startswith('mailto:'):
                return full_tag
            
            # Пропускаем якоря
            if url.startswith('#'):
                return full_tag
            
            # Парсим URL
            url_parts = url.strip('/').split('/')
            
            if len(url_parts) < 2:
                return full_tag
            
            # Определяем тип и slug
            content_type = url_parts[0]
            slug = url_parts[-1]
            
            collection_map = {
                'people': (db.people, '/people/'),
                'kvn': (db.kvn, '/kvn/'),
                'teams': (db.teams, '/kvn/teams/'),
                'shows': (db.shows, '/shows/'),
                'articles': (db.articles, '/articles/'),
                'news': (db.news, '/news/'),
            }
            
            # Для KVN может быть полный путь
            if content_type == 'kvn' and len(url_parts) > 2:
                full_path = '/'.join(url_parts)
                doc = await db.kvn.find_one({"full_path": full_path.lstrip('/')})
                if doc:
                    correct_url = f"/{doc.get('full_path', '').lstrip('/')}"
                    return f'<a href="{correct_url}">{text}</a>'
            
            if content_type in collection_map:
                collection, url_prefix = collection_map[content_type]
                doc = await collection.find_one({"slug": slug})
                
                if doc:
                    # Проверяем, не изменился ли slug
                    current_slug = doc.get('slug')
                    if current_slug != slug:
                        # Slug изменился, обновляем ссылку
                        if content_type == 'kvn':
                            full_path = doc.get('full_path') or current_slug
                            correct_url = f"/{full_path.lstrip('/')}"
                        else:
                            correct_url = f"{url_prefix}{current_slug}"
                        return f'<a href="{correct_url}">{text}</a>'
            
            return full_tag
        
        # Обрабатываем все совпадения асинхронно
        matches = list(link_pattern.finditer(html))
        replacements = []
        for match in matches:
            replacement = await replace_link(match)
            replacements.append((match.start(), match.end(), replacement))
        
        # Применяем замены в обратном порядке, чтобы не сбить индексы
        result = html
        for start, end, replacement in reversed(replacements):
            result = result[:start] + replacement + result[end:]
        
        return result
    
    @staticmethod
    async def resolve_links_in_modules(modules: List[Dict]) -> List[Dict]:
        """
        Разрешает ссылки во всех text_block модулях
        
        Args:
            modules: Список модулей страницы
            
        Returns:
            Список модулей с обновленными ссылками
        """
        if not modules:
            return modules
        
        resolved_modules = []
        for module in modules:
            if module.get('type') == 'text_block':
                content = module.get('data', {}).get('content', '')
                if content:
                    resolved_content = await LinkResolver.resolve_links_in_html(content)
                    new_module = module.copy()
                    new_module['data'] = module['data'].copy()
                    new_module['data']['content'] = resolved_content
                    resolved_modules.append(new_module)
                else:
                    resolved_modules.append(module)
            else:
                resolved_modules.append(module)
        
        return resolved_modules
