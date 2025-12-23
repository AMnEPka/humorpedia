#!/usr/bin/env python3
"""
Скрипт для массового импорта персон из JSON в MongoDB

Использование:
    python3 import_people.py --file people_data.json
    python3 import_people.py --file people_data.json --dry-run

Формат JSON файла:
[
    {
        "title": "Фамилия Имя",
        "slug": "slug-name",
        "full_name": "Полное имя",
        "bio_content": "<p>Биография</p>",
        "birth_date": "1989-02-09",
        "birth_place": "Город",
        "occupation": ["актер"],
        "achievements": ["достижение"],
        "tags": ["тег1", "тег2"],
        "social_links": {"vk": "url"},
        "timeline_events": [
            {"year": "2010", "title": "Событие", "description": "Описание"}
        ],
        "rating": {"average": 4.5, "count": 10},
        "image_url": "/media/people/photo.jpg"
    }
]
"""
import os
import sys
import json
import argparse
import pymongo
from utils import create_person_document, MONGO_URL, DB_NAME


def import_people_from_json(json_file, dry_run=False, update_existing=False):
    """
    Импорт персон из JSON файла
    
    Args:
        json_file: Путь к JSON файлу с данными
        dry_run: Только проверить данные, не записывать
        update_existing: Обновлять существующие записи
    
    Returns:
        dict: Статистика импорта
    """
    stats = {
        'total': 0,
        'imported': 0,
        'updated': 0,
        'skipped': 0,
        'errors': []
    }
    
    # Загрузка данных
    with open(json_file, 'r', encoding='utf-8') as f:
        people_data = json.load(f)
    
    stats['total'] = len(people_data)
    print(f"Загружено {stats['total']} записей из {json_file}")
    
    if dry_run:
        print("\n[DRY RUN] Проверка данных без записи в БД")
        for person in people_data:
            print(f"  - {person.get('title')} ({person.get('slug')})")
        return stats
    
    # Подключение к MongoDB
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    for person in people_data:
        try:
            slug = person.get('slug')
            if not slug:
                stats['errors'].append(f"Нет slug для: {person.get('title')}")
                continue
            
            # Проверка существующей записи
            existing = db.people.find_one({'slug': slug})
            
            if existing and not update_existing:
                print(f"  [SKIP] {person.get('title')} - уже существует")
                stats['skipped'] += 1
                continue
            
            # Создание документа
            doc = create_person_document(
                title=person.get('title'),
                slug=slug,
                full_name=person.get('full_name'),
                bio_content=person.get('bio_content', ''),
                birth_date=person.get('birth_date'),
                birth_place=person.get('birth_place'),
                occupation=person.get('occupation'),
                achievements=person.get('achievements'),
                tags=person.get('tags'),
                social_links=person.get('social_links'),
                timeline_events=person.get('timeline_events'),
                rating=person.get('rating'),
                image_url=person.get('image_url')
            )
            
            if existing:
                # Обновление
                doc['_id'] = existing['_id']  # Сохраняем оригинальный ID
                db.people.replace_one({'slug': slug}, doc)
                print(f"  [UPDATE] {person.get('title')}")
                stats['updated'] += 1
            else:
                # Вставка
                db.people.insert_one(doc)
                print(f"  [INSERT] {person.get('title')}")
                stats['imported'] += 1
        
        except Exception as e:
            stats['errors'].append(f"{person.get('title')}: {str(e)}")
            print(f"  [ERROR] {person.get('title')}: {e}")
    
    client.close()
    
    # Итоги
    print(f"\n{'='*50}")
    print(f"Импорт завершён:")
    print(f"  Всего: {stats['total']}")
    print(f"  Импортировано: {stats['imported']}")
    print(f"  Обновлено: {stats['updated']}")
    print(f"  Пропущено: {stats['skipped']}")
    print(f"  Ошибок: {len(stats['errors'])}")
    
    if stats['errors']:
        print("\nОшибки:")
        for err in stats['errors']:
            print(f"  - {err}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Импорт персон из JSON в MongoDB')
    parser.add_argument('--file', '-f', required=True, help='Путь к JSON файлу с данными')
    parser.add_argument('--dry-run', action='store_true', help='Только проверить данные')
    parser.add_argument('--update', action='store_true', help='Обновлять существующие записи')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"Файл не найден: {args.file}")
        sys.exit(1)
    
    import_people_from_json(args.file, dry_run=args.dry_run, update_existing=args.update)


if __name__ == '__main__':
    main()
