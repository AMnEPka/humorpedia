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

    # Убираем город/пояснение в скобках в конце: "Команда (Город)" -> "Команда"
    name = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()
    
    # Приводим к нижнему регистру, убираем лишние пробелы
    normalized = re.sub(r'\s+', ' ', name.lower().strip())
    # Убираем кавычки
    normalized = normalized.replace('«', '').replace('»', '').replace('"', '').replace("'", '')

    # Нормализуем "ё" -> "е" (в названиях часто плавает)
    normalized = normalized.replace('ё', 'е')

    # Убираем пунктуацию/разделители (оставляем только буквы/цифры/пробелы)
    normalized = re.sub(r'[^0-9a-zа-я]+', ' ', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    # Аббревиатуры/инициалы: "Т.Т.", "Т. Т." -> "тт"
    tokens = normalized.split()
    if tokens and all(len(t) == 1 for t in tokens):
        normalized = ''.join(tokens)
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
        team_slug_map: Карта название(lower, без города) -> slug (опционально)
        
    Returns:
        Tuple (team_id, team_slug) если найдено, иначе None
    """
    # ВАЖНО: slug может быть, даже если name отсутствует (особенно если парсер извлёк только ссылку).
    # Поэтому сначала всегда пытаемся сопоставить по slug.
    if team_slug:
        for team in existing_teams:
            if team.get('slug') == team_slug:
                return (team['_id'], team['slug'])

    # Если нет ни name, ни slug — сопоставлять нечего
    if not team_name and not team_slug:
        return None

    # Очищаем название от города в скобках: "Команда (Город)" -> "Команда"
    team_name_clean = re.sub(r'\s*\([^)]*\)\s*$', '', (team_name or '')).strip()
    normalized_name = normalize_team_name(team_name_clean or team_name or "")
    
    # 2. Точное совпадение по названию
    for team in existing_teams:
        # Используем name, если есть, иначе title как fallback
        db_team_name = team.get('name', '').strip() or team.get('title', '').strip()
        # Также убираем город в скобках, если он зачем-то попал в БД
        db_team_name_clean = re.sub(r'\s*\([^)]*\)\s*$', '', db_team_name).strip()
        team_normalized = normalize_team_name(db_team_name_clean or db_team_name)
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
        db_team_name = team.get('name', '').strip() or team.get('title', '').strip()
        db_team_name_clean = re.sub(r'\s*\([^)]*\)\s*$', '', db_team_name).strip()
        team_normalized = normalize_team_name(db_team_name_clean or db_team_name)
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
    
    # 5. Поиск через team_slug_map (если передан).
    # В парсере карта строится как: name(lower, без города) -> slug.
    # Используем её, чтобы:
    # - восстановить slug, если он отсутствует у команды сезона
    # - затем сопоставить по slug (самый надёжный вариант)
    if team_slug_map and not team_slug:
        key = (team_name_clean or team_name or "").lower().strip()
        mapped_slug = team_slug_map.get(key)
        if not mapped_slug and key:
            # Пробуем частичное совпадение по ключам карты
            for map_name, map_slug in team_slug_map.items():
                if len(key) > 3 and (key in map_name or map_name in key):
                    mapped_slug = map_slug
                    break
        if mapped_slug:
            for team in existing_teams:
                if team.get('slug') == mapped_slug:
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
        team_slug_map: Карта название(lower, без города) -> slug (опционально)
        
    Returns:
        Словарь: team_slug -> (team_id, team_slug)
    """
    matches: Dict[str, Tuple[str, str]] = {}
    
    for team in season_teams:
        team_slug = team.get('slug', '')
        team_name = team.get('name', '')
        
        match = match_team_by_name(team_name, team_slug, existing_teams, team_slug_map)
        if match:
            # ВАЖНО: у многих команд slug может отсутствовать (""), особенно если в исходном HTML нет ссылок.
            # Нельзя использовать "" как ключ — иначе все такие команды "схлопнутся" в одну запись,
            # и статистика/фоллбеки будут выглядеть как постепенное улучшение по 1 команде за запуск.
            if team_slug:
                matches[team_slug] = match
            else:
                name_key = normalize_team_name(team_name)
                if name_key:
                    matches[f"__name__:{name_key}"] = match
    
    return matches

