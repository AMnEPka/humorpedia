#!/usr/bin/env python3
"""
Скрипт для извлечения данных из MODX SQL-дампа через grep
Не загружает весь файл в память, работает потоково

Использование:
    python3 extract_from_sql.py --sql modx_new.sql --name "Чеснокова Ирина"
    python3 extract_from_sql.py --sql modx_new.sql --id 148
    python3 extract_from_sql.py --sql modx_new.sql --list-people > people_ids.txt
"""
import os
import sys
import re
import json
import argparse
import subprocess
from utils import extract_ratings_from_sql, find_resource_id_by_name, clean_html, transliterate


def grep_sql(sql_file, pattern, timeout=60):
    """Выполнить grep по SQL файлу"""
    try:
        result = subprocess.run(
            ['grep', '-oE', pattern, sql_file],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout.strip().split('\n') if result.stdout.strip() else []
    except subprocess.TimeoutExpired:
        print(f"Timeout при поиске: {pattern}")
        return []
    except Exception as e:
        print(f"Ошибка grep: {e}")
        return []


def list_all_people(sql_file):
    """
    Список всех персон в SQL-дампе
    Ищет записи с шаблоном "Информация о человеке"
    """
    # Паттерн для поиска записей людей в modx_site_content
    # Формат: (id,'document','text/html','Фамилия Имя',...
    pattern = r"\([0-9]+,'document','text/html','[^']+','[^']*','[^']*','[a-z0-9-]+'"
    
    matches = grep_sql(sql_file, pattern, timeout=120)
    
    people = []
    for match in matches:
        try:
            # Parse: (id,'document','text/html','title','longtitle','description','slug'
            parts = re.match(r"\((\d+),'document','text/html','([^']+)','([^']*)','([^']*)','([^']+)'", match)
            if parts:
                resource_id = parts.group(1)
                title = parts.group(2)
                longtitle = parts.group(3) or title
                description = parts.group(4)
                slug = parts.group(5)
                
                people.append({
                    'id': resource_id,
                    'title': title,
                    'longtitle': longtitle,
                    'description': description,
                    'slug': slug
                })
        except Exception as e:
            continue
    
    return people


def extract_person_data(sql_file, resource_id=None, name=None):
    """
    Извлечение данных персоны по ID или имени
    
    Args:
        sql_file: Путь к SQL файлу
        resource_id: ID ресурса (если известен)
        name: Имя для поиска (если ID неизвестен)
    
    Returns:
        dict: Данные персоны
    """
    # Если ID не указан, ищем по имени
    if not resource_id and name:
        resource_id = find_resource_id_by_name(sql_file, name)
        if not resource_id:
            print(f"Не найден ресурс с именем: {name}")
            return None
    
    if not resource_id:
        print("Необходимо указать --id или --name")
        return None
    
    print(f"Извлечение данных для ID: {resource_id}")
    
    # 1. Получаем основные данные из site_content
    pattern = f"\\({resource_id},'document','text/html','[^']+','[^']*','[^']*','[^']+'"
    matches = grep_sql(sql_file, pattern)
    
    if not matches:
        print(f"Не найдена запись с ID {resource_id}")
        return None
    
    match = matches[0]
    parts = re.match(r"\((\d+),'document','text/html','([^']+)','([^']*)','([^']*)','([^']+)'", match)
    
    if not parts:
        print(f"Не удалось распарсить запись: {match}")
        return None
    
    title = clean_html(parts.group(2))
    longtitle = clean_html(parts.group(3)) or title
    description = clean_html(parts.group(4))
    slug = parts.group(5)
    
    # 2. Получаем рейтинги
    rating = extract_ratings_from_sql(sql_file, resource_id)
    
    # 3. Собираем результат
    result = {
        'resource_id': resource_id,
        'title': title,
        'slug': slug,
        'full_name': longtitle,
        'bio_content': f"<p>{description}</p>" if description else "",
        'rating': {
            'average': rating['average'],
            'count': rating['count']
        },
        'tags': [],
        'timeline_events': [],
        'social_links': {},
        'birth_date': None,
        'birth_place': None,
        'occupation': [],
        'achievements': [],
        'image_url': None
    }
    
    print(f"Найдено: {title} (slug: {slug})")
    print(f"Рейтинг: {rating['average']:.2f} ({rating['count']} голосов)")
    
    return result


def main():
    parser = argparse.ArgumentParser(description='Извлечение данных из MODX SQL-дампа')
    parser.add_argument('--sql', '-s', required=True, help='Путь к SQL файлу')
    parser.add_argument('--id', type=str, help='ID ресурса')
    parser.add_argument('--name', '-n', type=str, help='Имя для поиска')
    parser.add_argument('--list-people', action='store_true', help='Список всех персон')
    parser.add_argument('--output', '-o', type=str, help='Файл для вывода JSON')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.sql):
        print(f"Файл не найден: {args.sql}")
        sys.exit(1)
    
    if args.list_people:
        people = list_all_people(args.sql)
        print(f"Найдено {len(people)} записей")
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(people, f, ensure_ascii=False, indent=2)
            print(f"Сохранено в {args.output}")
        else:
            for p in people[:20]:  # Показываем первые 20
                print(f"  ID={p['id']}: {p['title']} ({p['slug']})")
            if len(people) > 20:
                print(f"  ... и ещё {len(people) - 20} записей")
    
    elif args.id or args.name:
        data = extract_person_data(args.sql, resource_id=args.id, name=args.name)
        
        if data and args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Сохранено в {args.output}")
        elif data:
            print(json.dumps(data, ensure_ascii=False, indent=2))
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
