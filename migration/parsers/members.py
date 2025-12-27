"""Парсер для модуля team_members (состав команды)."""

import re
import json
from typing import Optional, List
from .base import BaseParser, ParseContext


class TeamMembersParser(BaseParser):
    """Парсер состава команды.
    
    Конфигурация:
        tv_field: Название TV поля с JSON участниками
        html_selector: Регулярка для поиска в HTML
    """
    
    module_type = "team_members"
    default_title = "Состав"
    
    def parse(self, ctx: ParseContext) -> Optional[dict]:
        members = []
        
        # 1. Пробуем TV поле (JSON)
        tv_field = self.config.get('tv_field', 'members')
        if tv_field and tv_field in ctx.tv_data:
            members = self._parse_members_json(ctx.tv_data[tv_field])
        
        # 2. Пробуем MIGX
        if not members:
            config = ctx.tv_data.get('config', '')
            if config:
                sections = self._parse_migx(config)
                for sec in sections:
                    if sec.get('MIGX_formname') == 'members':
                        members_data = sec.get('list', sec.get('items', []))
                        members = self._parse_members_json(members_data)
                        break
        
        # 3. Парсим HTML
        if not members and ctx.html:
            members = self._parse_html_members(ctx.html)
        
        if not members:
            return None
        
        return {
            'title': self.config.get('title', self.default_title),
            'members': members
        }
    
    def _parse_members_json(self, data) -> List[dict]:
        """Парсит JSON с участниками."""
        try:
            if isinstance(data, str):
                data = json.loads(self.normalize_html(data))
            
            if isinstance(data, list):
                members = []
                for item in data:
                    if isinstance(item, dict):
                        member = {
                            'name': item.get('name', item.get('title', '')),
                            'role': item.get('role', item.get('position', '')),
                            'photo': item.get('photo', item.get('image', '')),
                            'slug': item.get('slug', item.get('id', '')),
                            'person_id': item.get('person_id', item.get('id', ''))
                        }
                        if member['name']:
                            members.append(member)
                return members
        except:
            pass
        return []
    
    def _parse_html_members(self, html: str) -> List[dict]:
        """Парсит участников из HTML."""
        members = []
        
        # Ищем ссылки на участников
        links = re.findall(
            r'<a[^>]+href=["\']([^"\'>]*/people/[^"\'>]+)["\'][^>]*>([^<]+)</a>',
            html, re.IGNORECASE
        )
        
        for href, name in links:
            slug = href.split('/')[-1]
            members.append({
                'name': self.strip_tags(name).strip(),
                'role': '',
                'photo': '',
                'slug': slug,
                'person_id': ''
            })
        
        return members
    
    def _parse_migx(self, config_str: str) -> list:
        if not config_str:
            return []
        try:
            config_str = self.normalize_html(config_str)
            data = json.loads(config_str)
            return data if isinstance(data, list) else [data]
        except:
            return []
