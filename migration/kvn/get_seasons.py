#!/usr/bin/env python3
"""
Скрипт для получения всех обработанных сезонов КВН.

Использование:
    # Показать все обработанные сезоны
    python get_seasons.py
    
    # Показать сезоны конкретной лиги
    python get_seasons.py --league premier-liga
    
    # Экспортировать в JSON
    python get_seasons.py --export seasons.json
    
    # Показать детали одного сезона
    python get_seasons.py --path kvn/premier-liga/2023
"""

import os
import sys
import json
import argparse
import pymongo


def get_processed_seasons(db, league: str = None):
    """
    Получает все сезоны с обработанными данными.
    
    Args:
        db: База данных MongoDB
        league: Slug лиги (опционально)
    
    Returns:
        Список документов сезонов с полем season_data
    """
    query = {'season_data': {'$exists': True}}
    
    if league:
        # Фильтруем по лиге
        query['full_path'] = {'$regex': f'^kvn/{league}/'}
    
    seasons = list(db.kvn.find(query).sort('full_path', 1))
    return seasons


def print_season_summary(season):
    """Выводит краткую информацию о сезоне."""
    season_data = season.get('season_data', {})
    
    print(f"\n{'='*60}")
    print(f"📋 {season.get('title', season.get('name', 'Без названия'))}")
    print(f"   Path: {season.get('full_path', 'N/A')}")
    print(f"   Лига: {season_data.get('league_slug', 'N/A')}")
    print(f"   Год: {season_data.get('year', 'N/A')}")
    
    stages = season_data.get('stages', [])
    total_games = sum(len(s.get('games', [])) for s in stages)
    total_teams = len(season_data.get('all_teams', []))
    
    print(f"   Стадий: {len(stages)}, Игр: {total_games}, Команд: {total_teams}")
    
    winners = season_data.get('winners', [])
    if winners:
        print(f"   🏆 Победители: {', '.join(winners)}")
    
    # Показываем стадии
    if stages:
        print(f"\n   Стадии:")
        for stage in stages:
            games_count = len(stage.get('games', []))
            print(f"     • {stage.get('name', 'N/A')}: {games_count} игр")


def print_season_details(season):
    """Выводит детальную информацию о сезоне."""
    season_data = season.get('season_data', {})
    
    print(f"\n{'='*80}")
    print(f"📋 {season.get('title', season.get('name', 'Без названия'))}")
    print(f"{'='*80}")
    print(f"Path: {season.get('full_path', 'N/A')}")
    print(f"Лига: {season_data.get('league_slug', 'N/A')}")
    print(f"Год: {season_data.get('year', 'N/A')}")
    
    # Метаданные
    if season_data.get('editors'):
        print(f"Редакторы: {', '.join(season_data['editors'])}")
    if season_data.get('host'):
        print(f"Ведущий: {season_data['host']}")
    if season_data.get('jury'):
        print(f"Жюри ({len(season_data['jury'])}): {', '.join(season_data['jury'][:5])}...")
    
    # Команды
    teams = season_data.get('all_teams', [])
    if teams:
        print(f"\nКоманды-участники ({len(teams)}):")
        for i, team in enumerate(teams[:10], 1):
            print(f"  {i}. {team}")
        if len(teams) > 10:
            print(f"  ... и ещё {len(teams) - 10}")
    
    # Стадии
    stages = season_data.get('stages', [])
    if stages:
        print(f"\n{'='*80}")
        print("СТАДИИ СЕЗОНА")
        print(f"{'='*80}")
        
        for stage in stages:
            print(f"\n📌 {stage.get('name', 'N/A')}")
            
            if stage.get('notes'):
                print(f"   Примечание: {stage['notes']}")
            
            games = stage.get('games', [])
            if games:
                for game in games:
                    print(f"\n   🎮 {game.get('name', 'N/A')}")
                    if game.get('date'):
                        print(f"      Дата: {game['date']}")
                    if game.get('host'):
                        print(f"      Ведущий: {game['host']}")
                    if game.get('jury'):
                        print(f"      Жюри: {', '.join(game['jury'][:3])}...")
                    
                    teams = game.get('teams', [])
                    if teams:
                        print(f"      Команды ({len(teams)}):")
                        for team in teams[:5]:
                            passed = "✅" if team.get('passed') else "❌"
                            winner = "🏆" if team.get('is_winner') else ""
                            print(f"        {passed} {winner} {team.get('place', '?')}. {team.get('team_name', 'N/A')}: {team.get('total', 0)}")
                        if len(teams) > 5:
                            print(f"        ... и ещё {len(teams) - 5}")
            
            if stage.get('additional_teams'):
                print(f"\n   🔄 Добор: {', '.join(stage['additional_teams'])}")
                if stage.get('additional_notes'):
                    print(f"      {stage['additional_notes']}")


