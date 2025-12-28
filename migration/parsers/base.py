"""Базовый класс для всех парсеров модулей."""

from __future__ import annotations
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4
from html import unescape
from urllib.parse import urlparse


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
        """Нормализует MIGX JSON строку для парсинга."""
        if not text:
            return ""
        
        # Удаляем все управляющие символы
        text = re.sub(r'[\x00-\x09\x0b-\x1f]', '', text)
        text = text.replace('\\r\\n', ' ').replace('\\r', ' ').replace('\\n', ' ')
        text = text.replace('>\\<', '><')
        text = text.replace('\\"', '"')
        text = text.replace("\\'", "'")
        text = text.replace('\\/', '/')
        text = text.replace('\\<', '<').replace('\\>', '>')
        # Заменяем переносы на пробелы для валидного JSON
        text = text.replace('\n', ' ')
        
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
        
        url_lower = url.lower().strip()

        # Parse the URL to safely inspect its components
        parsed = urlparse(url_lower)
        host = parsed.hostname or ""

        # Handle scheme-less inputs like "vk.com/user" or "instagram.com/user"
        if not host:
            # If there is no scheme and netloc, try to treat the first
            # non-empty path segment as a pseudo-host for classification.
            if not parsed.scheme and not parsed.netloc and parsed.path:
                first_segment = parsed.path.split("/")[0]
                host = first_segment
            else:
                host = ""

        host = host.lower()

        def is_host_for(domain: str) -> bool:
            return host == domain or host.endswith("." + domain)

        # Prefer host-based checks when available
        if host:
            if is_host_for("vk.com") or "vkontakte" in host:
                return ("vk", url)
            if is_host_for("youtube.com") or is_host_for("youtu.be"):
                return ("youtube", url)
            if is_host_for("instagram.com") or is_host_for("instagr.am"):
                return ("instagram", url)
            if is_host_for("t.me") or is_host_for("telegram.me") or "telegram" in host:
                return ("telegram", url)
            if is_host_for("twitter.com") or is_host_for("x.com"):
                return ("twitter", url)
            if is_host_for("tiktok.com"):
                return ("tiktok", url)
            return ("website", url)

        # Fallback for completely unparseable inputs without a host:
        # keep loose matching for backward compatibility, but avoid
        # relying on arbitrary domain-like substrings in the full URL.
        first_segment = ""
        if parsed.path:
            first_segment = parsed.path.split("/")[0].lower()

        def _segment_contains_token(segment: str, token: str) -> bool:
            """
            Check if the given token appears in the segment as a separate word
            (for example 'vk' in 'vk', 'vk123', '123vk', 'vk_com'), but avoid
            arbitrary substring matches inside long strings.
            """
            if not segment:
                return False
            pattern = r"\b" + re.escape(token) + r"\b"
            return re.search(pattern, segment) is not None

        # Match known services based on the first path segment only.
        # This avoids scanning the entire URL string for domain substrings.
        if first_segment in ("vk.com", "vkontakte") or _segment_contains_token(first_segment, "vk"):
            return ("vk", url)
        if first_segment in ("youtube.com", "youtu.be", "youtube") or _segment_contains_token(first_segment, "youtube"):
            return ("youtube", url)
        if first_segment in ("instagram.com", "instagr.am", "instagram") or _segment_contains_token(first_segment, "instagram"):
            return ("instagram", url)
        if first_segment in ("t.me", "telegram.me", "telegram") or _segment_contains_token(first_segment, "telegram"):
            return ("telegram", url)
        # Treat "x.com" specially: only consider it when it appears as
        # the leading path segment (e.g. "x.com/..." without a scheme).
        x_in_path = False
        if parsed.path:
            first_segment = parsed.path.split("/")[0]
            if first_segment == "x.com" or first_segment.startswith("x.com?") or first_segment.startswith("x.com#"):
                x_in_path = True
        if _segment_contains_token(first_segment.lower(), "twitter") or x_in_path:
            return ("twitter", url)
        if _segment_contains_token(first_segment.lower(), "tiktok") or first_segment.lower() in ("tiktok.com", "tiktok"):
            return ("tiktok", url)
        return ("website", url)
