#!/usr/bin/env python3
"""
Скрипт для обработки сезонов КВН.

Использование:
    # Обработка одного сезона (dry-run)
    python process_seasons.py --path kvn/premier-liga/2023
    
    # Обработка одного сезона с записью в БД
    python process_seasons.py --path kvn/premier-liga/2023 --apply
    
    # Обработка всех сезонов лиги
    python process_seasons.py --league premier-liga --apply
    
    # Обработка всех сезонов всех лиг
    python process_seasons.py --all --apply

Результат:
    Добавляет поле 'season_data' в документ сезона с структурированной информацией:
    - stages: список стадий с играми
    - teams: команды-участники
    - winners: победители сезона
    - jury: жюри
    - и т.д.
"""

import os
import sys
import re
import json
import argparse
from datetime import datetime

# Добавляем путь к парсерам
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo
from parsers.kvn_season import KVNSeasonParser


# Лиги для обработки (slug -> название)
LEAGUES = {
    'vl-kvn': 'Высшая лига КВН',
    'premier-liga': 'Премьер-лига КВН',
    '1l-kvn': 'Первая лига КВН',
    'ml-kvn': 'Международная лига КВН',
    'vul': 'Высшая украинская лига КВН',
}


def extract_year(slug: str) -> int:
    """Извлекает год из slug сезона."""
    # Ищем 4-значное число
    match = re.search(r'(\d{4})', slug)
    if match:
        return int(match.group(1))
    
    # Ищем 2-значное число (для старых сезонов)
    match = re.search(r'-(\d{2})(?:$|[^0-9])', slug)
    if match:
        year = int(match.group(1))
        return 1900 + year if year > 50 else 2000 + year
    
    return 0


def get_season_html(season_doc: dict) -> str:
    """Собирает весь HTML контент из текстовых модулей."""
    modules = season_doc.get('modules', [])
    text_modules = [m for m in modules if m.get('type') == 'text_block']
    
    html_parts = []
    for m in text_modules:
        content = m.get('data', {}).get('content', '')
        if content:
            html_parts.append(content)
    
    return '\n'.join(html_parts)


def process_season(db, path: str, apply: bool = False, verbose: bool = False) -> dict:
    """
    Обрабатывает один сезон.
    
    Args:
        db: База данных MongoDB
        path: Полный путь к сезону (например, kvn/premier-liga/2023)
        apply: Записать результат в БД
        verbose: Подробный вывод
        
    Returns:
        Результат парсинга
    """
    season_doc = db.kvn.find_one({'full_path': path})
    if not season_doc:
        print(f"  ❌ Сезон {path} не найден")
        return None
    
    # Получаем HTML
    html = get_season_html(season_doc)
    if not html:
        print(f"  ⚠️  Нет текстового контента")
        return None
    
    # Определяем лигу и год
    path_parts = path.split('/')
    league = path_parts[1] if len(path_parts) > 1 else ''
    year = extract_year(path_parts[-1])
    
    # Парсим
    parser = KVNSeasonParser()
    result = parser.parse(html, league=league, year=year)
    result_dict = parser.to_dict(result)
    
    # Статистика
    total_games = sum(len(s['games']) for s in result_dict['stages'])
    total_teams = len(set(
        t['team_slug'] or t['team_name']
        for s in result_dict['stages']
        for g in s['games']
        for t in g['teams']
    ))
    
    print(f"  📊 Стадий: {len(result_dict['stages'])}, Игр: {total_games}, Команд: {total_teams}")
    
    if result_dict['winners']:
        print(f"  🏆 Победители: {result_dict['winners']}")
    
    if verbose:
        for stage in result_dict['stages']:
            print(f"    📌 {stage['name']} ({len(stage['games'])} игр)")
            for game in stage['games']:
                print(f"      🎮 {game['name']} - {game['date'] or 'дата не указана'}")
    
    # Записываем в БД
    if apply:
        db.kvn.update_one(
            {'_id': season_doc['_id']},
            {'$set': {'season_data': result_dict}}
        )
        print(f"  ✅ Записано в БД")
    else:
        print(f"  🔍 Dry-run: используйте --apply для записи")
    
    return result_dict


