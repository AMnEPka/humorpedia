"""Парсер для модуля facts_table."""

import re
import json
from typing import Optional
from .base import BaseParser, ParseContext


class FactsParser(BaseParser):
    """Парсер таблицы фактов.
    
    Конфигурация:
        tv_field: Название TV поля с таблицей (по умолчанию ищет в config -> info -> table)
        html_selector: Регулярка для поиска таблицы в HTML
        exclude_keys: Список ключей для исключения
        style: 'card' | 'table' | 'list'
    """
    
    module_type = "facts_table"
    default_title = "Информация"
    
    def parse(self, ctx: ParseContext) -> Optional[dict]:
        facts = {}
        
        # 1. Пробуем TV поле напрямую
        tv_field = self.config.get('tv_field')
        if tv_field and tv_field in ctx.tv_data:
            table_html = ctx.tv_data[tv_field]
            facts = self._parse_table(table_html)
        
        # 2. Пробуем MIGX config -> секция info -> table
        if not facts:
            config = ctx.tv_data.get('config', '')
            if config:
                sections = self._parse_migx(config)
                for sec in sections:
                    if sec.get('MIGX_formname') == 'info':
                        table_html = sec.get('table', '')
                        if table_html:
                            facts = self._parse_table(table_html)
                            break
        
        # 3. Ищем таблицу в HTML
        if not facts and ctx.html:
            # Ищем таблицу с классом facts или info
            table_match = re.search(
                r'<table[^>]*class=["\'][^"\']*(facts|info)[^"\']["\'][^>]*>(.*?)</table>',
                ctx.html, re.IGNORECASE | re.DOTALL
            )
            if table_match:
                facts = self._parse_table(table_match.group(2))
        
        # Фильтруем исключённые ключи
        exclude = self.config.get('exclude_keys', [])
        facts = {k: v for k, v in facts.items() if k not in exclude}
        
        # Возвращаем даже если пусто - системный модуль
        return {
            'title': self.config.get('title', self.default_title),
            'style': self.config.get('style', 'card'),
            'facts': facts
        }
    
    def _parse_table(self, html: str) -> dict:
        """Парсит HTML таблицу в словарь."""
        facts = {}
        rows = self.extract_table_rows(html)
        
        for key, val in rows:
            if key and val:
                facts[key] = val
        
        return facts
    
    def _parse_migx(self, config_str: str) -> list:
        """Парсит MIGX JSON."""
        if not config_str:
            return []
        
        try:
            # Нормализуем строку
            config_str = self.normalize_migx_json(config_str)
            data = json.loads(config_str)
            return data if isinstance(data, list) else [data]
        except:
            return []
