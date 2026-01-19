#!/usr/bin/env python3
"""
Скрипт для исправления документа сезона КВН 2011 года.
Заполняет недостающие поля по аналогии с автоматически импортированным сезоном 2015 года.
"""

import os
import sys
import json
from pprint import pprint
from uuid import uuid4

# Добавляем путь к корню проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo

# MongoDB настройки
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'humorpedia')

# ID документов для сравнения
SEASON_2015_ID = "2b5a31a8-2145-4c07-b265-5edda64eb97b"  # Автоматический импорт
SEASON_2011_ID = "056c1c06-1d0b-45ee-9572-0a3701ca128b"  # Ручное создание


def get_document(db, doc_id: str):
    """Получает документ по _id"""
    return db.kvn.find_one({"_id": doc_id})


def compare_documents(doc1, doc2):
    """Сравнивает два документа и показывает различия"""
    print("\n" + "="*80)
    print("СРАВНЕНИЕ ДОКУМЕНТОВ")
    print("="*80)
    
    # Собираем все ключи
    keys1 = set(doc1.keys())
    keys2 = set(doc2.keys())
    
    only_in_1 = keys1 - keys2
    only_in_2 = keys2 - keys1
    common = keys1 & keys2
    
    print(f"\nКлючи только в документе 2015 (автоимпорт): {sorted(only_in_1)}")
    print(f"Ключи только в документе 2011 (ручное): {sorted(only_in_2)}")
    
    print(f"\nОбщие ключи с разными значениями:")
    for key in sorted(common):
        val1 = doc1.get(key)
        val2 = doc2.get(key)
        if val1 != val2:
            print(f"\n  {key}:")
            print(f"    2015: {type(val1).__name__} = {str(val1)[:100]}")
            print(f"    2011: {type(val2).__name__} = {str(val2)[:100]}")


