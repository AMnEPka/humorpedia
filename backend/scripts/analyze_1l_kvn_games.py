#!/usr/bin/env python3
"""
Анализ игр первой лиги КВН на наличие данных.

Проверяет для каждой игры наличие:
- самой игры
- баллов у команд
- баллов за каждый конкурс
- даты игры
- списка членов жюри
- ведущего

Сохраняет результаты в CSV файл в корне проекта.
"""

import asyncio
import csv
import os
import sys
from pathlib import Path

# Add backend root to import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_db, close_db  # noqa: E402


def check_game_data(game: dict) -> dict:
    """
    Проверяет наличие данных в игре.
    
    Returns:
        dict с результатами проверки:
        - has_game: есть ли объект игры
        - has_team_scores: есть ли баллы у команд (total или scores)
        - has_contest_scores: есть ли баллы за каждый конкурс
        - has_date: есть ли дата игры
        - has_jury: есть ли список жюри
        - has_host: есть ли ведущий
    """
    result = {
        'has_game': False,
        'has_team_scores': False,
        'has_contest_scores': False,
        'has_date': False,
        'has_jury': False,
        'has_host': False,
    }
    
    if not game:
        return result
    
    result['has_game'] = True
    
    # Проверка даты
    date = game.get('date', '')
    if date and date.strip():
        result['has_date'] = True
    
    # Проверка жюри
    jury = game.get('jury', [])
    if jury and isinstance(jury, list) and len(jury) > 0:
        # Проверяем, что есть хотя бы один непустой элемент
        if any(j and str(j).strip() for j in jury):
            result['has_jury'] = True
    
    # Проверка ведущего
    host = game.get('host', '')
    if host and str(host).strip():
        result['has_host'] = True
    
    # Проверка команд и баллов
    teams = game.get('teams', [])
    contests = game.get('contests', [])
    
    if teams and isinstance(teams, list) and len(teams) > 0:
        # Проверяем наличие баллов у команд
        has_any_score = False
        teams_with_contest_scores = 0
        total_valid_teams = 0
        
        for team in teams:
            if not isinstance(team, dict):
                continue
            
            total_valid_teams += 1
            
            # Проверяем наличие total (даже если 0 - это тоже данные)
            total = team.get('total')
            if total is not None and isinstance(total, (int, float)):
                has_any_score = True
            
            # Проверяем наличие scores
            scores = team.get('scores', {})
            if scores and isinstance(scores, dict) and len(scores) > 0:
                has_any_score = True
                
                # Проверяем наличие баллов за конкурсы у этой команды
                if contests and len(contests) > 0:
                    has_scores_for_all_contests = True
                    for contest in contests:
                        if contest not in scores or scores[contest] is None:
                            has_scores_for_all_contests = False
                            break
                        score_value = scores[contest]
                        if not isinstance(score_value, (int, float)):
                            has_scores_for_all_contests = False
                            break
                    
                    if has_scores_for_all_contests:
                        teams_with_contest_scores += 1
        
        if has_any_score:
            result['has_team_scores'] = True
        
        # Считаем, что есть баллы за конкурсы, если хотя бы у одной команды есть баллы за все конкурсы
        # или если у большинства команд (>= 50%) есть баллы за все конкурсы
        if contests and len(contests) > 0:
            if teams_with_contest_scores > 0:
                # Если хотя бы у одной команды есть баллы за все конкурсы - это уже хорошо
                result['has_contest_scores'] = True
            elif total_valid_teams > 0:
                # Или если у большинства команд есть баллы за конкурсы
                if teams_with_contest_scores >= (total_valid_teams / 2):
                    result['has_contest_scores'] = True
    
    return result


