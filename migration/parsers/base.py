"""Базовый класс для всех парсеров модулей."""

from __future__ import annotations
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4
from html import unescape


@dataclass
class ParseContext:
    """Контекст для парсинга - общие данные для всех парсеров."""
    html: str = ""  # Основной HTML контент страницы
    title: str = ""  # Название ресурса
    resource_id: int = 0  # ID в MODX
    tv_data: dict = field(default_factory=dict)  # TV данные (migx и прочее)
    tag_map: dict = field(default_factory=dict)  # Маппинг tag_id -> tag_name
    image_map: dict = field(default_factory=dict)  # Маппинг image_id -> url
    sql_file: str = ""  # Путь к SQL файлу для извлечения рейтингов
    rating: float = 0.0  # Рейтинг из site_content
    votes: int = 0  # Количество голосов из site_content
    extra: dict = field(default_factory=dict)  # Дополнительные данные


class BaseParser(ABC):
    """Базовый класс парсера модуля."""
    
    # Тип модуля (poster_photo, facts_table, etc.)
    module_type: str = "unknown"
    
    # Название по умолчанию
    default_title: str = ""
    
    def __init__(self, config: dict = None):
        """Инициализация парсера.
        
        Args:
            config: Конфигурация парсера (селекторы, опции)
        """
        self.config = config or {}
    
    @abstractmethod
    def parse(self, ctx: ParseContext) -> Optional[dict]:
        """Парсит данные и возвращает data для модуля.
        
        Args:
            ctx: Контекст парсинга
            
        Returns:
            dict с данными модуля или None если данные не найдены
        """
        pass
    
    def build_module(self, ctx: ParseContext, order: int = 1) -> Optional[dict]:
        """Строит полный модуль с метаданными.
        
        Args:
            ctx: Контекст парсинга
            order: Порядок модуля
            
        Returns:
            Полный документ модуля или None
        """
        data = self.parse(ctx)
        if data is None:
            return None
        
        return {
            'id': str(uuid4()),
            'type': self.module_type,
            'order': order,
            'title': self.config.get('title', self.default_title),
            'visible': self.config.get('visible', True),
            'data': data
        }
    
    # === Утилиты для парсеров ===
    
    @staticmethod
    def normalize_html(text: str) -> str:
        """Нормализует HTML из SQL/TV данных."""
        if not text:
            return ""
        
        text = unescape(text)
        # Удаляем управляющие символы кроме newline
        text = re.sub(r'[\x00-\x09\x0b-\x1f]', '', text)
        text = text.replace('\\r\\n', '\n').replace('\\r', '\n').replace('\\n', '\n')
        text = text.replace('>\\<', '><')
        text = text.replace('\\\\"', '"').replace('\\"', '"')
        text = text.replace("\\\\'" , "'").replace("\\'", "'")
        text = text.replace('\\/', '/')
        text = text.replace('\\<', '<').replace('\\>', '>')
        text = text.replace('\u00a0', ' ').replace('&nbsp;', ' ')
        
        return text.strip()
    
    @staticmethod
    def normalize_migx_json(text: str) -> str:
        """Нормализует MIGX JSON строку для парсинга.
        
        Обрабатывает различные уровни экранирования из SQL dump.
        """
        if not text:
            return ""
        
        # Удаляем все управляющие символы
        text = re.sub(r'[\x00-\x09\x0b-\x1f]', '', text)
        text = text.replace('\\r\\n', ' ').replace('\\r', ' ').replace('\\n', ' ')
        text = text.replace('\n', ' ')
        
        # Самый внешний уровень экранирования от SQL
        # \\" -> " (внешние кавычки JSON)
        text = text.replace('\\"', '"')
        
        # \\/ -> / 
        text = text.replace('\\/', '/')
        
        # Удаляем невалидные escape-последовательности 
        # Но сохраняем \\", которые теперь стали \" внутри строк
        text = re.sub(r'\\(?!["\\/bfnrtu\\])', '', text)
        
        return text.strip()
    
    @staticmethod
    def strip_tags(html: str) -> str:
        """Удаляет HTML теги из текста."""
        return re.sub(r'<[^>]+>', '', html).strip()
    
    @staticmethod
    def extract_table_rows(html: str) -> list[tuple[str, str]]:
        """Извлекает строки из HTML таблицы (ключ, значение)."""
        rows = re.findall(
            r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>',
            html, re.IGNORECASE | re.DOTALL
        )
        return [(BaseParser.strip_tags(k), BaseParser.normalize_html(v)) for k, v in rows]
    
    @staticmethod
    def find_first_image(html: str) -> Optional[str]:
        """Находит первое изображение в HTML."""
        match = re.search(r'<img[^>]+src=["\']([^"\'>]+)["\']', html, re.IGNORECASE)
        return match.group(1) if match else None
    
    @staticmethod
    def find_all_images(html: str) -> list[str]:
        """Находит все изображения в HTML."""
        return re.findall(r'<img[^>]+src=["\']([^"\'>]+)["\']', html, re.IGNORECASE)
    
    @staticmethod
    def parse_social_link(url: str) -> Optional[tuple[str, str]]:
        """Определяет тип социальной ссылки.
        
        Returns:
            (key, url) или None
        """
        if not url:
            return None
        
        url_lower = url.lower()
        
        if 'vk.com' in url_lower or 'vkontakte' in url_lower:
            return ('vk', url)
        elif 'youtube' in url_lower:
            return ('youtube', url)
        elif 'instagram' in url_lower or 'instagr.am' in url_lower:
            return ('instagram', url)
        elif 't.me' in url_lower or 'telegram' in url_lower:
            return ('telegram', url)
        elif 'twitter' in url_lower or 'x.com' in url_lower:
            return ('twitter', url)
        elif 'tiktok' in url_lower:
            return ('tiktok', url)
        else:
            return ('website', url)
