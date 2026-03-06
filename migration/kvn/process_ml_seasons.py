#!/usr/bin/env python3
"""
Скрипт для обработки сезонов Международной лиги КВН.

Этот скрипт обновляет сезоны международной лиги, приводя их к такому же виду,
как сезоны высшей лиги. Он парсит HTML из модулей админки, создает структурированные
данные season_data, сопоставляет команды с существующими в БД, добавляет теги
и обновляет модули.

Использование:
    # Обработка одного сезона (dry-run)
    python process_ml_seasons.py --path kvn/ml-kvn/2023
    
    # Обработка одного сезона с записью в БД
    python process_ml_seasons.py --path kvn/ml-kvn/2023 --apply
    
    # Обработка всех сезонов международной лиги
    python process_ml_seasons.py --all --apply

Результат:
    Добавляет/обновляет поле 'season_data' в документ сезона с структурированной информацией:
    - stages: список стадий с играми
    - teams: команды-участники
    - winners: победители сезона
    - jury: жюри
    - и т.д.
    
    Также:
    - Сопоставляет команды с существующими в БД
    - Добавляет теги (КВН, Международная лига КВН, названия команд)
    - Обновляет модуль "Команды-участники" со ссылками
    - Скрывает старые модули с результатами
"""

import os
import sys
import re
import json
import argparse
from datetime import datetime, timezone
from uuid import uuid4

# Добавляем путь к парсерам
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo
from parsers.kvn_season import KVNSeasonParser
from team_matcher import match_all_teams, normalize_team_name


# Лига для обработки
LEAGUE_SLUG = 'ml-kvn'
LEAGUE_NAME = 'Международная лига КВН'


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


def transliterate_slug(text: str) -> str:
    """Транслитерирует текст в slug."""
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    slug = text.lower().replace(" ", "-")
    slug = ''.join(translit_map.get(c, c) for c in slug)
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    return slug.strip('-')


