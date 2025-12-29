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
        """Парсит JSON с социальными ссылками.
        
        Поддерживает два формата:
        1. Массив объектов: [{"name": "website", "link": "https://..."}, ...]
        2. Словарь: {"website": "https://...", "vk": "https://..."}
        """
        links = {}
        
        try:
            if isinstance(data, str):
                # Нормализуем строку (убираем экранирование)
                normalized = self.normalize_html(data)
                normalized = normalized.replace('\\"', '"').replace('\\/', '/')
                data = json.loads(normalized)
            
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        # Формат из MIGX: {"name": "website", "link": "https://..."}
                        name = item.get('name', '')
                        link = item.get('link', '')
                        
                        if link:
                            # Если есть name, используем его как ключ (если это известная соцсеть)
                            # Иначе определяем тип по URL
                            if name:
                                # Нормализуем имя (lowercase, убираем пробелы)
                                name_lower = name.lower().strip()
                                # Если это известная соцсеть, используем стандартный ключ
                                known_socials = {
                                    'vk': 'vk', 'vkontakte': 'vk',
                                    'youtube': 'youtube', 'ютуб': 'youtube',
                                    'instagram': 'instagram', 'инстаграм': 'instagram', 'ig': 'instagram',
                                    'telegram': 'telegram', 'телеграм': 'telegram', 'tg': 'telegram',
                                    'twitter': 'twitter', 'твиттер': 'twitter',
                                    'tiktok': 'tiktok', 'тикток': 'tiktok',
                                    'website': 'website', 'сайт': 'website', 'site': 'website'
                                }
                                key = known_socials.get(name_lower, 'website')
                            else:
                                # Определяем тип по URL
                                result = self.parse_social_link(link)
                                if result:
                                    key, _ = result
                                else:
                                    key = 'website'
                            
                            links[key] = link
            elif isinstance(data, dict):
                # Формат словаря: {"website": "https://...", "vk": "https://..."}
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
            config_str = self.normalize_migx_json(config_str)
            data = json.loads(config_str)
            return data if isinstance(data, list) else [data]
        except:
            return []
