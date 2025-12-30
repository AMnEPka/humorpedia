"""
Сервис автоматического связывания городов с людьми и командами.

Логика связывания:
- Люди: если facts["Место рождения"] содержит название города
- Команды: если facts["Город"] содержит название города

Варианты запуска:
1. Ручной: POST /api/cities/link-all
2. Периодический: cron job или scheduler
3. При сохранении: вызывается из update endpoint
"""

import logging
from typing import List, Dict, Any, Optional
import re

logger = logging.getLogger(__name__)


def normalize_city_name(name: str) -> str:
    """Нормализует название города для сравнения."""
    if not name:
        return ""
    # Убираем "г.", "город", пробелы, приводим к нижнему регистру
    normalized = name.lower().strip()
    normalized = re.sub(r'^г\.\s*', '', normalized)
    normalized = re.sub(r'^город\s+', '', normalized)
    normalized = normalized.strip()
    return normalized


def city_matches(city_name: str, field_value: str) -> bool:
    """Проверяет, совпадает ли название города с полем."""
    if not city_name or not field_value:
        return False
    
    norm_city = normalize_city_name(city_name)
    norm_field = normalize_city_name(field_value)
    
    # Точное совпадение или содержание
    return norm_city == norm_field or norm_city in norm_field


async def find_people_by_city(db, city_name: str) -> List[str]:
    """
    Находит людей, родившихся в указанном городе.
    Ищет в facts["Место рождения"].
    """
    people_ids = []
    
    # Ищем в коллекции people
    cursor = db.people.find({"status": "published"}, {"_id": 1, "facts": 1, "title": 1})
    
    async for person in cursor:
        facts = person.get("facts", {})
        birth_place = facts.get("Место рождения", "")
        
        if city_matches(city_name, birth_place):
            people_ids.append(person["_id"])
            logger.debug(f"Found person for {city_name}: {person.get('title')} (birth: {birth_place})")
    
    return people_ids


async def find_teams_by_city(db, city_name: str) -> List[str]:
    """
    Находит команды из указанного города.
    Ищет в facts["Город"].
    """
    team_ids = []
    
    # Ищем в коллекции teams
    cursor = db.teams.find({"status": "published"}, {"_id": 1, "facts": 1, "title": 1})
    
    async for team in cursor:
        facts = team.get("facts", {})
        team_city = facts.get("Город", "")
        
        if city_matches(city_name, team_city):
            team_ids.append(team["_id"])
            logger.debug(f"Found team for {city_name}: {team.get('title')} (city: {team_city})")
    
    return team_ids


async def link_city(db, city_id: str) -> Dict[str, Any]:
    """
    Связывает один город с людьми и командами.
    Возвращает статистику связывания.
    """
    city = await db.cities.find_one({"_id": city_id})
    if not city:
        return {"error": "City not found", "city_id": city_id}
    
    city_name = city.get("name") or city.get("title")
    
    # Находим связанных людей и команды
    people_ids = await find_people_by_city(db, city_name)
    team_ids = await find_teams_by_city(db, city_name)
    
    # Обновляем город
    await db.cities.update_one(
        {"_id": city_id},
        {"$set": {
            "related_person_ids": people_ids,
            "related_team_ids": team_ids
        }}
    )
    
    return {
        "city_id": city_id,
        "city_name": city_name,
        "people_count": len(people_ids),
        "teams_count": len(team_ids),
        "people_ids": people_ids,
        "team_ids": team_ids
    }


async def link_all_cities(db) -> Dict[str, Any]:
    """
    Связывает все города с людьми и командами.
    Возвращает общую статистику.
    """
    results = []
    total_people = 0
    total_teams = 0
    
    cursor = db.cities.find({}, {"_id": 1, "name": 1, "title": 1})
    
    async for city in cursor:
        result = await link_city(db, city["_id"])
        results.append(result)
        total_people += result.get("people_count", 0)
        total_teams += result.get("teams_count", 0)
    
    return {
        "cities_processed": len(results),
        "total_people_linked": total_people,
        "total_teams_linked": total_teams,
        "details": results
    }


async def link_person_to_cities(db, person_id: str) -> Dict[str, Any]:
    """
    При сохранении человека - обновляет связи в соответствующих городах.
    """
    person = await db.people.find_one({"_id": person_id})
    if not person:
        return {"error": "Person not found"}
    
    facts = person.get("facts", {})
    birth_place = facts.get("Место рождения", "")
    
    if not birth_place:
        return {"person_id": person_id, "cities_updated": 0}
    
    # Находим город по названию
    norm_place = normalize_city_name(birth_place)
    
    cities_updated = 0
    cursor = db.cities.find({}, {"_id": 1, "name": 1, "title": 1, "related_person_ids": 1})
    
    async for city in cursor:
        city_name = city.get("name") or city.get("title")
        if city_matches(city_name, birth_place):
            # Добавляем человека в город если его там нет
            current_people = city.get("related_person_ids", [])
            if person_id not in current_people:
                await db.cities.update_one(
                    {"_id": city["_id"]},
                    {"$addToSet": {"related_person_ids": person_id}}
                )
                cities_updated += 1
    
    return {"person_id": person_id, "cities_updated": cities_updated}


async def link_team_to_cities(db, team_id: str) -> Dict[str, Any]:
    """
    При сохранении команды - обновляет связи в соответствующих городах.
    """
    team = await db.teams.find_one({"_id": team_id})
    if not team:
        return {"error": "Team not found"}
    
    facts = team.get("facts", {})
    team_city = facts.get("Город", "")
    
    if not team_city:
        return {"team_id": team_id, "cities_updated": 0}
    
    cities_updated = 0
    cursor = db.cities.find({}, {"_id": 1, "name": 1, "title": 1, "related_team_ids": 1})
    
    async for city in cursor:
        city_name = city.get("name") or city.get("title")
        if city_matches(city_name, team_city):
            # Добавляем команду в город если её там нет
            current_teams = city.get("related_team_ids", [])
            if team_id not in current_teams:
                await db.cities.update_one(
                    {"_id": city["_id"]},
                    {"$addToSet": {"related_team_ids": team_id}}
                )
                cities_updated += 1
    
    return {"team_id": team_id, "cities_updated": cities_updated}
