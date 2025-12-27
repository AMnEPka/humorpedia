"""Парсер для модуля image_gallery."""

import re
import json
from typing import Optional, List
from .base import BaseParser, ParseContext


class GalleryParser(BaseParser):
    """Парсер галереи изображений.
    
    Конфигурация:
        tv_field: Название TV поля с JSON изображениями
        html_selector: Регулярка для поиска изображений
        max_images: Максимальное количество изображений
    """
    
    module_type = "image_gallery"
    default_title = "Галерея"
    
    def parse(self, ctx: ParseContext) -> Optional[dict]:
        images = []
        
        # 1. Пробуем TV поле (JSON)
        tv_field = self.config.get('tv_field', 'gallery')
        if tv_field and tv_field in ctx.tv_data:
            images = self._parse_images_json(ctx.tv_data[tv_field])
        
        # 2. Пробуем MIGX секцию gallery
        if not images:
            config = ctx.tv_data.get('config', '')
            if config:
                sections = self._parse_migx(config)
                for sec in sections:
                    if sec.get('MIGX_formname') == 'gallery':
                        images_data = sec.get('images', sec.get('items', []))
                        images = self._parse_images_json(images_data)
                        break
        
        # 3. Ищем все изображения в HTML
        if not images and ctx.html:
            img_urls = self.find_all_images(ctx.html)
            images = [{'url': url, 'caption': ''} for url in img_urls]
        
        if not images:
            return None
        
        # Применяем лимит
        max_images = self.config.get('max_images', 0)
        if max_images > 0:
            images = images[:max_images]
        
        return {
            'title': self.config.get('title', self.default_title),
            'images': images
        }
    
    def _parse_images_json(self, data) -> List[dict]:
        """Парсит JSON с изображениями."""
        try:
            if isinstance(data, str):
                data = json.loads(self.normalize_html(data))
            
            if isinstance(data, list):
                images = []
                for item in data:
                    if isinstance(item, dict):
                        img = {
                            'url': item.get('url', item.get('image', item.get('src', ''))),
                            'caption': item.get('caption', item.get('title', item.get('alt', '')))
                        }
                        if img['url']:
                            images.append(img)
                    elif isinstance(item, str):
                        images.append({'url': item, 'caption': ''})
                return images
        except:
            pass
        return []
    
    def _parse_migx(self, config_str: str) -> list:
        if not config_str:
            return []
        try:
            config_str = self.normalize_html(config_str)
            data = json.loads(config_str)
            return data if isinstance(data, list) else [data]
        except:
            return []
