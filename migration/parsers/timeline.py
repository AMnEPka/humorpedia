"""Парсер для модуля timeline."""

import re
import json
from typing import Optional, List
from .base import BaseParser, ParseContext


class TimelineParser(BaseParser):
    """Парсер хронологии/таймлайна.
    
    Конфигурация:
        tv_field: Название TV поля с JSON событиями
        migx_section: Секция MIGX для поиска
        html_selector: Регулярка для парсинга HTML таймлайна
        date_format: Формат даты в HTML
    """
    
    module_type = "timeline"
    default_title = "Хронология"
    
    def parse(self, ctx: ParseContext) -> Optional[dict]:
        events = []
        
        # 1. Пробуем TV поля timeline-block-date{N}, timeline-block-name{N}, timeline-block-value{N}
        for i in range(1, 15):
            suf = "" if i == 1 else str(i)
            date = ctx.tv_data.get(f"timeline-block-date{suf}", "")
            name = ctx.tv_data.get(f"timeline-block-name{suf}", "")
            value = ctx.tv_data.get(f"timeline-block-value{suf}", "")
            
            if date and name and value:
                events.append({
                    'year': self.normalize_html(date),
                    'date': '',
                    'title': self.normalize_html(name),
                    'description': self.normalize_html(value)
                })
        
        # 2. Пробуем MIGX секцию timeline -> list_triple
        if not events:
            config = ctx.tv_data.get('config', '')
            if config:
                sections = self._parse_migx(config)
                
                for sec in sections:
                    if sec.get('MIGX_formname') == 'timeline':
                        list_triple = sec.get('list_triple', [])
                        
                        # list_triple может быть строкой или массивом
                        if isinstance(list_triple, str) and list_triple:
                            try:
                                # Нормализуем JSON
                                list_triple = self.normalize_migx_json(list_triple)
                                list_triple = json.loads(list_triple)
                            except:
                                list_triple = []
                        
                        if isinstance(list_triple, list):
                            for item in list_triple:
                                if isinstance(item, dict):
                                    title = item.get('title', '')
                                    subtitle = item.get('subtitle', '')  # год
                                    content = item.get('content', '')
                                    
                                    if title or subtitle:
                                        events.append({
                                            'year': self.normalize_html(subtitle) if subtitle else '',
                                            'date': '',
                                            'title': self.normalize_html(title) if title else '',
                                            'description': self.normalize_html(content) if content else ''
                                        })
                        break
        
        # 3. Пробуем TV поля tv_simple секции
        if not events:
            config = ctx.tv_data.get('config', '')
            if config:
                sections = self._parse_migx(config)
                migx_section = self.config.get('migx_section', 'tv_simple')
                
                for sec in sections:
                    form_name = sec.get('MIGX_formname', '')
                    
                    # Ищем секции с годами/датами
                    if form_name == migx_section or form_name.startswith('tv_'):
                        event = self._extract_event_from_section(sec)
                        if event:
                            events.append(event)
        
        # 4. Парсим HTML если есть селектор
        if not events and ctx.html:
            events = self._parse_html_timeline(ctx.html)
        
        if not events:
            return None
        
        # Сортируем по году
        events = self._sort_events(events)
        
        return {
            'title': self.config.get('title', self.default_title),
            'events': events
        }
    
    def _parse_events_json(self, data) -> List[dict]:
        """Парсит JSON с событиями."""
        try:
            if isinstance(data, str):
                data = json.loads(self.normalize_html(data))
            
            if isinstance(data, list):
                events = []
                for item in data:
                    if isinstance(item, dict):
                        event = {
                            'year': item.get('year', item.get('date', '')),
                            'date': item.get('date', ''),
                            'title': self.normalize_html(item.get('title', '')),
                            'description': self.normalize_html(item.get('description', item.get('text', '')))
                        }
                        if event['year'] or event['title']:
                            events.append(event)
                return events
        except:
            pass
        return []
    
    def _extract_event_from_section(self, sec: dict) -> Optional[dict]:
        """Извлекает событие из секции MIGX."""
        year = sec.get('year', sec.get('date', ''))
        title = sec.get('title', sec.get('name', ''))
        description = sec.get('subtitle', sec.get('description', sec.get('content', '')))
        
        if not year and not title:
            return None
        
        return {
            'year': self.normalize_html(str(year)) if year else '',
            'date': '',
            'title': self.normalize_html(title) if title else '',
            'description': self.normalize_html(description) if description else ''
        }
    
    def _parse_html_timeline(self, html: str) -> List[dict]:
        """Парсит таймлайн из HTML."""
        events = []
        
        # Ищем элементы с классом timeline-item или подобным
        items = re.findall(
            r'<div[^>]*class=["\'][^"\']*(timeline-item|event)[^"\']["\'][^>]*>(.*?)</div>',
            html, re.IGNORECASE | re.DOTALL
        )
        
        for _, content in items:
            # Извлекаем год/дату
            year_match = re.search(r'<[^>]*class=["\'][^"\']*(year|date)[^"\']["\'][^>]*>([^<]+)', content)
            title_match = re.search(r'<[^>]*class=["\'][^"\']*(title|heading)[^"\']["\'][^>]*>([^<]+)', content)
            desc_match = re.search(r'<[^>]*class=["\'][^"\']*(desc|content|text)[^"\']["\'][^>]*>(.*?)</[^>]+>', content, re.DOTALL)
            
            event = {
                'year': year_match.group(2).strip() if year_match else '',
                'date': '',
                'title': title_match.group(2).strip() if title_match else '',
                'description': self.normalize_html(desc_match.group(2)) if desc_match else ''
            }
            
            if event['year'] or event['title']:
                events.append(event)
        
        return events
    
    def _sort_events(self, events: List[dict]) -> List[dict]:
        """Сортирует события по году."""
        def get_sort_key(e):
            year_str = e.get('year', '') or e.get('date', '')
            # Извлекаем первое число из строки
            match = re.search(r'(\d{4})', str(year_str))
            return int(match.group(1)) if match else 0
        
        return sorted(events, key=get_sort_key)
    
    def _parse_migx(self, config_str: str) -> list:
        if not config_str:
            return []
        try:
            config_str = self.normalize_migx_json(config_str)
            data = json.loads(config_str)
            return data if isinstance(data, list) else [data]
        except:
            return []
