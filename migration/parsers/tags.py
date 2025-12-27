"""Парсер для модуля tags_cloud."""

import re
from typing import Optional
from .base import BaseParser, ParseContext


class TagsParser(BaseParser):
    """Парсер тегов.
    
    Конфигурация:
        tv_field: Название TV поля с тегами (разделитель ||)
        html_selector: Регулярка для поиска тегов в HTML
        delimiter: Разделитель тегов в TV поле
        max_tags: Максимальное количество тегов (0 = без лимита)
        style: 'badges' | 'links' | 'cloud'
    """
    
    module_type = "tags_cloud"
    default_title = "Теги"
    
    def parse(self, ctx: ParseContext) -> Optional[dict]:
        tags = []
        
        # 1. Пробуем TV поле
        tv_field = self.config.get('tv_field', 'tags')
        delimiter = self.config.get('delimiter', '||')
        
        if tv_field and tv_field in ctx.tv_data:
            tag_str = ctx.tv_data[tv_field]
            if tag_str:
                tag_ids = [t.strip() for t in tag_str.split(delimiter) if t.strip()]
                
                # Конвертируем ID в названия через tag_map
                for tag_id in tag_ids:
                    if tag_id in ctx.tag_map:
                        tags.append(ctx.tag_map[tag_id])
                    elif not tag_id.isdigit():
                        # Это уже название, а не ID
                        tags.append(tag_id)
        
        # 2. Ищем теги в HTML (по классу tag или badge)
        if not tags and ctx.html:
            tag_matches = re.findall(
                r'<(?:a|span)[^>]*class=["\'][^"\']*(tag|badge)[^"\']["\'][^>]*>([^<]+)</(?:a|span)>',
                ctx.html, re.IGNORECASE
            )
            tags = [self.strip_tags(m[1]).strip() for m in tag_matches if m[1].strip()]
        
        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique_tags = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                unique_tags.append(t)
        
        # Применяем лимит
        max_tags = self.config.get('max_tags', 0)
        if max_tags > 0:
            unique_tags = unique_tags[:max_tags]
        
        return {
            'title': self.config.get('display_title', ''),
            'style': self.config.get('style', 'badges'),
            'max_tags': max_tags,
            'tags': unique_tags
        }
