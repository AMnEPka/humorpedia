"""Парсер для модуля text_block."""

import re
import json
from typing import Optional, List
from .base import BaseParser, ParseContext


class TextBlockParser(BaseParser):
    """Парсер текстового блока.
    
    Конфигурация:
        tv_field: Название TV поля с текстом
        migx_section: Название секции MIGX (например 'info', 'biography')
        migx_field: Поле внутри секции MIGX (например 'subtitle', 'content')
        html_selector: Регулярка для поиска текста в HTML
        title: Заголовок блока
        strip_first_heading: Удалять первый заголовок если он совпадает с title
        all_sections: Собрать все секции кроме info/timeline/tags
        all_text_sections: Вернуть список всех text секций (для множественных модулей)
    """
    
    module_type = "text_block"
    default_title = ""
    
    def parse(self, ctx: ParseContext) -> Optional[dict]:
        content = ""
        block_title = self.config.get('title', '')
        
        # 1. Пробуем TV поле напрямую
        tv_field = self.config.get('tv_field')
        if tv_field and tv_field in ctx.tv_data:
            content = ctx.tv_data[tv_field]
        
        # 2. Пробуем MIGX секцию
        if not content:
            migx_section = self.config.get('migx_section')
            migx_field = self.config.get('migx_field', 'subtitle')
            
            if migx_section:
                config = ctx.tv_data.get('config', '')
                if config:
                    sections = self._parse_migx(config)
                    for sec in sections:
                        if sec.get('MIGX_formname') == migx_section:
                            content = sec.get(migx_field, '') or sec.get('content', '')
                            if not block_title:
                                block_title = sec.get('title', '')
                            break
        
        # 3. Берём все секции MIGX кроме info/timeline/tags
        if not content and self.config.get('all_sections'):
            config = ctx.tv_data.get('config', '')
            if config:
                sections = self._parse_migx(config)
                contents = []
                skip_types = {'info', 'timeline', 'tags', 'ad_250', 'ad_block_120', 'popular_articles'}
                for sec in sections:
                    form = sec.get('MIGX_formname', '')
                    if form not in skip_types:
                        text = sec.get('content', '') or sec.get('subtitle', '')
                        title = sec.get('title', '')
                        if text:
                            if title:
                                contents.append(f'<h3>{title}</h3>{text}')
                            else:
                                contents.append(text)
                content = ''.join(contents)
        
        # 4. Ищем в HTML по селектору
        if not content and ctx.html:
            selector = self.config.get('html_selector')
            if selector:
                match = re.search(selector, ctx.html, re.IGNORECASE | re.DOTALL)
                if match:
                    content = match.group(1) if match.lastindex else match.group(0)
        
        if not content:
            return None
        
        # Нормализуем HTML
        content = self.normalize_html(content)
        
        # Удаляем первый заголовок если нужно
        if self.config.get('strip_first_heading') and ctx.title:
            title_lower = ctx.title.lower()
            content_lower = content.lower()
            if content_lower.startswith(f'<p>{title_lower}') or content_lower.startswith('<h'):
                content = re.sub(r'^<[ph]\d?>[^<]*</[ph]\d?>', '', content, count=1, flags=re.IGNORECASE | re.DOTALL).strip()
        
        return {
            'title': block_title,
            'content': content
        }
    
    def parse_all_text_sections(self, ctx: ParseContext) -> List[dict]:
        """Парсит все text секции из MIGX и возвращает список."""
        results = []
        
        config = ctx.tv_data.get('config', '')
        if not config:
            return results
        
        sections = self._parse_migx(config)
        skip_types = {'info', 'timeline', 'tags', 'ad_250', 'ad_block_120', 'popular_articles'}
        
        for sec in sections:
            form = sec.get('MIGX_formname', '')
            
            # Обрабатываем text секции
            if form == 'text':
                content = sec.get('content', '') or sec.get('subtitle', '')
                title = sec.get('title', '')
                
                if content:
                    results.append({
                        'title': self.normalize_html(title) if title else '',
                        'content': self.normalize_html(content)
                    })
            
            # Обрабатываем table секции как текстовые блоки
            elif form == 'table':
                content = sec.get('content', '')
                if content:
                    results.append({
                        'title': '',
                        'content': self.normalize_html(content)
                    })
        
        return results
    
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
