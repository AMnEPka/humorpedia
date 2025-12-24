#!/usr/bin/env python3
"""
Утилиты для миграции данных Humorpedia
"""
import os
import re
import subprocess
from uuid import uuid4
from html import unescape
from datetime import datetime, timezone


def normalize_rich_text(value: str) -> str:
    """Нормализует HTML/текст из SQL/TV, где часто встречаются экранированные последовательности.

    Цель: на выходе получить валидный HTML без артефактов вида \\r\\n, \\" и \\/,
    чтобы React мог безопасно рендерить его через dangerouslySetInnerHTML.
    """
    if not value:
        return ""

    # 1) HTML entities (&lt; &gt; &amp; ...)
    value = unescape(value)

    # 2) Частые SQL/JSON-экранирования (двойные слеши)
    #    Важно: порядок имеет значение (сначала \\r\\n, потом \\n и т.д.)
    value = value.replace('\\r\\n', '\n').replace('\\r', '\n')
    value = value.replace('\\n', '\n')

    # 3) Экранированные кавычки и слеши внутри HTML-атрибутов/тегов
    value = value.replace('\\"', '"')
    value = value.replace("\\'", "'")
    value = value.replace('\\/', '/')

    # 4) Иногда попадаются лишние обратные слэши перед < или >
    value = value.replace('\\<', '<').replace('\\>', '>')

    # 5) Неразрывные пробелы
    value = value.replace('\u00a0', ' ').replace('&nbsp;', ' ')

    return value.strip()

# MongoDB настройки
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'humorpedia')

def clean_html(text):
    """Очистка HTML-сущностей и нормализация текста.

    NB: В миграции мы часто получаем HTML как строку с экранированиями (\\r\\n, \\" и т.п.).
    Для этого используем normalize_rich_text.
    """
    return normalize_rich_text(text)



def extract_ratings_from_sql(sql_file, resource_id):
    """
    Извлечение рейтингов из SQL-дампа через grep (без загрузки файла в память)
    
    Args:
        sql_file: Путь к SQL файлу
        resource_id: ID ресурса в MODX
    
    Returns:
        dict: {'average': float, 'count': int, 'votes': list}
    """
    pattern = f"\\([0-9]+,{resource_id},[0-9]+,[0-9]+\\)"
    
    try:
        result = subprocess.run(
            ['grep', '-oE', pattern, sql_file],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            return {'average': 0.0, 'count': 0, 'votes': []}
        
        votes = []
        total = 0
        
        for match in result.stdout.strip().split('\n'):
            # Parse (id, rid, user_id, score)
            parts = match.strip('()').split(',')
            if len(parts) >= 4:
                score = int(parts[3])
                votes.append({
                    'user_id': int(parts[2]),
                    'score': score
                })
                total += score
        
        avg = total / len(votes) if votes else 0.0
        
        return {
            'average': round(avg, 2),
            'count': len(votes),
            'votes': votes
        }
    
    except subprocess.TimeoutExpired:
        print(f"Timeout while extracting ratings for ID {resource_id}")
        return {'average': 0.0, 'count': 0, 'votes': []}
    except Exception as e:
        print(f"Error extracting ratings: {e}")
        return {'average': 0.0, 'count': 0, 'votes': []}


def find_resource_id_by_name(sql_file, name):
    """
    Поиск ID ресурса по имени в SQL-дампе
    
    Args:
        sql_file: Путь к SQL файлу
        name: Имя для поиска (например, "Чеснокова Ирина")
    
    Returns:
        str or None: ID ресурса
    """
    pattern = f"([0-9]*,'document','text/html','{name}"
    
    try:
        result = subprocess.run(
            ['grep', '-o', pattern, sql_file],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            return None
        
        # Extract ID from first match
        match = re.search(r'\((\d+),', result.stdout)
        if match:
            return match.group(1)
        
        return None
    
    except Exception as e:
        print(f"Error finding resource: {e}")
        return None


def create_person_document(
    title,
    slug,
    full_name=None,
    bio_content="",
    birth_date=None,
    birth_place=None,
    occupation=None,
    achievements=None,
    tags=None,
    social_links=None,
    timeline_events=None,
    rating=None,
    image_url=None
):
    """
    Создание документа персоны для MongoDB
    
    Returns:
        dict: Готовый документ для вставки в коллекцию people
    """
    modules = []
    
    # Биография
    if bio_content:
        modules.append({
            'id': str(uuid4()),
            'type': 'text_block',
            'order': 1,
            'title': None,
            'visible': True,
            'data': {
                'title': 'Биография',
                'content': normalize_rich_text(bio_content)
            }
        })
    
    # Таймлайн
    if timeline_events:
        modules.append({
            'id': str(uuid4()),
            'type': 'timeline',
            'order': 2,
            'title': None,
            'visible': True,
            'data': {
                'title': 'Хронология',
                'events': timeline_events
            }
        })
    
    return {
        '_id': str(uuid4()),
        'content_type': 'person',
        'title': title,
        'slug': slug,
        'full_name': full_name or title,
        'status': 'published',
        'tags': tags or [],
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'bio': {
            'birth_date': birth_date,
            'birth_place': birth_place,
            'occupation': occupation or [],
            'achievements': achievements or []
        },
        'social_links': social_links or {},
        'modules': modules,
        'rating': rating or {'average': 0.0, 'count': 0},
        'views_count': 0,
        'views': 0,
        'team_ids': [],
        'show_ids': [],
        'article_ids': [],
        'featured': False,
        'image': image_url,
        'seo': {
            'meta_title': title,
            'meta_description': bio_content[:160] if bio_content else ''
        }
    }


def transliterate(text):
    """
    Транслитерация русского текста в латиницу для slug
    """
    trans = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        ' ': '-'
    }
    
    result = []
    for char in text.lower():
        result.append(trans.get(char, char))
    
    slug = ''.join(result)
    # Remove multiple dashes and clean up
    slug = re.sub(r'-+', '-', slug)
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    return slug.strip('-')
