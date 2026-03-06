#!/usr/bin/env python3
"""
Скрипт для исправления сезонов КВН, которые имеют неправильный league_slug "ml-kvn" 
для годов до 2014. Международная лига КВН была создана в 2014 году, поэтому сезоны 
до этого года не должны иметь league_slug "ml-kvn".

Использование:
    # Проверка (dry-run)
    python fix_ml_kvn_before_2014.py
    
    # Применить исправления
    python fix_ml_kvn_before_2014.py --apply
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo

# MongoDB настройки
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'humorpedia')

# Международная лига была создана в 2014 году
ML_KVN_START_YEAR = 2014


def extract_year_from_season(season_doc: dict) -> int:
    """Извлекает год из сезона"""
    season_data = season_doc.get("season_data", {})
    year = season_data.get("year")
    if year:
        return int(year)
    
    # Пытаемся извлечь из slug
    slug = season_doc.get("slug", "")
    m = re.search(r"(19|20)\d{2}", slug)
    if m:
        return int(m.group(0))
    
    # Пытаемся извлечь из full_path
    full_path = season_doc.get("full_path", "")
    if full_path:
        m = re.search(r"(19|20)\d{2}", full_path)
        if m:
            return int(m.group(0))
    
    return 0


def determine_correct_league_slug(season_doc: dict, year: int) -> str:
    """Определяет правильный league_slug на основе full_path или других данных"""
    full_path = season_doc.get("full_path", "")
    if full_path:
        # Убираем начальный слэш, если есть
        clean_path = full_path.lstrip("/")
        path_parts = clean_path.split("/")
        if len(path_parts) >= 2 and path_parts[0] == "kvn":
            potential_league = path_parts[1]
            # Проверяем, что это валидный league_slug
            valid_leagues = ["vl-kvn", "premier-liga", "1l-kvn", "ml-kvn", "vul"]
            if potential_league in valid_leagues:
                # Если в пути указано ml-kvn, но год < 2014, это ошибка
                # Нужно определить правильную лигу из других данных
                if potential_league == "ml-kvn" and year < ML_KVN_START_YEAR:
                    # Проверяем slug сезона - может быть pl-2006, vl-2006 и т.д.
                    slug = season_doc.get("slug", "").lower()
                    if "pl-" in slug or "premier" in slug:
                        return "premier-liga"
                    elif "vl-" in slug or "vysshaya" in slug:
                        return "vl-kvn"
                    elif "1l-" in slug or "pervaya" in slug:
                        return "1l-kvn"
                    else:
                        # По умолчанию для старых сезонов - Премьер-лига (чаще всего)
                        return "premier-liga"
                # Если лига корректна для года, возвращаем её
                return potential_league
    
    # Если не удалось определить, возвращаем None
    return None


def fix_season_league_slug(db, season_doc, apply: bool = False) -> bool:
    """Исправляет league_slug в season_data для сезона"""
    
    season_id = season_doc.get("_id")
    title = season_doc.get("title", "N/A")
    full_path = season_doc.get("full_path", "")
    
    season_data = season_doc.get("season_data", {})
    if not season_data:
        print(f"[SKIP] Сезон {title} ({season_id}) не имеет season_data")
        return False
    
    current_league_slug = season_data.get("league_slug")
    if current_league_slug != "ml-kvn":
        # Нас интересуют только сезоны с ml-kvn
        return False
    
    year = extract_year_from_season(season_doc)
    if year == 0:
        print(f"[WARNING] Не удалось определить год для сезона {title}")
        return False
    
    if year >= ML_KVN_START_YEAR:
        # Сезон после 2014 года - всё правильно
        return False
    
    # Нашли проблемный сезон: год < 2014, но league_slug = "ml-kvn"
    print(f"[FOUND] Сезон {title} ({year} год) имеет неправильный league_slug: ml-kvn")
    print(f"       full_path: {full_path}")
    
    # Определяем правильный league_slug
    correct_league_slug = determine_correct_league_slug(season_doc, year)
    if not correct_league_slug:
        print(f"[WARNING] Не удалось определить правильный league_slug для сезона {title}")
        print(f"         Предполагаем, что это Премьер-лига (premier-liga)")
        correct_league_slug = "premier-liga"
    
    print(f"[FIX] Будет изменено: ml-kvn -> {correct_league_slug}")
    
    if apply:
        # Обновляем season_data
        updated_season_data = season_data.copy()
        updated_season_data["league_slug"] = correct_league_slug
        
        # Также обновляем league_name если нужно
        league_names = {
            "vl-kvn": "Высшая лига КВН",
            "premier-liga": "Премьер-лига КВН",
            "1l-kvn": "Первая лига КВН",
            "ml-kvn": "Международная лига КВН",
            "vul": "Высшая украинская лига КВН"
        }
        if correct_league_slug in league_names:
            updated_season_data["league_name"] = league_names[correct_league_slug]
        
        result = db.kvn.update_one(
            {"_id": season_id},
            {"$set": {"season_data": updated_season_data}}
        )
        
        if result.modified_count > 0:
            print(f"[OK] Сезон {title} успешно обновлен")
            return True
        else:
            print(f"[WARNING] Сезон {title} не был обновлен")
            return False
    else:
        print(f"[DRY-RUN] Будет изменено: ml-kvn -> {correct_league_slug}")
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Исправление неправильного league_slug "ml-kvn" для сезонов до 2014 года'
    )
    parser.add_argument('--apply', action='store_true', help='Применить изменения в БД')
    args = parser.parse_args()
    
    # Подключаемся к MongoDB
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        print(f"[INFO] Ищем сезоны с неправильным league_slug 'ml-kvn' до {ML_KVN_START_YEAR} года")
        print(f"{'='*80}")
        
        # Ищем все сезоны с league_slug = "ml-kvn"
        seasons = list(db.kvn.find({
            "season_data.league_slug": "ml-kvn"
        }))
        
        print(f"[INFO] Найдено {len(seasons)} сезонов с league_slug='ml-kvn'")
        print()
        
        fixed_count = 0
        skipped_count = 0
        
        for season in seasons:
            year = extract_year_from_season(season)
            if year > 0 and year < ML_KVN_START_YEAR:
                if fix_season_league_slug(db, season, apply=args.apply):
                    fixed_count += 1
                print()
            else:
                skipped_count += 1
        
        print(f"{'='*80}")
        print(f"ИТОГИ")
        print(f"{'='*80}")
        print(f"Найдено проблемных сезонов: {fixed_count}")
        print(f"Пропущено сезонов (правильные или без года): {skipped_count}")
        
        if not args.apply:
            print()
            print("[INFO] Это был dry-run. Для применения изменений запустите с флагом --apply")
        else:
            print()
            print(f"[OK] Исправлено сезонов: {fixed_count}")
        
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
