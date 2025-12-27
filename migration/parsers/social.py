"""Парсер для модуля social_links."""

import re
import json
from typing import Optional
from .base import BaseParser, ParseContext


class SocialLinksParser(BaseParser):
    """Парсер социальных ссылок.
    
    Конфигурация:
        tv_field: Название TV поля с JSON ссылок
        html_selector: Регулярка для поиска ссылок в HTML
        style: 'list' | 'icons' | 'buttons'
    """
    
    module_type = "social_links"
    default_title = "Ссылки"
    
    def parse(self, ctx: ParseContext) -> Optional[dict]:
        links = {}
        
        # 1. Пробуем TV поле (JSON)
        tv_field = self.config.get('tv_field', 'list_social')
        
        # Проверяем в TV данных напрямую
        if tv_field and tv_field in ctx.tv_data:
            links = self._parse_social_json(ctx.tv_data[tv_field])
        
        # 2. Пробуем MIGX config -> info -> list_social
        if not links:
            config = ctx.tv_data.get('config', '')
            if config:
                sections = self._parse_migx(config)
                for sec in sections:
                    if sec.get('MIGX_formname') == 'info':
                        social_data = sec.get('list_social', '')
                        if social_data:
                            links = self._parse_social_json(social_data)
                            break
        
        # 3. Ищем ссылки в HTML
        if not links and ctx.html:
            # Ищем ссылки на соцсети
            href_matches = re.findall(
                r'<a[^>]+href=["\']([^"\'>]+(?:vk\.com|youtube|instagram|telegram|t\.me|twitter|x\.com|tiktok)[^"\'>]*)["\']',
                ctx.html, re.IGNORECASE
            )
            for href in href_matches:
                result = self.parse_social_link(href)
                if result:
                    key, url = result
                    if key not in links:
                        links[key] = url
        
        return {
            'title': self.config.get('title', self.default_title),
            'style': self.config.get('style', 'list'),
            'links': links
        }
    
    def _parse_social_json(self, data) -> dict:
        """Парсит JSON с социальными ссылками."""
        links = {}
        
        try:
            if isinstance(data, str):
                data = json.loads(self.normalize_html(data))
            
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        link = item.get('link', '')
                        if link:
                            result = self.parse_social_link(link)
                            if result:
                                key, url = result
                                links[key] = url
            elif isinstance(data, dict):
                for key, val in data.items():
                    if val:
                        links[key] = val
        except:
            pass
        
        return links
    
    def _parse_migx(self, config_str: str) -> list:
        """Парсит MIGX JSON."""
        if not config_str:
            return []
        try:
            config_str = self.normalize_html(config_str)
            data = json.loads(config_str)
            return data if isinstance(data, list) else [data]
        except:
            return []
