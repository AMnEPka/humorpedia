#!/usr/bin/env python3
"""
Модуль для сопоставления команд из сезонов с существующими командами в БД.

Поддерживает:
- Точное совпадение по названию или slug
- Совпадение по алиасам
- Нормализацию падежей (Сборную Пермского края -> Сборная Пермского края)
- Частичное совпадение по вхождению
"""

import re
from typing import List, Dict, Optional, Tuple


def normalize_case(name: str) -> str:
    """
    Нормализует падеж названия команды.
    
    Преобразует винительный падеж в именительный:
    - "Сборную Пермского края" -> "Сборная Пермского края"
    - "Команду КВН" -> "Команда КВН"
    """
    if not name:
        return name
    
    words = name.split()
    if not words:
        return name
    
    first_word = words[0]
    
    # Проверяем окончания винительного падежа для первого слова
    if first_word.endswith('ую') and len(first_word) > 3:
        words[0] = first_word[:-2] + 'ая'
    elif first_word.endswith('юю') and len(first_word) > 3:
        words[0] = first_word[:-2] + 'яя'
    elif first_word.endswith('у') and len(first_word) > 2:
        if first_word[-2] not in 'аеёиоуыэюя':
            words[0] = first_word[:-1] + 'а'
    
    return ' '.join(words)


def normalize_team_name(name: str) -> str:
    """
    Нормализует название команды для сравнения.
    
    1. Приводит к нижнему регистру
    2. Убирает лишние пробелы
    3. Убирает кавычки
    4. Нормализует падеж
    """
    if not name:
        return ""
    
    # Нормализуем падеж сначала (до lower)
    name = normalize_case(name)
    
    # Приводим к нижнему регистру, убираем лишние пробелы
    normalized = re.sub(r'\s+', ' ', name.lower().strip())
    # Убираем кавычки
    normalized = normalized.replace('«', '').replace('»', '').replace('"', '').replace("'", '')
    return normalized


def match_team_by_name(
    team_name: str,
    team_slug: str,
    existing_teams: List[Dict],
    team_slug_map: Dict[str, str] = None
) -> Optional[Tuple[str, str]]:
    """
    Сопоставляет команду из сезона с существующей командой в БД.
    
    Args:
        team_name: Название команды из сезона
        team_slug: Slug команды из сезона (если есть)
        existing_teams: Список существующих команд из БД
        team_slug_map: Карта slug -> название (опционально)
        
    Returns:
        Tuple (team_id, team_slug) если найдено, иначе None
    """
    if not team_name:
        return None
    
    normalized_name = normalize_team_name(team_name)
    
    # 1. Точное совпадение по slug (если есть)
    if team_slug:
        for team in existing_teams:
            if team.get('slug') == team_slug:
                return (team['_id'], team['slug'])
    
    # 2. Точное совпадение по названию
    for team in existing_teams:
        # Используем name, если есть, иначе title как fallback
        team_name = team.get('name', '').strip() or team.get('title', '').strip()
        team_normalized = normalize_team_name(team_name)
        if team_normalized == normalized_name:
            return (team['_id'], team['slug'])
    
    # 3. Совпадение по алиасам
    for team in existing_teams:
        aliases = team.get('aliases', [])
        for alias in aliases:
            alias_normalized = normalize_team_name(alias)
            if alias_normalized == normalized_name:
                return (team['_id'], team['slug'])
    
    # 4. Частичное совпадение (если одно название содержит другое)
    for team in existing_teams:
        # Используем name, если есть, иначе title как fallback
        team_name = team.get('name', '').strip() or team.get('title', '').strip()
        team_normalized = normalize_team_name(team_name)
        # Проверяем вхождение (но не слишком короткие слова)
        if len(normalized_name) > 3 and len(team_normalized) > 3:
            if normalized_name in team_normalized or team_normalized in normalized_name:
                return (team['_id'], team['slug'])
        
        # Проверяем алиасы
        aliases = team.get('aliases', [])
        for alias in aliases:
            alias_normalized = normalize_team_name(alias)
            if len(normalized_name) > 3 and len(alias_normalized) > 3:
                if normalized_name in alias_normalized or alias_normalized in normalized_name:
                    return (team['_id'], team['slug'])
    
    # 5. Поиск через team_slug_map (если передан)
    if team_slug_map and team_slug:
        mapped_name = team_slug_map.get(team_slug.lower())
        if mapped_name:
            mapped_normalized = normalize_team_name(mapped_name)
            for team in existing_teams:
                # Используем name, если есть, иначе title как fallback
                team_name = team.get('name', '').strip() or team.get('title', '').strip()
                team_normalized = normalize_team_name(team_name)
                if team_normalized == mapped_normalized:
                    return (team['_id'], team['slug'])
    
    return None


def match_all_teams(
    season_teams: List[Dict],
    existing_teams: List[Dict],
    team_slug_map: Dict[str, str] = None
) -> Dict[str, Tuple[str, str]]:
    """
    Сопоставляет все команды сезона с существующими командами.
    
    Args:
        season_teams: Список команд из сезона [{"slug": "...", "name": "..."}]
        existing_teams: Список существующих команд из БД
        team_slug_map: Карта slug -> название (опционально)
        
    Returns:
        Словарь: team_slug -> (team_id, team_slug)
    """
    matches = {}
    
    for team in season_teams:
        team_slug = team.get('slug', '')
        team_name = team.get('name', '')
        
        match = match_team_by_name(team_name, team_slug, existing_teams, team_slug_map)
        if match:
            matches[team_slug] = match
    
    return matches