def main():
    parser = argparse.ArgumentParser(
        description='Получение обработанных сезонов КВН',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Все обработанные сезоны
  python get_seasons.py
  
  # Сезоны конкретной лиги
  python get_seasons.py --league premier-liga
  
  # Детали одного сезона
  python get_seasons.py --path kvn/premier-liga/2023 --details
  
  # Экспорт в JSON
  python get_seasons.py --export seasons.json
        """
    )
    parser.add_argument('--league', type=str, help='Фильтр по лиге')
    parser.add_argument('--path', type=str, help='Путь к конкретному сезону')
    parser.add_argument('--details', action='store_true', help='Показать детали')
    parser.add_argument('--export', type=str, help='Экспортировать в JSON файл')
    parser.add_argument('--count-only', action='store_true', help='Только количество')
    
    args = parser.parse_args()
    
    # Подключаемся к MongoDB
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'humorpedia')
    
    client = pymongo.MongoClient(mongo_url)
    db = client[db_name]
    
    try:
        if args.path:
            # Один сезон
            season = db.kvn.find_one({'full_path': args.path})
            if not season:
                print(f"❌ Сезон {args.path} не найден")
                return
            
            if 'season_data' not in season:
                print(f"⚠️  Сезон {args.path} ещё не обработан")
                print(f"   Запустите: python process_seasons.py --path {args.path} --apply")
                return
            
            if args.details:
                print_season_details(season)
            else:
                print_season_summary(season)
            
            if args.export:
                with open(args.export, 'w', encoding='utf-8') as f:
                    json.dump(season.get('season_data', {}), f, ensure_ascii=False, indent=2)
                print(f"\n💾 Экспортировано в {args.export}")
        
        else:
            # Все сезоны
            seasons = get_processed_seasons(db, args.league)
            
            if args.count_only:
                print(f"✅ Обработано сезонов: {len(seasons)}")
                return
            
            if not seasons:
                print("⚠️  Нет обработанных сезонов")
                print("   Запустите: python process_seasons.py --all --apply")
                return
            
            print(f"\n{'='*60}")
            print(f"📊 ОБРАБОТАННЫЕ СЕЗОНЫ КВН")
            print(f"{'='*60}")
            print(f"Всего: {len(seasons)}")
            
            if args.league:
                print(f"Лига: {args.league}")
            
            # Группируем по лигам
            by_league = {}
            for season in seasons:
                league = season.get('season_data', {}).get('league_slug', 'unknown')
                if league not in by_league:
                    by_league[league] = []
                by_league[league].append(season)
            
            for league, league_seasons in sorted(by_league.items()):
                print(f"\n🏆 {league.upper()} ({len(league_seasons)} сезонов)")
                for season in league_seasons:
                    season_data = season.get('season_data', {})
                    year = season_data.get('year', '?')
                    stages = len(season_data.get('stages', []))
                    games = sum(len(s.get('games', [])) for s in season_data.get('stages', []))
                    print(f"   • {year}: {stages} стадий, {games} игр")
            
            # Детали если нужно
            if args.details:
                for season in seasons:
                    print_season_details(season)
            else:
                for season in seasons:
                    print_season_summary(season)
            
            # Экспорт
            if args.export:
                export_data = {
                    'total': len(seasons),
                    'seasons': [
                        {
                            'path': s.get('full_path'),
                            'title': s.get('title', s.get('name')),
                            'season_data': s.get('season_data', {})
                        }
                        for s in seasons
                    ]
                }
                with open(args.export, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                print(f"\n💾 Экспортировано {len(seasons)} сезонов в {args.export}")
    
    finally:
        client.close()


if __name__ == '__main__':
    main()