def update_season_2011(db, season_2015_doc, season_2011_doc, apply: bool = False):
    """Обновляет документ 2011 года по аналогии с 2015"""
    
    print("\n" + "="*80)
    print("ОБНОВЛЕНИЕ ДОКУМЕНТА 2011 ГОДА")
    print("="*80)
    
    updates = {}
    
    # 1. Поле id (дублирующее _id)
    if "id" not in season_2011_doc or not season_2011_doc.get("id"):
        season_2011_id = season_2011_doc.get("_id")
        if season_2011_id:
            # Используем существующий _id как id
            updates["id"] = season_2011_id
            print(f"[OK] Добавляем поле id: {season_2011_id}")
        else:
            # Генерируем новый UUID
            updates["id"] = str(uuid4())
            print(f"[OK] Генерируем новое поле id: {updates['id']}")
    else:
        print(f"[INFO] Поле id уже существует: {season_2011_doc.get('id')}")
    
    # 2. Поле seo
    seo_2011 = season_2011_doc.get("seo", {})
    seo_2015 = season_2015_doc.get("seo", {})
    
    # Проверяем, нужно ли обновить seo (если его нет или оно пустое)
    needs_seo_update = False
    if not seo_2011:
        needs_seo_update = True
    else:
        # Проверяем, пустое ли meta_title или meta_description
        meta_title = seo_2011.get("meta_title", "") if isinstance(seo_2011, dict) else ""
        meta_description = seo_2011.get("meta_description", "") if isinstance(seo_2011, dict) else ""
        if not meta_title or not meta_description:
            needs_seo_update = True
    
    if needs_seo_update:
        # Используем структуру из 2015, но с данными 2011
        title = season_2011_doc.get("title") or season_2011_doc.get("name", "")
        description = season_2011_doc.get("description", "")
        
        # Берем шаблон из 2015, если есть
        if seo_2015 and isinstance(seo_2015, dict):
            # Используем структуру из 2015, но заполняем данными 2011
            new_seo = {
                "meta_title": title if not meta_title else meta_title,
                "meta_description": description[:500] if description and not meta_description else (meta_description if meta_description else "")
            }
            # Сохраняем другие поля из существующего seo, если они есть
            if isinstance(seo_2011, dict):
                new_seo.update({k: v for k, v in seo_2011.items() if k not in ["meta_title", "meta_description"]})
            updates["seo"] = new_seo
            print(f"[OK] Обновляем поле seo: {updates['seo']}")
        else:
            # Создаем по умолчанию
            new_seo = {
                "meta_title": title,
                "meta_description": description[:500] if description else ""
            }
            # Сохраняем другие поля из существующего seo, если они есть
            if isinstance(seo_2011, dict):
                new_seo.update({k: v for k, v in seo_2011.items() if k not in ["meta_title", "meta_description"]})
            updates["seo"] = new_seo
            print(f"[OK] Создаем поле seo по умолчанию: {updates['seo']}")
    else:
        print(f"[INFO] Поле seo уже заполнено: {seo_2011}")
    
    # 3. Поле rating
    if "rating" not in season_2011_doc or not season_2011_doc.get("rating"):
        # Берем rating из 2015 или создаем по умолчанию
        rating_2015 = season_2015_doc.get("rating", {})
        if rating_2015 and isinstance(rating_2015, dict):
            updates["rating"] = {
                "average": rating_2015.get("average", 0.0),
                "count": rating_2015.get("count", 0)
            }
            print(f"[OK] Добавляем поле rating из 2015: {updates['rating']}")
        else:
            updates["rating"] = {"average": 0.0, "count": 0}
            print(f"[OK] Создаем поле rating по умолчанию: {updates['rating']}")
    else:
        print(f"[INFO] Поле rating уже существует: {season_2011_doc.get('rating')}")
    
    # 4. Удаляем modules, если есть season_data
    if "season_data" in season_2011_doc and season_2011_doc.get("season_data"):
        if "modules" in season_2011_doc and season_2011_doc.get("modules"):
            # Не удаляем modules, но можем их скрыть или оставить как есть
            # По запросу пользователя: "блок modules не нужен, мы для данных используем блок season_data"
            # Но modules могут содержать другой контент, поэтому просто оставим их
            print(f"[INFO] У документа есть season_data и modules. Modules оставляем (могут содержать другой контент).")
    
    # 5. Проверяем season_data для статистики жюри
    season_data_2011 = season_2011_doc.get("season_data", {})
    if not season_data_2011:
        print(f"[WARNING] ВНИМАНИЕ: У документа 2011 года нет season_data!")
        print(f"    Это может быть причиной, почему сезон не отображается в статистике жюри.")
        print(f"    Статистика жюри ищет документы по season_data.league_slug и season_data.year")
    else:
        league_slug = season_data_2011.get("league_slug")
        year = season_data_2011.get("year")
        print(f"[INFO] season_data существует:")
        print(f"    league_slug: {league_slug}")
        print(f"    year: {year}")
        
        # Проверяем, что league_slug и year заполнены
        if not league_slug:
            print(f"[WARNING] ВНИМАНИЕ: season_data.league_slug не заполнен!")
            # Пытаемся определить league_slug из full_path
            full_path = season_2011_doc.get("full_path", "")
            if full_path:
                path_parts = full_path.split("/")
                if len(path_parts) >= 2:
                    potential_league = path_parts[1]
                    print(f"    Пытаемся использовать league_slug из full_path: {potential_league}")
                    # Обновляем season_data с league_slug
                    if "season_data" not in updates:
                        updates["season_data"] = season_data_2011.copy()
                    updates["season_data"]["league_slug"] = potential_league
                    print(f"[OK] Добавляем league_slug в season_data: {potential_league}")
        if not year:
            print(f"[WARNING] ВНИМАНИЕ: season_data.year не заполнен!")
    
    # Применяем обновления
    if updates and apply:
        print(f"\n[UPDATE] Применяем обновления к документу 2011 года...")
        result = db.kvn.update_one(
            {"_id": SEASON_2011_ID},
            {"$set": updates}
        )
        if result.modified_count > 0:
            print(f"[OK] Документ успешно обновлен!")
        else:
            print(f"[WARNING] Документ не был обновлен (возможно, изменения уже применены)")
    elif updates:
        print(f"\n[DRY-RUN] Dry-run режим. Для применения используйте --apply")
        print(f"   Обновления, которые будут применены:")
        pprint(updates, width=100)
    else:
        print(f"\n[OK] Все необходимые поля уже заполнены")
    
    return updates


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Исправление документа сезона КВН 2011 года'
    )
    parser.add_argument('--apply', action='store_true', help='Применить изменения в БД')
    parser.add_argument('--compare', action='store_true', help='Только сравнить документы')
    args = parser.parse_args()
    
    # Подключаемся к MongoDB
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        # Получаем документы
        print(f"[INFO] Получаем документы из коллекции kvn...")
        season_2015 = get_document(db, SEASON_2015_ID)
        season_2011 = get_document(db, SEASON_2011_ID)
        
        if not season_2015:
            print(f"[ERROR] Документ 2015 года не найден: {SEASON_2015_ID}")
            return
        
        if not season_2011:
            print(f"[ERROR] Документ 2011 года не найден: {SEASON_2011_ID}")
            return
        
        print(f"[OK] Документ 2015 года найден: {season_2015.get('title', 'N/A')}")
        print(f"[OK] Документ 2011 года найден: {season_2011.get('title', 'N/A')}")
        
        # Сравниваем документы
        if args.compare or not args.apply:
            compare_documents(season_2015, season_2011)
        
        # Обновляем документ 2011
        if not args.compare:
            updates = update_season_2011(db, season_2015, season_2011, apply=args.apply)
            
            if args.apply and updates:
                # Проверяем результат
                print(f"\n[INFO] Проверяем обновленный документ...")
                updated_doc = get_document(db, SEASON_2011_ID)
                print(f"[OK] id: {updated_doc.get('id', 'НЕТ')}")
                print(f"[OK] seo: {updated_doc.get('seo', 'НЕТ')}")
                print(f"[OK] rating: {updated_doc.get('rating', 'НЕТ')}")
                
                # Проверяем season_data для статистики жюри
                season_data = updated_doc.get("season_data", {})
                if season_data:
                    print(f"[OK] season_data.league_slug: {season_data.get('league_slug', 'НЕТ')}")
                    print(f"[OK] season_data.year: {season_data.get('year', 'НЕТ')}")
                else:
                    print(f"[WARNING] season_data отсутствует - сезон не будет отображаться в статистике жюри!")
    
    finally:
        client.close()


if __name__ == '__main__':
    main()
