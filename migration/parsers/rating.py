"""Парсер для модуля rating_widget."""

import subprocess
import re
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
        rating = {'average': 0.0, 'count': 0}
        
        # 1. Пробуем TV поле
        if 'rating' in ctx.tv_data:
            rating_data = ctx.tv_data['rating']
            if isinstance(rating_data, dict):
                rating = rating_data
            elif isinstance(rating_data, (int, float)):
                rating = {'average': float(rating_data), 'count': 1}
        
        # 2. Извлекаем из SQL если есть файл и resource_id
        if rating['count'] == 0 and ctx.sql_file and ctx.resource_id:
            rating = self._extract_from_sql(ctx.sql_file, ctx.resource_id)
        
        # Всегда возвращаем данные - это системный модуль
        return {
            'title': self.config.get('title', self.default_title),
            'style': self.config.get('style', 'smileys'),
            'rating': rating
        }
    
    def _extract_from_sql(self, sql_file: str, resource_id: int) -> dict:
        """Извлекает рейтинг из SQL дампа."""
        pattern = f"\\([0-9]+,{resource_id},[0-9]+,[0-9]+\\)"
        
        try:
            result = subprocess.run(
                ['grep', '-oE', pattern, sql_file],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0 or not result.stdout.strip():
                return {'average': 0.0, 'count': 0}
            
            votes = []
            total = 0
            
            for match in result.stdout.strip().split('\n'):
                parts = match.strip('()').split(',')
                if len(parts) >= 4:
                    score = int(parts[3])
                    votes.append(score)
                    total += score
            
            avg = total / len(votes) if votes else 0.0
            
            return {
                'average': round(avg, 2),
                'count': len(votes)
            }
        
        except Exception:
            return {'average': 0.0, 'count': 0}