async def analyze_1l_kvn():
    """Анализирует все игры первой лиги КВН."""
    db = await get_db()
    
    # Находим все сезоны первой лиги
    query = {
        "season_data.league_slug": "1l-kvn"
    }
    
    seasons = await db.kvn.find(query).sort("season_data.year", 1).to_list(1000)
    
    print(f"Найдено сезонов первой лиги: {len(seasons)}")
    
    results = []
    
    for season in seasons:
        season_data = season.get('season_data', {})
        year = season_data.get('year', 0)
        season_slug = season.get('slug', '')
        season_full_path = season.get('full_path', '')
        
        stages = season_data.get('stages', [])
        
        if not stages:
            # Если нет стадий, добавляем запись о сезоне без игр
            results.append({
                'season_year': year,
                'season_slug': season_slug,
                'season_full_path': season_full_path,
                'stage_name': '',
                'game_name': '',
                'has_game': '-',
                'has_team_scores': '-',
                'has_contest_scores': '-',
                'has_date': '-',
                'has_jury': '-',
                'has_host': '-',
            })
            continue
        
        for stage in stages:
            stage_name = stage.get('name', '')
            games = stage.get('games', [])
            
            if not games:
                # Если нет игр в стадии, добавляем запись о стадии без игр
                results.append({
                    'season_year': year,
                    'season_slug': season_slug,
                    'season_full_path': season_full_path,
                    'stage_name': stage_name,
                    'game_name': '',
                    'has_game': '-',
                    'has_team_scores': '-',
                    'has_contest_scores': '-',
                    'has_date': '-',
                    'has_jury': '-',
                    'has_host': '-',
                })
                continue
            
            for game in games:
                game_name = game.get('name', '')
                check_result = check_game_data(game)
                
                # Преобразуем булевы значения в +/-
                def bool_to_sign(value):
                    if value is None:
                        return '-'
                    return '+' if value else '-'
                
                results.append({
                    'season_year': year,
                    'season_slug': season_slug,
                    'season_full_path': season_full_path,
                    'stage_name': stage_name,
                    'game_name': game_name,
                    'has_game': bool_to_sign(check_result['has_game']),
                    'has_team_scores': bool_to_sign(check_result['has_team_scores']),
                    'has_contest_scores': bool_to_sign(check_result['has_contest_scores']),
                    'has_date': bool_to_sign(check_result['has_date']),
                    'has_jury': bool_to_sign(check_result['has_jury']),
                    'has_host': bool_to_sign(check_result['has_host']),
                })
    
    # Сохраняем результаты в CSV
    # В контейнере backend монтируется как /app, а корень проекта - это /app/..
    # Но проще сохранить в /app и скопировать оттуда, или использовать относительный путь
    # Попробуем сохранить в /app (backend директория), а потом скопируем в корень
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent
    # Пытаемся найти корень проекта (где есть docker-compose.yml)
    project_root = backend_dir.parent
    csv_path = project_root / '1l_kvn_games_analysis.csv'
    
    # Если не можем записать в корень проекта (например, в контейнере),
    # сохраняем в /app (backend директория)
    try:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        # Fallback: сохраняем в /app
        csv_path = Path('/app') / '1l_kvn_games_analysis.csv'
    
    fieldnames = [
        'season_year',
        'season_slug',
        'season_full_path',
        'stage_name',
        'game_name',
        'has_game',
        'has_team_scores',
        'has_contest_scores',
        'has_date',
        'has_jury',
        'has_host',
    ]
    
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"✅ Анализ завершен. Результаты сохранены в: {csv_path}")
    print(f"Всего записей: {len(results)}")
    
    # Статистика
    total_games = len([r for r in results if r['has_game'] == '+'])
    games_with_scores = len([r for r in results if r['has_team_scores'] == '+'])
    games_with_contest_scores = len([r for r in results if r['has_contest_scores'] == '+'])
    games_with_date = len([r for r in results if r['has_date'] == '+'])
    games_with_jury = len([r for r in results if r['has_jury'] == '+'])
    games_with_host = len([r for r in results if r['has_host'] == '+'])
    
    print(f"\nСтатистика:")
    print(f"  Игр найдено: {total_games}")
    print(f"  С баллами команд: {games_with_scores}")
    print(f"  С баллами за конкурсы: {games_with_contest_scores}")
    print(f"  С датой: {games_with_date}")
    print(f"  С жюри: {games_with_jury}")
    print(f"  С ведущим: {games_with_host}")


async def main():
    try:
        await analyze_1l_kvn()
    finally:
        await close_db()


if __name__ == '__main__':
    asyncio.run(main())
