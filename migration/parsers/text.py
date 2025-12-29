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
                        # Для text секций
                        if form == 'text':
                            text = sec.get('content', '') or sec.get('subtitle', '')
                            title = sec.get('title', '')
                            if text:
                                # Нормализуем изображения в тексте
                                text = self._normalize_images_in_html(text, ctx.image_map)
                                if title:
                                    contents.append(f'<h3>{title}</h3>{text}')
                                else:
                                    contents.append(text)
                        # Для table секций (таблицы)
                        elif form == 'table':
                            table_content = sec.get('content', '')
                            if table_content:
                                # Нормализуем изображения в таблице
                                table_content = self._normalize_images_in_html(table_content, ctx.image_map)
                                contents.append(table_content)
                        # Для quote секций (цитаты)
                        elif form == 'quote':
                            quote_text = sec.get('content', '') or sec.get('text', '')
                            if quote_text:
                                # Нормализуем изображения в цитате
                                quote_text = self._normalize_images_in_html(quote_text, ctx.image_map)
                                contents.append(f'<blockquote>{quote_text}</blockquote>')
                        # Для остальных секций
                        else:
                            text = sec.get('content', '') or sec.get('subtitle', '')
                            title = sec.get('title', '')
                            if text:
                                # Нормализуем изображения в тексте
                                text = self._normalize_images_in_html(text, ctx.image_map)
                                if title:
                                    contents.append(f'<h3>{title}</h3>{text}')
                                else:
                                    contents.append(text)
                content = ''.join(contents)
                # Дополнительно нормализуем весь контент на случай, если что-то пропустили
                content = self._normalize_images_in_html(content, ctx.image_map)
        
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
        
        # Нормализуем изображения в HTML контенте (добавляем /media/imported/ если нужно)
        content = self._normalize_images_in_html(content, ctx.image_map)
        
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
    
    def _normalize_images_in_html(self, html: str, image_map: dict = None) -> str:
        """Нормализует пути к изображениям в HTML, добавляя префикс /media/imported/."""
        if not html:
            return html
        
        IMAGE_PREFIX = "/media/imported/"
        
        def normalize_image_url(url: str) -> str:
            """Нормализует URL изображения."""
            if not url:
                return url
            
            # Проверяем маппинг
            if image_map and url in image_map:
                url = image_map[url]
            
            # Уже абсолютный URL
            if url.startswith('http://') or url.startswith('https://'):
                return url
            
            # Уже имеет правильный префикс
            if url.startswith('/media/imported/'):
                return url
            
            # Добавляем префикс
            if not url.startswith('/'):
                return f"{IMAGE_PREFIX}{url.lstrip('/')}"
            
            return f"{IMAGE_PREFIX}{url.lstrip('/')}"
        
        # Заменяем все src атрибуты в img тегах
        def replace_src(match):
            full_tag = match.group(0)
            # match.group(1) - атрибуты до src, match.group(2) - значение src
            src_value = match.group(2)
            normalized_src = normalize_image_url(src_value)
            return full_tag.replace(src_value, normalized_src)
        
        # Ищем все img теги с src атрибутами
        html = re.sub(
            r'<img([^>]+)src=["\']([^"\'>]+)["\']',
            replace_src,
            html,
            flags=re.IGNORECASE
        )
        
        return html
    
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
                    normalized_content = self.normalize_html(content)
                    normalized_content = self._normalize_images_in_html(normalized_content, ctx.image_map)
                    results.append({
                        'title': self.normalize_html(title) if title else '',
                        'content': normalized_content
                    })
            
            # Обрабатываем table секции как текстовые блоки
            elif form == 'table':
                content = sec.get('content', '')
                if content:
                    normalized_content = self.normalize_html(content)
                    normalized_content = self._normalize_images_in_html(normalized_content, ctx.image_map)
                    results.append({
                        'title': '',
                        'content': normalized_content
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
