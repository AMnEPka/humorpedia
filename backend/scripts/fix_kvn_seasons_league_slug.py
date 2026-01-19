#!/usr/bin/env python3
"""
Скрипт для исправления сезонов КВН 2010, 2012, 2013, 2014.
Добавляет league_slug в season_data для сезонов, у которых его нет.
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo

# MongoDB настройки
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'humorpedia')

# Годы для исправления
YEARS_TO_FIX = [2010, 2012, 2013, 2014]


def extract_league_slug_from_path(full_path: str) -> str:
    """Извлекает league_slug из full_path"""
    if not full_path:
        return None
    
    path_parts = full_path.split("/")
    if len(path_parts) >= 2:
        # Формат: kvn/vl-kvn/vl-2010
        return path_parts[1]
    return None


def fix_season_league_slug(db, season_doc, apply: bool = False):
    """Исправляет league_slug в season_data для сезона"""
    
    season_id = season_doc.get("_id")
    title = season_doc.get("title", "N/A")
    full_path = season_doc.get("full_path", "")
    
    season_data = season_doc.get("season_data", {})
    if not season_data:
        print(f"[WARNING] Сезон {title} ({season_id}) не имеет season_data")
        return False
    
    current_league_slug = season_data.get("league_slug")
    if current_league_slug:
        print(f"[INFO] Сезон {title} уже имеет league_slug: {current_league_slug}")
        return False
    
    # Пытаемся определить league_slug из full_path
    league_slug = extract_league_slug_from_path(full_path)
    if not league_slug:
        print(f"[WARNING] Не удалось определить league_slug из full_path: {full_path}")
        return False
    
    print(f"[OK] Найден league_slug для сезона {title}: {league_slug}")
    
    if apply:
        # Обновляем season_data
        updated_season_data = season_data.copy()
        updated_season_data["league_slug"] = league_slug
        
        result = db.kvn.update_one(
            {"_id": season_id},
            {"$set": {"season_data": updated_season_data}}
        )
        
        if result.modified_count > 0:
            print(f"[OK] Сезон {title} успешно обновлен с league_slug: {league_slug}")
            return True
        else:
            print(f"[WARNING] Сезон {title} не был обновлен")
            return False
    else:
        print(f"[DRY-RUN] Будет добавлен league_slug: {league_slug}")
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Исправление league_slug в season_data для сезонов КВН'
    )
    parser.add_argument('--apply', action='store_true', help='Применить изменения в БД')
    parser.add_argument('--years', nargs='+', type=int, default=YEARS_TO_FIX,
                       help=f'Годы для исправления (по умолчанию: {YEARS_TO_FIX})')
    args = parser.parse_args()
    
    # Подключаемся к MongoDB
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        print(f"[INFO] Ищем сезоны для исправления: {args.years}")
        
        # Ищем сезоны по годам в season_data
        fixed_count = 0
        not_found_count = 0
        
        for year in args.years:
            print(f"\n{'='*80}")
            print(f"Обработка сезона {year} года")
            print(f"{'='*80}")
            
            # Ищем сезоны с указанным годом
            seasons = list(db.kvn.find({
                "season_data.year": year
            }))
            
            if not seasons:
                print(f"[WARNING] Сезон {year} года не найден")
                not_found_count += 1
                continue
            
            for season in seasons:
                title = season.get("title", "N/A")
                print(f"\n[INFO] Найден сезон: {title}")
                
                if fix_season_league_slug(db, season, apply=args.apply):
                    fixed_count += 1
        
        print(f"\n{'='*80}")
        print(f"ИТОГИ")
        print(f"{'='*80}")
        print(f"Исправлено сезонов: {fixed_count}")
        print(f"Не найдено сезонов: {not_found_count}")
        
        if not args.apply:
            print(f"\n[INFO] Dry-run режим. Для применения используйте --apply")
    
    finally:
        client.close()


if __name__ == '__main__':
    main()
