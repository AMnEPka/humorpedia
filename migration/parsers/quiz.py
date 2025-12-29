"""Парсер для модулей quiz_questions и quiz_results."""

import json
import re
from typing import Optional, List, Dict, Any
from .base import BaseParser, ParseContext


class QuizParser(BaseParser):
    """Парсер квизов (вопросы и результаты).
    
    Конфигурация:
        tv_field: Название TV поля (quiz_questions или quiz_final)
    """
    
    module_type = "quiz_questions"
    default_title = "Вопросы квиза"
    
    IMAGE_PREFIX = "/media/imported/"
    
    def parse(self, ctx: ParseContext) -> Optional[dict]:
        """Парсит вопросы квиза из TV поля quiz_questions."""
        tv_field = self.config.get('tv_field', 'quiz_questions')
        
        if tv_field not in ctx.tv_data:
            return None
        
        quiz_data = ctx.tv_data[tv_field]
        if not quiz_data:
            return None
        
        # Парсим MIGX JSON
        questions_data = self._parse_migx(quiz_data)
        if not questions_data:
            return None
        
        questions = []
        for idx, q_data in enumerate(questions_data, 1):
            question_text = q_data.get('question', '') or q_data.get('title', '')
            if not question_text:
                continue
            
            # Изображение вопроса
            question_image = q_data.get('image', '') or q_data.get('img', '')
            if question_image:
                question_image = self._normalize_image_url(question_image, ctx.image_map)
            
            # Варианты ответов
            options = []
            
            # Пробуем разные форматы хранения ответов
            # Формат 1: answer1, answer2, ... answerN, correct1, correct2, ...
            # Формат 2: options как JSON строка
            # Формат 3: options как MIGX секция
            
            # Ищем все поля answer*
            answer_fields = {}
            correct_fields = {}
            for key, value in q_data.items():
                if key.startswith('answer') and key[6:].isdigit():
                    idx_num = int(key[6:])
                    answer_fields[idx_num] = value
                elif key.startswith('correct') and key[7:].isdigit():
                    idx_num = int(key[7:])
                    correct_fields[idx_num] = value
            
            # Если есть answer поля
            if answer_fields:
                for idx_num in sorted(answer_fields.keys()):
                    answer_text = answer_fields[idx_num]
                    if not answer_text:
                        continue
                    
                    # Определяем правильность ответа
                    is_correct = False
                    if idx_num in correct_fields:
                        correct_val = str(correct_fields[idx_num]).lower()
                        is_correct = correct_val in ('1', 'true', 'yes', 'да', 'y')
                    elif 'correct' in q_data:
                        # Может быть одно поле correct с номером правильного ответа
                        correct_num = q_data.get('correct', '')
                        if str(correct_num) == str(idx_num):
                            is_correct = True
                    
                    option_id = chr(96 + idx_num)  # a, b, c, d...
                    options.append({
                        'id': option_id,
                        'text': self.normalize_html(answer_text),
                        'correct': is_correct
                    })
            
            # Если нет answer полей, пробуем options как JSON
            if not options:
                options_str = q_data.get('options', '')
                if options_str:
                    try:
                        if isinstance(options_str, str):
                            options_data = json.loads(options_str)
                        else:
                            options_data = options_str
                        
                        if isinstance(options_data, list):
                            for opt_idx, opt in enumerate(options_data):
                                if isinstance(opt, dict):
                                    opt_id = opt.get('id', chr(96 + opt_idx + 1))
                                    opt_text = opt.get('text', '') or opt.get('answer', '')
                                    opt_correct = opt.get('correct', False) or opt.get('is_correct', False)
                                    if opt_text:
                                        options.append({
                                            'id': str(opt_id),
                                            'text': self.normalize_html(opt_text),
                                            'correct': bool(opt_correct)
                                        })
                    except:
                        pass
            
            # Если всё ещё нет вариантов, пропускаем вопрос
            if not options:
                continue
            
            # Объяснение ответа
            explanation = q_data.get('explanation', '') or q_data.get('comment', '')
            if explanation:
                explanation = self.normalize_html(explanation)
            
            questions.append({
                'id': idx,
                'question': self.normalize_html(question_text),
                'image': question_image or None,
                'options': options,
                'explanation': explanation or None
            })
        
        if not questions:
            return None
        
        return {
            'questions': questions
        }
    
    def _normalize_image_url(self, url: str, image_map: Dict = None) -> str:
        """Нормализует URL изображения."""
        if not url:
            return ''
        
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
            return f"{self.IMAGE_PREFIX}{url.lstrip('/')}"
        
        return f"{self.IMAGE_PREFIX}{url.lstrip('/')}"
    
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


class QuizResultsParser(BaseParser):
    """Парсер результатов квиза."""
    
    module_type = "quiz_results"
    default_title = "Результаты"
    
    IMAGE_PREFIX = "/media/imported/"
    
    def parse(self, ctx: ParseContext) -> Optional[dict]:
        """Парсит результаты квиза из TV поля quiz_final."""
        tv_field = self.config.get('tv_field', 'quiz_final')
        
        if tv_field not in ctx.tv_data:
            return None
        
        quiz_final = ctx.tv_data[tv_field]
        if not quiz_final:
            return None
        
        # Парсим MIGX JSON
        results_data = self._parse_migx(quiz_final)
        if not results_data:
            return None
        
        results = []
        for r_data in results_data:
            # Диапазон баллов
            min_score = self._parse_int(r_data.get('min_score', 0))
            max_score = self._parse_int(r_data.get('max_score', 100))
            
            # Если нет явных границ, пробуем другие поля
            if min_score == 0 and max_score == 100:
                min_score = self._parse_int(r_data.get('min', 0))
                max_score = self._parse_int(r_data.get('max', 100))
            
            title = r_data.get('title', '') or r_data.get('name', '')
            description = r_data.get('description', '') or r_data.get('text', '') or r_data.get('content', '')
            
            if not title and not description:
                continue
            
            # Изображение результата
            result_image = r_data.get('image', '') or r_data.get('img', '')
            if result_image:
                result_image = self._normalize_image_url(result_image, ctx.image_map)
            
            results.append({
                'min_score': min_score,
                'max_score': max_score,
                'title': self.normalize_html(title),
                'description': self.normalize_html(description),
                'image': result_image or None
            })
        
        if not results:
            return None
        
        # Сортируем по min_score
        results.sort(key=lambda x: x['min_score'])
        
        return {
            'results': results
        }
    
    def _parse_int(self, value: Any) -> int:
        """Парсит целое число из различных форматов."""
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            # Убираем всё кроме цифр
            digits = re.sub(r'[^\d]', '', value)
            if digits:
                return int(digits)
        return 0
    
    def _normalize_image_url(self, url: str, image_map: Dict = None) -> str:
        """Нормализует URL изображения."""
        if not url:
            return ''
        
        if image_map and url in image_map:
            url = image_map[url]
        
        if url.startswith('http://') or url.startswith('https://'):
            return url
        
        if url.startswith('/media/imported/'):
            return url
        
        if not url.startswith('/'):
            return f"{self.IMAGE_PREFIX}{url.lstrip('/')}"
        
        return f"{self.IMAGE_PREFIX}{url.lstrip('/')}"
    
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

