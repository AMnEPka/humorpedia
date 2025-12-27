"""Парсер для модуля rating_widget."""

from typing import Optional
from .base import BaseParser, ParseContext


class RatingParser(BaseParser):
    """Парсер рейтинга.
    
    Конфигурация:
        style: 'smileys' | 'stars' | 'numeric'
    """
    
    module_type = "rating_widget"
    default_title = "Оценка"
    
    def parse(self, ctx: ParseContext) -> Optional[dict]:
        # Берём рейтинг из контекста (site_content.rating и site_content.votes)
        rating = {
            'average': round(ctx.rating, 2) if ctx.rating else 0.0,
            'count': ctx.votes if ctx.votes else 0
        }
        
        # Если рейтинг не найден в site_content, пробуем TV поле
        if rating['count'] == 0 and 'rating' in ctx.tv_data:
            rating_data = ctx.tv_data['rating']
            if isinstance(rating_data, dict):
                rating = rating_data
            elif isinstance(rating_data, (int, float)):
                rating = {'average': float(rating_data), 'count': 1}
        
        # Всегда возвращаем данные - это системный модуль
        return {
            'title': self.config.get('title', self.default_title),
            'style': self.config.get('style', 'smileys'),
            'rating': rating
        }