def get_league_seasons(db, league_slug: str) -> list:
    """Получает все сезоны лиги."""
    # Находим страницу лиги
    league = db.kvn.find_one({'slug': league_slug})
    if not league:
        league = db.kvn.find_one({'full_path': f'kvn/{league_slug}'})
    
    if not league:
        return []
    
    league_id = league.get('id')
    
    # Находим все сезоны (дочерние страницы)
    seasons = list(db.kvn.find({
        'parent_id': league_id,
        'full_path': {'$regex': r'\d{4}'}  # Содержит год
    }))
    
    # Также ищем по пути
    seasons_by_path = list(db.kvn.find({
        'full_path': {'$regex': f'^kvn/{league_slug}/.*\\d{{4}}'}
    }))
    
    # Объединяем и убираем дубликаты
    all_slugs = set()
    result = []
    for s in seasons + seasons_by_path:
        if s['slug'] not in all_slugs:
            all_slugs.add(s['slug'])
            result.append(s)
    
    return sorted(result, key=lambda x: extract_year(x.get('slug', '')))


def main():
    parser = argparse.ArgumentParser(
        description='Обработка сезонов КВН',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Один сезон
  python process_seasons.py --path kvn/premier-liga/2023
  
  # Все сезоны лиги
  python process_seasons.py --league premier-liga --apply
  
  # Все лиги
  python process_seasons.py --all --apply
        """
    )
    parser.add_argument('--path', type=str, help='Полный путь к сезону')
    parser.add_argument('--league', type=str, choices=list(LEAGUES.keys()),
                        help='Обработать все сезоны лиги')
    parser.add_argument('--all', action='store_true', help='Обработать все лиги')
    parser.add_argument('--apply', action='store_true', help='Записать в БД')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробный вывод')
    parser.add_argument('--output', '-o', type=str, help='Сохранить результат в JSON файл')
    
    args = parser.parse_args()
    
    if not args.path and not args.league and not args.all:
        parser.error("Укажите --path, --league или --all")
    
    # Подключаемся к MongoDB
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'humorpedia')
    
    client = pymongo.MongoClient(mongo_url)
    db = client[db_name]
    
    results = {}
    
    try:
        if args.path:
            # Один сезон
            print(f"\n📋 Обработка сезона: {args.path}")
            result = process_season(db, args.path, args.apply, args.verbose)
            if result:
                results[args.path] = result
        
        elif args.league:
            # Одна лига
            print(f"\n📋 Обработка лиги: {LEAGUES.get(args.league, args.league)}")
            seasons = get_league_seasons(db, args.league)
            print(f"   Найдено сезонов: {len(seasons)}")
            
            for season in seasons:
                path = season.get('full_path', '')
                print(f"\n🔹 {season.get('title', path)}")
                result = process_season(db, path, args.apply, args.verbose)
                if result:
                    results[path] = result
        
        elif args.all:
            # Все лиги
            print(f"\n📋 Обработка всех лиг")
            
            for league_slug, league_name in LEAGUES.items():
                print(f"\n{'='*60}")
                print(f"🏆 {league_name}")
                print(f"{'='*60}")
                
                seasons = get_league_seasons(db, league_slug)
                print(f"   Найдено сезонов: {len(seasons)}")
                
                for season in seasons:
                    path = season.get('full_path', '')
                    print(f"\n🔹 {season.get('title', path)}")
                    result = process_season(db, path, args.apply, args.verbose)
                    if result:
                        results[path] = result
        
        # Сохраняем результаты
        if args.output and results:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Результаты сохранены в {args.output}")
        
        # Итоги
        print(f"\n{'='*60}")
        print(f"✅ Обработано сезонов: {len(results)}")
        
        total_stages = sum(len(r['stages']) for r in results.values())
        total_games = sum(
            len(g) 
            for r in results.values() 
            for s in r['stages'] 
            for g in [s['games']]
        )
        
        print(f"   Стадий: {total_stages}")
        print(f"   Игр: {total_games}")
        
    finally:
        client.close()


if __name__ == '__main__':
    main()

