"""Парсер для модуля poster_photo."""

from typing import Optional
from .base import BaseParser, ParseContext


class PhotoParser(BaseParser):
    """Парсер фото/постера.
    
    Конфигурация:
        selector: CSS-подобный селектор для поиска изображения
        tv_field: Название TV поля с изображением
        fallback_tv_fields: Список запасных TV полей
        size: 'small' | 'medium' | 'large'
        shape: 'square' | 'rounded' | 'circle'
    """
    
    module_type = "poster_photo"
    default_title = "Фото"
    
    # Базовый путь для изображений
    IMAGE_PREFIX = "/media/imported/"
    
    def parse(self, ctx: ParseContext) -> Optional[dict]:
        image_url = None
        
        # 1. Пробуем TV поле
        tv_field = self.config.get('tv_field', 'image')
        if tv_field and tv_field in ctx.tv_data:
            image_url = ctx.tv_data[tv_field]
        
        # 2. Пробуем запасные TV поля
        if not image_url:
            for field in self.config.get('fallback_tv_fields', ['photo', 'poster', 'img', 'image']):
                if field in ctx.tv_data and ctx.tv_data[field]:
                    image_url = ctx.tv_data[field]
                    break
        
        # 3. Ищем в HTML
        if not image_url and ctx.html:
            image_url = self.find_first_image(ctx.html)
        
        # 4. Проверяем image_map
        if image_url and ctx.image_map:
            # Если это ID, конвертируем в URL
            if image_url in ctx.image_map:
                image_url = ctx.image_map[image_url]
        
        # 5. Добавляем префикс если нужно
        if image_url:
            image_url = self._normalize_image_url(image_url)
        
        # Возвращаем данные (модуль создаётся всегда)
        return {
            'url': image_url or '',
            'size': self.config.get('size', 'medium'),
            'shape': self.config.get('shape', 'rounded')
        }
    
    def _normalize_image_url(self, url: str) -> str:
        """Нормализует URL изображения, добавляя префикс если нужно."""
        if not url:
            return ''
        
        # Уже абсолютный URL
        if url.startswith('http://') or url.startswith('https://'):
            return url
        
        # Уже имеет правильный префикс
        if url.startswith('/media/imported/'):
            return url
        
        # Убираем начальный слеш если есть
        url = url.lstrip('/')
        
        # Если путь начинается с images/, добавляем префикс
        if url.startswith('images/'):
            return f"{self.IMAGE_PREFIX}{url}"
        
        # Иначе просто добавляем префикс
        return f"{self.IMAGE_PREFIX}{url}"