def sync_tags_to_collection(tags: list, db) -> None:
    """Синхронизация тегов с коллекцией tags."""
    if not tags:
        return
    
    for tag_name in tags:
        tag_name = tag_name.strip()
        if not tag_name:
            continue
        
        existing = db.tags.find_one({
            "name": {"$regex": f"^{re.escape(tag_name)}$", "$options": "i"}
        })
        
        if not existing:
            tag_doc = {
                "_id": str(uuid4()),
                "name": tag_name,
                "slug": transliterate_slug(tag_name),
                "old_id": None,
                "usage_count": 1,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            try:
                db.tags.insert_one(tag_doc)
            except Exception:
                pass
        else:
            db.tags.update_one(
                {"_id": existing["_id"]},
                {"$inc": {"usage_count": 1}}
            )


def process_season(db, path: str, apply: bool = False, verbose: bool = False) -> dict:
    """
    Обрабатывает один сезон международной лиги.
    
    Args:
        db: База данных MongoDB
        path: Полный путь к сезону (например, kvn/ml-kvn/2023)
        apply: Записать результат в БД
        verbose: Подробный вывод
        
    Returns:
        Результат парсинга
    """
    season_doc = db.kvn.find_one({'full_path': path})
    if not season_doc:
        print(f"  ❌ Сезон {path} не найден")
        return None
    
    # Получаем модули и HTML
    modules = season_doc.get('modules', [])
    html = get_season_html(season_doc)
    if not html:
        print(f"  ⚠️  Нет текстового контента")
        return None
    
    # Определяем год
    path_parts = path.split('/')
    year = extract_year(path_parts[-1])
    
    # Парсим с передачей модулей для расширенного парсинга
    parser = KVNSeasonParser()
    result = parser.parse(html, league=LEAGUE_SLUG, year=year, modules=modules)
    result_dict = parser.to_dict(result)
    
    # Убеждаемся, что league_slug установлен правильно
    result_dict['league_slug'] = LEAGUE_SLUG
    result_dict['league_name'] = LEAGUE_NAME
    
    # Получаем все существующие команды из БД
    # ВАЖНО: Загружаем также facts для получения города
    # ИГНОРИРУЕМ фильтр team_type, так как некоторые команды могут иметь team_type=None
    existing_teams = list(db.teams.find({
        'content_type': 'team'
    }, {
        '_id': 1,
        'slug': 1,
        'name': 1,
        'title': 1,  # Загружаем title как fallback для name
        'aliases': 1,
        'tags': 1,
        'facts': 1  # Для получения города
    }))
    
    # Сопоставляем команды сезона с существующими
    season_teams = result_dict.get('all_teams', [])
    
    # Строим карту slug -> название из парсера
    team_slug_map = {}
    if hasattr(parser, 'stage_parser') and parser.stage_parser:
        if hasattr(parser.stage_parser, 'game_parser') and parser.stage_parser.game_parser:
            team_slug_map = getattr(parser.stage_parser.game_parser, 'team_slug_map', {})
    
    team_matches = match_all_teams(season_teams, existing_teams, team_slug_map)

    # Для отладки: показываем какие команды не сопоставились и почему это важно
    # (обычно проблема в различиях названий/городах/алиасах или отсутствующих slug'ах).
    if verbose:
        def _team_match_key(team_dict: dict) -> str:
            slug = (team_dict.get('slug') or '').strip()
            if slug:
                return slug
            name_key = normalize_team_name(team_dict.get('name', ''))
            return f"__name__:{name_key}" if name_key else ""

        unmatched = []
        for t in season_teams:
            key = _team_match_key(t)
            if not key or key not in team_matches:
                unmatched.append(t)
        if unmatched:
            print(f"  ⚠️  Не сопоставлены команды ({len(unmatched)}):")
            for t in unmatched:
                print(f"    - {t.get('name', '').strip()} [{t.get('slug', '').strip()}]")
    
    # Обновляем команды в играх с учетом алиасов
    # Строим карту названий/алиасов -> (team_id, team_slug, team_name)
    # ВАЖНО: Алиасы должны иметь приоритет, чтобы "Пермский край" находил "Сборная Пермского края"
    team_name_map = {}
    for team in existing_teams:
        team_id = team['_id']
        team_slug = team.get('slug', '')
        # Используем name, если есть, иначе title как fallback
        team_name = team.get('name', '').strip() or team.get('title', '').strip()
        aliases = team.get('aliases', [])
        
        # Сначала добавляем алиасы (они имеют приоритет для сопоставления)
        for alias in aliases:
            if alias and alias.strip():  # Пропускаем пустые алиасы
                normalized = normalize_team_name(alias)
                if normalized:  # Убеждаемся, что нормализованное название не пустое
                    team_name_map[normalized] = (team_id, team_slug, team_name)
        
        # Затем добавляем основное название (если еще не добавлено)
        if team_name:
            normalized = normalize_team_name(team_name)
            if normalized not in team_name_map:  # Не перезаписываем алиасы
                team_name_map[normalized] = (team_id, team_slug, team_name)
    
    # Обновляем команды во всех играх (включая победителей)
    # ВАЖНО: Сохраняем флаги is_winner и passed при обновлении
    for stage_data in result_dict.get('stages', []):
        for game_data in stage_data.get('games', []):
            for team_data in game_data.get('teams', []):
                # Сохраняем флаги перед обновлением
                is_winner = team_data.get('is_winner', False)
                passed = team_data.get('passed', False)
                is_additional = team_data.get('is_additional', False)
                
                team_name = team_data.get('team_name', '')
                team_slug = team_data.get('team_slug', '')
                
                # Пробуем найти по названию (сначала проверяем алиасы)
                if team_name:
                    normalized = normalize_team_name(team_name)
                    if normalized in team_name_map:
                        team_id, matched_slug, matched_name = team_name_map[normalized]
                        # Обновляем slug и name команды, сохраняя флаги
                        team_data['team_slug'] = matched_slug
                        team_data['team_name'] = matched_name
                        team_data['team_id'] = team_id
                        # ВАЖНО: Сохраняем флаги ПОСЛЕ обновления названия
                        team_data['is_winner'] = is_winner
                        team_data['passed'] = passed
                        team_data['is_additional'] = is_additional
                    elif team_slug in team_matches:
                        # Пробуем найти по slug через team_matches
                        team_id, matched_slug = team_matches[team_slug]
                        matched_team = next((t for t in existing_teams if t['_id'] == team_id), None)
                        if matched_team:
                            team_data['team_slug'] = matched_team.get('slug', '')
                            # Используем name, если есть, иначе title как fallback
                            matched_team_name = matched_team.get('name', '').strip() or matched_team.get('title', '').strip()
                            team_data['team_name'] = matched_team_name or team_name
                            team_data['team_id'] = team_id
                            team_data['is_winner'] = is_winner
                            team_data['passed'] = passed
                            team_data['is_additional'] = is_additional
                    elif team_name:
                        # Фоллбек: если slug пустой/не совпал, пробуем по имени через team_matches (__name__:...)
                        name_key = normalize_team_name(team_name)
                        key = f"__name__:{name_key}" if name_key else ""
                        if key and key in team_matches:
                            team_id, matched_slug = team_matches[key]
                            matched_team = next((t for t in existing_teams if t['_id'] == team_id), None)
                            if matched_team:
                                team_data['team_slug'] = matched_team.get('slug', '')
                                matched_team_name = matched_team.get('name', '').strip() or matched_team.get('title', '').strip()
                                team_data['team_name'] = matched_team_name or team_name
                                team_data['team_id'] = team_id
                                team_data['is_winner'] = is_winner
                                team_data['passed'] = passed
                                team_data['is_additional'] = is_additional
                    else:
                        # Команда не найдена - но сохраняем флаги
                        team_data['is_winner'] = is_winner
                        team_data['passed'] = passed
                        team_data['is_additional'] = is_additional
                elif team_slug in team_matches:
                    # Если есть только slug - обновляем через team_matches
                    team_id, matched_slug = team_matches[team_slug]
                    matched_team = next((t for t in existing_teams if t['_id'] == team_id), None)
                    if matched_team:
                        team_data['team_slug'] = matched_team.get('slug', '')
                        # Используем name, если есть, иначе title как fallback
                        matched_team_name = matched_team.get('name', '').strip() or matched_team.get('title', '').strip()
                        team_data['team_name'] = matched_team_name
                        team_data['team_id'] = team_id
                        team_data['is_winner'] = is_winner
                        team_data['passed'] = passed
                        team_data['is_additional'] = is_additional
                elif team_name:
                    # Если есть только имя — пробуем через team_matches по __name__:...
                    name_key = normalize_team_name(team_name)
                    key = f"__name__:{name_key}" if name_key else ""
                    if key and key in team_matches:
                        team_id, matched_slug = team_matches[key]
                        matched_team = next((t for t in existing_teams if t['_id'] == team_id), None)
                        if matched_team:
                            team_data['team_slug'] = matched_team.get('slug', '')
                            matched_team_name = matched_team.get('name', '').strip() or matched_team.get('title', '').strip()
                            team_data['team_name'] = matched_team_name or team_name
                            team_data['team_id'] = team_id
                            team_data['is_winner'] = is_winner
                            team_data['passed'] = passed
                            team_data['is_additional'] = is_additional
    
    # Функция для получения полного названия команды с городом
    def get_full_team_name(team_id: str = None, team_slug: str = None, team_name: str = None) -> str:
        """Получает полное название команды с городом из БД."""
        team = None
        
        # Извлекаем город и чистое название из исходного названия (если есть)
        original_city = None
        original_name_clean = team_name or ''
        if team_name:
            city_match = re.search(r'\(([^)]+)\)\s*$', team_name)
            if city_match:
                original_city = city_match.group(1).strip()
                original_name_clean = re.sub(r'\s*\([^)]+\)\s*$', '', team_name).strip()
        
        # Ищем команду по ID или slug
        if team_id:
            team = next((t for t in existing_teams if t['_id'] == team_id), None)
        elif team_slug:
            team = next((t for t in existing_teams if t.get('slug') == team_slug), None)
        
        if team:
            # Если в БД есть название - используем его, иначе используем исходное
            # Проверяем сначала name, потом title (как fallback)
            name = team.get('name', '').strip()
            if not name:
                name = team.get('title', '').strip()
            if not name:
                name = original_name_clean
            
            facts = team.get('facts', {})
            
            # Ищем город в facts - проверяем разные варианты ключей
            city = ''
            if isinstance(facts, dict):
                # Основной ключ
                city = facts.get('Город', '') or facts.get('город', '')
                # Альтернативные варианты
                if not city:
                    for key in facts.keys():
                        if 'город' in key.lower():
                            city = facts.get(key, '')
                            break
            
            # Если в БД нет города, но есть в исходном названии - используем исходный
            if not city and original_city:
                city = original_city
            
            # Убираем город из названия, если он уже там есть
            name_clean = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()
            
            if city:
                return f"{name_clean} ({city})"
            return name_clean
        
        # Если команда не найдена - возвращаем исходное название (может там уже есть город)
        return team_name or ''
    
    # Обновляем all_teams с полными названиями и городами
    updated_all_teams = []
    for team_data in season_teams:
        team_slug = team_data.get('slug', '')
        team_name = team_data.get('name', '')
        
        # Находим сопоставленную команду
        matched_team_id = None
        matched_slug = None
        
        if team_slug in team_matches:
            matched_team_id, matched_slug = team_matches[team_slug]
        elif team_name:
            # Пробуем найти по названию
            team_name_clean = re.sub(r'\s*\([^)]*\)\s*$', '', team_name).strip()
            normalized = normalize_team_name(team_name_clean)
            if normalized in team_name_map:
                matched_team_id, matched_slug, _ = team_name_map[normalized]
            else:
                # Фоллбек: match_all_teams может хранить сопоставления по имени в ключе "__name__:<normalized>"
                name_key = normalize_team_name(team_name_clean or team_name)
                key = f"__name__:{name_key}" if name_key else ""
                if key and key in team_matches:
                    matched_team_id, matched_slug = team_matches[key]
                
                # Если всё ещё не нашли — АГРЕССИВНЫЙ ПОИСК: пробуем найти команду по совпадению нормализованного имени
                # Это нужно для команд типа МИСИ, СПСИ, которые могут не сопоставляться точно
                if not matched_team_id:
                    for team in existing_teams:
                        team_db_name = team.get('name', '')
                        team_db_slug = team.get('slug', '')
                        
                        # Проверяем точное совпадение (без учета регистра и скобок)
                        team_db_name_clean = re.sub(r'\s*\([^)]*\)\s*$', '', team_db_name).strip()
                        if normalize_team_name(team_name_clean) == normalize_team_name(team_db_name_clean):
                            matched_team_id = team['_id']
                            matched_slug = team_db_slug
                            break
                        
                        # Проверяем совпадение по slug
                        if team_slug and team_db_slug == team_slug:
                            matched_team_id = team['_id']
                            matched_slug = team_db_slug
                            break
        
        # Получаем полное название с городом
        # ВАЖНО: Передаем исходное team_name, чтобы если команда не найдена, использовался город из исходного названия
        full_name = get_full_team_name(
            team_id=matched_team_id,
            team_slug=matched_slug or team_slug,
            team_name=team_name  # Передаем исходное название с городом, если есть
        )
        
        updated_all_teams.append({
            'slug': matched_slug or team_slug,
            'name': full_name
        })
    
    # Обновляем result_dict
    result_dict['all_teams'] = updated_all_teams
    
    # Обновляем winners с полными названиями и городами
    # ВАЖНО: winners теперь хранит словари {"name": "...", "slug": "..."} для ссылок
    # Сначала собираем всех победителей из финала (где is_winner=True)
    final_winners = []
    for stage_data in result_dict.get('stages', []):
        # Ищем финал
        stage_name = stage_data.get('name', '').lower()
        if 'финал' in stage_name and '/' not in stage_name:
            for game_data in stage_data.get('games', []):
                for team_data in game_data.get('teams', []):
                    if team_data.get('is_winner', False):
                        team_slug = team_data.get('team_slug', '')
                        team_name = team_data.get('team_name', '')
                        team_id = team_data.get('team_id')
                        
                        # Находим сопоставленную команду
                        matched_team_id = team_id
                        matched_slug = team_slug
                        
                        if not matched_team_id and team_slug in team_matches:
                            matched_team_id, matched_slug = team_matches[team_slug]
                        elif not matched_team_id and team_name:
                            team_name_clean = re.sub(r'\s*\([^)]*\)\s*$', '', team_name).strip()
                            normalized = normalize_team_name(team_name_clean)
                            if normalized in team_name_map:
                                matched_team_id, matched_slug, _ = team_name_map[normalized]
                        
                        # Получаем полное название с городом
                        full_name = get_full_team_name(
                            team_id=matched_team_id,
                            team_slug=matched_slug or team_slug,
                            team_name=team_name
                        )
                        
                        # Проверяем, не добавлен ли уже этот победитель
                        winner_exists = any(w.get('name') == full_name for w in final_winners)
                        if full_name and not winner_exists:
                            final_winners.append({
                                'name': full_name,
                                'slug': matched_slug or team_slug
                            })
    
    # Если нашли победителей в финале - используем их
    if final_winners:
        result_dict['winners'] = final_winners
    else:
        # Иначе используем список из парсера
        updated_winners = []
        for winner_name in result_dict.get('winners', []):
            # Пробуем найти команду-победителя
            # winners может содержать как названия, так и slug'и
            matched_team_id = None
            matched_slug = None
            
            # Если winner_name уже словарь (новая структура) - используем его
            if isinstance(winner_name, dict):
                matched_slug = winner_name.get('slug', '')
                winner_name = winner_name.get('name', '')
            
            # Пробуем найти по названию
            winner_name_clean = re.sub(r'\s*\([^)]*\)\s*$', '', winner_name).strip()
            normalized = normalize_team_name(winner_name_clean)
            
            if normalized in team_name_map:
                matched_team_id, matched_slug, _ = team_name_map[normalized]
            else:
                # Пробуем найти по slug (если winner_name - это slug)
                if winner_name in team_matches:
                    matched_team_id, matched_slug = team_matches[winner_name]
            
            # Получаем полное название с городом
            full_name = get_full_team_name(
                team_id=matched_team_id,
                team_slug=matched_slug or winner_name,  # Используем winner_name как slug, если не нашли
                team_name=winner_name
            )
            
            if full_name:
                updated_winners.append({
                    'name': full_name,
                    'slug': matched_slug or winner_name  # Используем winner_name как slug, если не нашли
                })
        
        # Обновляем result_dict
        result_dict['winners'] = updated_winners
    
    # Собираем теги для сезона
    # ВАЖНО: Только "КВН", название лиги и названия команд (без городов в скобках)
    season_tags = ['КВН']
    
    # Добавляем тег лиги
    if LEAGUE_NAME and LEAGUE_NAME != 'КВН':
        season_tags.append(LEAGUE_NAME)
    
    # Добавляем теги всех команд-участниц
    # ВАЖНО: Добавляем только название команды как тег (без города в скобках), НЕ все теги команды из БД
    matched_team_tags = set()
    for team_data in season_teams:
        team_name = team_data.get('name', '')
        if team_name:
            # Убираем город из скобок: "Команда (Город)" -> "Команда"
            team_name_clean = re.sub(r'\s*\([^)]*\)\s*$', '', team_name).strip()
            if team_name_clean:
                matched_team_tags.add(team_name_clean)
    
    season_tags.extend(sorted(matched_team_tags))
    
    # Обновляем модуль "Команды-участники" со ссылками
    # ВАЖНО: Удаляем ВСЕ старые модули "Команды-участники" и создаем один новый
    # Также скрываем старые модули с результатами, так как они теперь в season_data
    updated_modules = []
    
    # Сначала собираем все модули, КРОМЕ "Команды-участники" и старых результатов
    for module in modules:
        module_title = module.get('title', '').lower()
        module_type = module.get('type', '').lower()
        
        # Пропускаем все модули "Команды-участники" - они будут заменены одним новым
        if ('команд' in module_title and 'участн' in module_title) or \
           ('участник' in module_title and 'команд' in module_title):
            continue  # Пропускаем старые модули "Команды-участники"
        
        # Скрываем старые модули с результатами, так как они теперь в season_data
        # Проверяем как по названию, так и по содержимому
        module_content = str(module.get('data', {}).get('content', '')).lower()
        if (module_title in ['результаты', 'результат'] or 
            'результат' in module_content[:100] or  # Первые 100 символов
            (module_type == 'text_block' and '1/8 финала' in module_content or 
             '1/4 финала' in module_content or '1/2 финала' in module_content or
             'финал' in module_content)):
            # Скрываем старые модули с результатами
            module_copy = module.copy()
            module_copy['visible'] = False
            updated_modules.append(module_copy)
        else:
            # Оставляем другие модули (например, "Облако тегов", "Ссылки", общее описание)
            updated_modules.append(module)
    
    # Создаем один новый модуль "Команды-участники" со ссылками
    # ВАЖНО: Используем обновленные all_teams с полными названиями и городами
    if updated_all_teams:
        teams_html_parts = []
        for team_data in updated_all_teams:
            team_slug = team_data.get('slug', '')
            team_name = team_data.get('name', '')  # Уже содержит полное название с городом
            
            # Показываем полное название с городом и ссылкой
            if team_slug:
                teams_html_parts.append(f'<a href="/kvn/teams/{team_slug}">{team_name}</a>')
            else:
                teams_html_parts.append(team_name)
        
        # Находим подходящее место для модуля "Команды-участники"
        # Размещаем его после модулей с общей информацией, но перед скрытыми модулями с результатами
        visible_modules = [m for m in updated_modules if m.get('visible', True)]
        max_order = max([m.get('order', 0) for m in visible_modules], default=0) if visible_modules else 0
        
        # Создаем новый модуль "Команды-участники"
        # Размещаем его после всех видимых модулей
        new_module = {
            'id': str(uuid4()),
            'type': 'text_block',
            'order': max_order + 1,
            'title': 'Команды-участники',
            'visible': True,
            'data': {
                'title': 'Команды-участники',
                'content': ', '.join(teams_html_parts)
            }
        }
        # Вставляем модуль перед скрытыми модулями с результатами
        # Находим первый скрытый модуль и вставляем перед ним
        hidden_index = next((i for i, m in enumerate(updated_modules) if not m.get('visible', True)), len(updated_modules))
        updated_modules.insert(hidden_index, new_module)
    
    # Статистика
    total_games = sum(len(s['games']) for s in result_dict['stages'])
    total_teams = len(season_teams)
    # matched_count должен считаться "по командам сезона", а не "по ключам словаря",
    # потому что часть сопоставлений может быть сохранена по ключу "__name__:<...>".
    matched_count = 0
    for t in season_teams:
        slug = (t.get('slug') or '').strip()
        if slug and slug in team_matches:
            matched_count += 1
            continue
        name_key = normalize_team_name(t.get('name', ''))
        if name_key and f"__name__:{name_key}" in team_matches:
            matched_count += 1
    
    print(f"  📊 Стадий: {len(result_dict['stages'])}, Игр: {total_games}, Команд: {total_teams}")
    print(f"  🔗 Сопоставлено команд: {matched_count}/{total_teams}")
    print(f"  🏷️  Тегов: {len(season_tags)}")
    
    if result_dict['winners']:
        print(f"  🏆 Победители: {result_dict['winners']}")
    
    if verbose:
        for stage in result_dict['stages']:
            print(f"    📌 {stage['name']} ({len(stage['games'])} игр)")
            for game in stage['games']:
                print(f"      🎮 {game['name']} - {game['date'] or 'дата не указана'}")
    
    # Записываем в БД
    if apply:
        # Синхронизируем теги
        sync_tags_to_collection(season_tags, db)
        
        # Обновляем документ сезона
        # ВАЖНО: Сохраняем все модули (не удаляем старый контент)
        # Результаты хранятся в season_data и рендерятся отдельно
        update_data = {
            'season_data': result_dict,
            'tags': season_tags,
            'modules': updated_modules  # Сохраняем все модули (включая скрытые старые результаты)
        }
        
        db.kvn.update_one(
            {'_id': season_doc['_id']},
            {'$set': update_data}
        )
        print(f"  ✅ Записано в БД")
    else:
        print(f"  🔍 Dry-run: используйте --apply для записи")
        if verbose:
            print(f"  📋 Теги для добавления: {season_tags}")
    
    return result_dict


def get_league_seasons(db) -> list:
    """Получает все сезоны международной лиги."""
    # Находим страницу лиги
    league = db.kvn.find_one({'slug': LEAGUE_SLUG})
    if not league:
        league = db.kvn.find_one({'full_path': f'kvn/{LEAGUE_SLUG}'})
    
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
        'full_path': {'$regex': f'^kvn/{LEAGUE_SLUG}/.*\\d{{4}}'}
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
        description='Обработка сезонов Международной лиги КВН',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Один сезон (dry-run)
  python process_ml_seasons.py --path kvn/ml-kvn/2023
  
  # Один сезон с записью в БД
  python process_ml_seasons.py --path kvn/ml-kvn/2023 --apply
  
  # Все сезоны международной лиги
  python process_ml_seasons.py --all --apply
        """
    )
    parser.add_argument('--path', type=str, help='Полный путь к сезону')
    parser.add_argument('--all', action='store_true', help='Обработать все сезоны международной лиги')
    parser.add_argument('--apply', action='store_true', help='Записать в БД')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробный вывод')
    parser.add_argument('--output', '-o', type=str, help='Сохранить результат в JSON файл')
    
    args = parser.parse_args()
    
    if not args.path and not args.all:
        parser.error("Укажите --path или --all")
    
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
        
        elif args.all:
            # Все сезоны международной лиги
            print(f"\n📋 Обработка всех сезонов {LEAGUE_NAME}")
            seasons = get_league_seasons(db)
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
