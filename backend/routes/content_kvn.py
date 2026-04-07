"""KVN routes — CRUD + hierarchy + seasons + jury stats."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone
import re
import uuid
import json
import traceback
import logging

from models.base import ContentStatus
from models.content import KVN, KVNCreate, KVNUpdate
from utils.database import get_db
from services.crud import (
    check_slug_unique, create_content, delete_content,
    get_by_id_or_slug, convert_objectids_to_strings,
)
from services.tags import tag_service
from services.linking import linking_service
from services.link_resolver import LinkResolver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["kvn"])


# ---------------------------------------------------------------------------
#  KVN helper functions
# ---------------------------------------------------------------------------

def get_league_slug_from_parent(parent_doc):
    """Определяет league_slug из родительского документа KVN"""
    if not parent_doc:
        return None
    
    parent_slug = parent_doc.get("slug", "")
    parent_full_path = parent_doc.get("full_path", "")
    
    # Проверяем slug родителя
    if parent_slug == "vl-kvn":
        return "vl-kvn"
    elif parent_slug == "premier-liga":
        return "premier-liga"
    elif parent_slug == "1l-kvn":
        return "1l-kvn"
    elif parent_slug == "ml-kvn":
        return "ml-kvn"

def extract_year_from_slug(slug: str) -> int:
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


async def find_adjacent_seasons(db, current_season: dict) -> tuple[str, str]:
    """
    Находит соседние сезоны для текущего сезона.
    
    Returns:
        Tuple (prev_season_slug, next_season_slug)
    """
    season_data = current_season.get("season_data", {})
    year = season_data.get("year", 0)
    league_slug = season_data.get("league_slug", "")
    
    # Если нет года или лиги, пытаемся извлечь из slug или full_path
    if not year:
        slug = current_season.get("slug", "")
        full_path = current_season.get("full_path", "")
        year = extract_year_from_slug(slug) or extract_year_from_slug(full_path)
    
    if not league_slug:
        # Приоритет 1: пытаемся получить из родительского ресурса (самый надежный способ)
        parent_id = current_season.get("parent_id")
        if parent_id:
            parent = await db.kvn.find_one({"id": parent_id})
            if not parent:
                parent = await db.kvn.find_one({"_id": parent_id})
            if parent:
                league_slug = get_league_slug_from_parent(parent)
        
        # Приоритет 2: пытаемся извлечь из full_path (формат: kvn/league-slug/season-slug)
        if not league_slug:
            full_path = current_season.get("full_path", "")
            # Убираем начальный слэш, если есть, и разбиваем путь
            path_parts = full_path.lstrip("/").split("/")
            if len(path_parts) >= 2 and path_parts[0] == "kvn":
                league_slug = path_parts[1]
    
    if not year or not league_slug:
        return "", ""
    
    prev_season_slug = ""
    next_season_slug = ""
    
    # Ищем предыдущий сезон (year - 1)
    prev_year = year - 1
    # Ищем следующий сезон (year + 1)
    next_year = year + 1
    
    # Ищем сезоны в той же лиге
    # Вариант 1 (самый надежный): ищем по season_data.year напрямую
    if not prev_season_slug:
        prev_season = await db.kvn.find_one({
            "season_data.year": prev_year,
            "season_data.league_slug": league_slug
        }, {"slug": 1})
        if prev_season:
            prev_season_slug = prev_season.get("slug", "")
    
    if not next_season_slug:
        next_season = await db.kvn.find_one({
            "season_data.year": next_year,
            "season_data.league_slug": league_slug
        }, {"slug": 1})
        if next_season:
            next_season_slug = next_season.get("slug", "")
    
    # Вариант 1.5: ищем сезоны без season_data, но с правильным full_path и годом в slug
    # Это помогает найти сезоны, созданные вручную без полного season_data
    if not prev_season_slug or not next_season_slug:
        # Ищем все сезоны с правильным full_path паттерном
        escaped_league = re.escape(league_slug)
        for target_year in [prev_year, next_year]:
            if target_year == prev_year and prev_season_slug:
                continue
            if target_year == next_year and next_season_slug:
                continue
            
            # Ищем сезоны с годом в full_path или slug
            candidates = await db.kvn.find({
                "$or": [
                    {"full_path": {"$regex": f"kvn/{escaped_league}/.*{target_year}"}},
                    {"slug": {"$regex": f".*{target_year}"}}
                ]
            }, {"slug": 1, "season_data": 1, "full_path": 1, "parent_id": 1}).to_list(20)
            
            for candidate in candidates:
                # Проверяем, что это действительно сезон нужного года
                c_year = candidate.get("season_data", {}).get("year", 0)
                if not c_year:
                    c_year = extract_year_from_slug(candidate.get("slug", ""))
                if not c_year:
                    c_year = extract_year_from_slug(candidate.get("full_path", ""))
                
                # Проверяем, что это сезон той же лиги (по parent_id или full_path)
                is_same_league = False
                candidate_parent_id = candidate.get("parent_id")
                current_parent_id = current_season.get("parent_id")
                if candidate_parent_id and current_parent_id and candidate_parent_id == current_parent_id:
                    is_same_league = True
                else:
                    # Проверяем по full_path
                    candidate_full_path = candidate.get("full_path", "")
                    if candidate_full_path.startswith(f"kvn/{league_slug}/") or f"/{league_slug}/" in candidate_full_path:
                        is_same_league = True
                
                if c_year == target_year and is_same_league:
                    found_slug = candidate.get("slug", "")
                    if target_year == prev_year and not prev_season_slug:
                        prev_season_slug = found_slug
                    elif target_year == next_year and not next_season_slug:
                        next_season_slug = found_slug
                    break
    
    # Вариант 2: по parent_id (если сезоны - дочерние страницы лиги)
    if not prev_season_slug or not next_season_slug:
        parent_id = current_season.get("parent_id")
        if parent_id:
            # Ищем все сезоны той же лиги
            all_seasons = await db.kvn.find(
                {"parent_id": parent_id},
                {"slug": 1, "season_data": 1, "full_path": 1}
            ).to_list(1000)
            
            # Сортируем по году
            seasons_by_year = {}
            for season in all_seasons:
                s_year = season.get("season_data", {}).get("year", 0)
                if not s_year:
                    # Пытаемся извлечь год из slug
                    s_year = extract_year_from_slug(season.get("slug", ""))
                if not s_year:
                    # Если не нашли в slug, пытаемся извлечь из full_path
                    s_year = extract_year_from_slug(season.get("full_path", ""))
                if s_year:
                    seasons_by_year[s_year] = season.get("slug", "")
            
            if not prev_season_slug and prev_year in seasons_by_year:
                prev_season_slug = seasons_by_year[prev_year]
            if not next_season_slug and next_year in seasons_by_year:
                next_season_slug = seasons_by_year[next_year]
    
    # Вариант 3: по full_path с regex (если не нашли предыдущими способами)
    if not prev_season_slug or not next_season_slug:
        # Ищем сезоны по full_path с годом
        for target_year in [prev_year, next_year]:
            if target_year == prev_year and prev_season_slug:
                continue
            if target_year == next_year and next_season_slug:
                continue
            
            # Ищем сезон с нужным годом в той же лиге
            # Варианты full_path: kvn/vl-kvn/vl-2009, kvn/vl-kvn/2009 и т.д.
            # Ищем по regex, который ищет год как отдельное число (не часть другого числа)
            # Используем границы слова или начало/конец строки для точного совпадения года
            escaped_league = re.escape(league_slug)
            patterns = [
                f"^kvn/{escaped_league}/.*-{target_year}$",  # kvn/vl-kvn/vl-2009
                f"^kvn/{escaped_league}/{target_year}$",      # kvn/vl-kvn/2009
                f"^kvn/{escaped_league}/.*{target_year}$",     # любой вариант с годом в конце
                f"kvn/{escaped_league}/.*-{target_year}$",     # без ^ в начале (на случай если путь без начального слэша)
                f"kvn/{escaped_league}/{target_year}$",
                f"kvn/{escaped_league}/.*{target_year}$",
            ]
            
            for pattern in patterns:
                seasons = await db.kvn.find({
                    "full_path": {"$regex": pattern}
                }, {"slug": 1, "season_data": 1, "full_path": 1}).to_list(10)
                
                # Проверяем каждый найденный сезон, чтобы убедиться, что год совпадает
                for season in seasons:
                    # Проверяем год в season_data
                    s_year = season.get("season_data", {}).get("year", 0)
                    if not s_year:
                        # Если нет в season_data, извлекаем из slug
                        s_year = extract_year_from_slug(season.get("slug", ""))
                    if not s_year:
                        # Если не нашли в slug, пытаемся извлечь из full_path
                        s_year = extract_year_from_slug(season.get("full_path", ""))
                    
                    # Если год совпадает - это наш сезон
                    if s_year == target_year:
                        found_slug = season.get("slug", "")
                        if target_year == prev_year:
                            prev_season_slug = found_slug
                        else:
                            next_season_slug = found_slug
                        break
                
                if (target_year == prev_year and prev_season_slug) or (target_year == next_year and next_season_slug):
                    break
    
    return prev_season_slug, next_season_slug


@router.get("/kvn/jury-stats", response_model=dict)
async def get_kvn_jury_stats(
    league_slug: str = "vl-kvn",
    min_year: Optional[int] = None,
    max_year: Optional[int] = None
):
    """
    Get jury statistics for KVN seasons.
    Returns aggregated data about all jury members with their game counts and details.
    """
    db = await get_db()
    
    # Get all teams from teams collection (without filtering by team_type)
    all_teams_from_db = await db.teams.find({}, {"slug": 1, "name": 1, "title": 1}).to_list(1000)
    team_slug_to_name = {}
    all_team_slugs = set()
    for team in all_teams_from_db:
        slug = team.get("slug", "")
        name = team.get("name") or team.get("title", "")
        if slug:
            all_team_slugs.add(slug)
            team_slug_to_name[slug] = name
    
    # Build query for seasons
    query = {
        "season_data.league_slug": league_slug
    }
    
    # Build year filter
    year_filter = {}
    if min_year is not None:
        year_filter["$gte"] = min_year
    if max_year is not None:
        year_filter["$lte"] = max_year
    
    if year_filter:
        query["season_data.year"] = year_filter
    
    # Get all seasons for the league
    seasons = await db.kvn.find(query).to_list(1000)
    
    # Aggregate jury statistics
    jury_stats = {}  # jury_name -> { games_count, games: [...], years: set(), teams: set() }
    all_years = set()
    
    for season in seasons:
        season_data = season.get("season_data", {})
        year = season_data.get("year", 0)
        season_slug = season.get("slug", "")
        season_name = season.get("name") or season.get("title", "")
        all_years.add(year)
        
        stages = season_data.get("stages", [])
        for stage in stages:
            games = stage.get("games", [])
            for game in games:
                jury = game.get("jury", [])
                game_name = game.get("name", "")
                game_date = game.get("date", "")
                stage_name = stage.get("name", "")
                
                # Get teams from this game
                teams = game.get("teams", [])
                team_slugs = []
                for team in teams:
                    team_slug = team.get("team_slug", "")
                    if team_slug and team_slug in all_team_slugs:
                        team_slugs.append(team_slug)
                
                # Process each jury member
                for jury_member in jury:
                    if not jury_member:
                        continue
                    
                    if jury_member not in jury_stats:
                        jury_stats[jury_member] = {
                            "games_count": 0,
                            "games": [],
                            "years": set(),
                            "teams": set()
                        }
                    
                    jury_stats[jury_member]["games_count"] += 1
                    jury_stats[jury_member]["years"].add(year)
                    for team_slug in team_slugs:
                        jury_stats[jury_member]["teams"].add(team_slug)
                    
                    # Add game details
                    jury_stats[jury_member]["games"].append({
                        "year": year,
                        "season_slug": season_slug,
                        "season_name": season_name,
                        "stage_name": stage_name,
                        "game_name": game_name,
                        "game_date": game_date,
                        "teams": team_slugs
                    })
    
    # Function to get last name (last word) for sorting
    def get_last_name_for_sort(name):
        """Get last name (last word) from full name for sorting"""
        if not name:
            return ""
        parts = name.strip().split()
        if len(parts) > 0:
            return parts[-1].lower()  # Return last word in lowercase for sorting
        return name.lower()
    
    # Convert sets to lists for JSON serialization
    result = {
        "jury_members": [],
        "all_years": sorted(list(all_years)),
        "all_teams": sorted(list(all_team_slugs)),
        "team_names": team_slug_to_name,
        "total_games": sum(stats["games_count"] for stats in jury_stats.values())
    }
    
    for jury_name, stats in jury_stats.items():
        result["jury_members"].append({
            "name": jury_name,
            "games_count": stats["games_count"],
            "years": sorted(list(stats["years"])),
            "teams": sorted(list(stats["teams"])),
            "games": stats["games"]
        })
    
    # Sort jury members by last name (alphabetically)
    result["jury_members"].sort(key=lambda x: get_last_name_for_sort(x["name"]))
    
    return result


def _get_city_from_facts(facts: dict) -> str:
    """Extract city from team facts, handling various formats"""
    if not isinstance(facts, dict):
        return ""
    
    # Ищем город по разным вариантам ключей
    city_value = (
        facts.get("Город") or 
        facts.get("город") or 
        facts.get("Города") or 
        facts.get("города") or 
        ""
    )
    
    if not city_value:
        return ""
    
    # Если это строка, обрабатываем HTML и разделители
    if isinstance(city_value, str):
        # Удаляем HTML-теги (особенно <br>)
        cleaned = re.sub(r'<br\s*/?>', '\n', city_value, flags=re.IGNORECASE)
        cleaned = re.sub(r'<[^>]+>', '', cleaned).strip()
        
        # Разделяем по новой строке, запятой или слэшу
        cities = [
            c.strip() 
            for c in re.split(r'[\n,;/]', cleaned) 
            if c.strip()
        ]
        
        # Возвращаем все города через запятую
        return ', '.join(cities) if cities else ""
    
    return str(city_value).strip()


# ---------------------------------------------------------------------------
#  KVN CRUD routes
# ---------------------------------------------------------------------------

@router.post("/kvn", response_model=dict)
async def create_kvn(data: KVNCreate):
    """Create a new KVN page"""
    await check_slug_unique("kvn", data.slug)
    
    db = await get_db()
    
    # Calculate level and full_path based on parent
    level = 0
    full_path = data.slug
    parent = None
    if data.parent_id:
        # For KVN, parent_id is a UUID string, not _id
        # Try to find by 'id' field first, then fallback to _id
        parent = await db.kvn.find_one({"id": data.parent_id})
        if not parent:
            parent = await db.kvn.find_one({"_id": data.parent_id})
        if not parent:
            raise HTTPException(status_code=404, detail="Parent KVN page not found")
        
        parent_level = parent.get("level", 0)
        if parent_level >= 4:
            raise HTTPException(status_code=400, detail="Maximum hierarchy level (4) reached")
        
        level = parent_level + 1
        parent_path = parent.get("full_path", parent.get("slug"))
        full_path = f"{parent_path}/{data.slug}"
    
    kvn = KVN(
        title=data.title,
        slug=data.slug,
        name=data.name,
        poster=data.poster,
        description=data.description,
        parent_id=data.parent_id,
        level=level,
        full_path=full_path,
        facts=data.facts or {},
        facts_order=data.facts_order or [],
        social_links=data.social_links or {},
        modules=data.modules,
        tags=data.tags,
        seo=data.seo or {},
        status=data.status,
        team_ids=data.team_ids or [],
        person_ids=data.person_ids or []
    )
    
    result = await create_content("kvn", kvn, data.tags)
    
    # Автоматически добавляем league_slug в season_data, если создается дочерняя страница с родителем "Высшая лига КВН"
    if parent:
        league_slug = get_league_slug_from_parent(parent)
        if league_slug:
            # Проверяем, есть ли уже season_data в документе
            created_doc = await db.kvn.find_one({"id": result["id"]})
            if created_doc:
                season_data = created_doc.get("season_data", {})
                # Если season_data существует, но нет league_slug - добавляем
                if season_data and not season_data.get("league_slug"):
                    season_data["league_slug"] = league_slug
                    await db.kvn.update_one(
                        {"_id": created_doc["_id"]},
                        {"$set": {"season_data": season_data}}
                    )
                    logger.info(f"Автоматически добавлен league_slug '{league_slug}' в season_data для нового документа KVN")
                # Если season_data не существует, но это сезон (определяем по full_path или slug, содержащему год)
                elif not season_data:
                    # Проверяем, является ли это сезоном (slug или full_path содержит год)

                    year_match = re.search(r'\b(19|20)\d{2}\b', full_path)
                    if year_match:
                        # Создаем базовую структуру season_data с league_slug
                        year = int(year_match.group())
                        season_data = {
                            "league_slug": league_slug,
                            "year": year
                        }
                        await db.kvn.update_one(
                            {"_id": created_doc["_id"]},
                            {"$set": {"season_data": season_data}}
                        )
                        logger.info(f"Автоматически создан season_data с league_slug '{league_slug}' для нового сезона {year}")
    
    # Update parent's child_kvn_ids if parent exists
    if data.parent_id:
        # Find parent by 'id' field (UUID) for KVN
        parent_doc = await db.kvn.find_one({"id": data.parent_id})
        if not parent_doc:
            # Fallback to _id if not found by id
            parent_doc = await db.kvn.find_one({"_id": data.parent_id})
        if parent_doc:
            await db.kvn.update_one(
                {"_id": parent_doc["_id"]},
                {"$addToSet": {"child_kvn_ids": result["id"]}}
            )
    
    # Update person and team links
    if data.person_ids:
        await linking_service.update_person_links("kvn", result["id"], data.person_ids)
    if data.team_ids:
        await linking_service.update_team_links("kvn", result["id"], data.team_ids)
    
    return result


@router.get("/kvn", response_model=dict)
async def list_kvn(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[ContentStatus] = None,
    include_children: bool = False
):
    """List KVN pages"""
    db = await get_db()
    query = {}
    
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
            {"slug": {"$regex": search, "$options": "i"}}
        ]
    
    if status:
        query["status"] = status.value
    
    if not include_children:
        query["parent_id"] = None  # Only root pages
    
    count = await db.kvn.count_documents(query)
    cursor = db.kvn.find(query, {"_id": 0}).sort("title", 1).skip(skip).limit(limit)
    items = await cursor.to_list(limit)
    
    return {"items": items, "total": count, "skip": skip, "limit": limit}

@router.get("/kvn/by-path/{path:path}", response_model=dict)
async def get_kvn_by_path(path: str):
    """Get KVN page by full path with children and breadcrumbs"""
    db = await get_db()
    
    # Try both with and without leading slash
    path_clean = path.lstrip("/")
    
    kvn = await db.kvn.find_one({"full_path": path_clean})
    if not kvn:
        kvn = await db.kvn.find_one({"full_path": f"/{path_clean}"})
    if not kvn:
        kvn = await db.kvn.find_one({"slug": path_clean})
    if not kvn:
        raise HTTPException(status_code=404, detail="KVN page not found")
    
    # Increment views
    await db.kvn.update_one({"_id": kvn["_id"]}, {"$inc": {"views": 1}})
    
    # Get children
    section_id = kvn.get("id")
    if section_id:
        children = await db.kvn.find(
            {"parent_id": section_id},
            {"_id": 0}
        ).sort("title", 1).to_list(100)
        kvn["children"] = children
    else:
        kvn["children"] = []
    
    # Get breadcrumbs
    breadcrumbs = []
    if kvn.get("parent_id"):
        current_parent_id = kvn["parent_id"]
        while current_parent_id:
            parent = await db.kvn.find_one({"id": current_parent_id})
            if parent:
                breadcrumbs.insert(0, {
                    "id": parent.get("id"),
                    "title": parent.get("name") or parent.get("title"),
                    "full_path": parent.get("full_path") or parent.get("slug")
                })
                current_parent_id = parent.get("parent_id")
            else:
                break
    
    kvn["breadcrumbs"] = breadcrumbs
    
    # Автоматически определяем соседние сезоны
    # Пытаемся найти соседние сезоны, даже если season_data отсутствует
    # (можем извлечь год и лигу из slug или full_path)
    prev_season_slug, next_season_slug = await find_adjacent_seasons(db, kvn)
    
    # Обновляем season_data с найденными соседними сезонами
    if kvn.get("season_data"):
        # Всегда обновляем, чтобы исправить неправильные значения и добавить отсутствующие
        if prev_season_slug:
            kvn["season_data"]["prev_season"] = prev_season_slug
        elif not kvn["season_data"].get("prev_season"):
            kvn["season_data"]["prev_season"] = ""
        
        if next_season_slug:
            kvn["season_data"]["next_season"] = next_season_slug
        elif not kvn["season_data"].get("next_season"):
            kvn["season_data"]["next_season"] = ""
    elif prev_season_slug or next_season_slug:
        # Если season_data отсутствует, но мы нашли соседние сезоны, создаем season_data
        kvn["season_data"] = {
            "prev_season": prev_season_slug or "",
            "next_season": next_season_slug or ""
        }
    
    # Загружаем данные команд из сезона
    team_data = {}
    if kvn.get("season_data"):
        season_data = kvn["season_data"]
        team_slugs = set()
        
        # Собираем slug из winners
        for winner in season_data.get("winners", []):
            if isinstance(winner, str):
                if winner:
                    team_slugs.add(winner)
            elif isinstance(winner, dict):
                slug = winner.get("slug")
                if slug:
                    team_slugs.add(slug)
        
        # Собираем slug из all_teams
        for team in season_data.get("all_teams", []):
            if isinstance(team, str):
                if team:
                    team_slugs.add(team)
            elif isinstance(team, dict):
                slug = team.get("slug")
                if slug:
                    team_slugs.add(slug)
        
        # Собираем slug из stages -> games -> teams
        for stage in season_data.get("stages", []):
            for game in stage.get("games", []):
                for team in game.get("teams", []):
                    if isinstance(team, dict):
                        slug = team.get("team_slug")
                        if slug:
                            team_slugs.add(slug)
        
        # Загружаем данные команд одним запросом
        if team_slugs:
            teams_cursor = db.teams.find(
                {"slug": {"$in": list(team_slugs)}},
                {
                    "slug": 1,
                    "name": 1,
                    "title": 1,
                    "facts": 1,
                    "updated_at": 1
                }
            )
            teams_list = await teams_cursor.to_list(length=len(team_slugs))
            
            # Формируем словарь по slug
            for team in teams_list:
                slug = team.get("slug")
                if slug:
                    team_name = team.get("name") or team.get("title") or ""
                    city = _get_city_from_facts(team.get("facts", {}))
                    team_data[slug] = {
                        "name": team_name,
                        "city": city,
                        "updated_at": team.get("updated_at")
                    }
    
    # Добавляем данные команд в ответ
    kvn["team_data"] = team_data
    kvn["team_data_version"] = datetime.now(timezone.utc).isoformat()
    
    # Remove MongoDB _id from response
    if "_id" in kvn:
        del kvn["_id"]
    
    return kvn


@router.get("/kvn/{parent_slug}/children", response_model=dict)
async def get_kvn_children(parent_slug: str):
    """Get children of a KVN page"""
    db = await get_db()
    parent = await db.kvn.find_one({"slug": parent_slug})
    if not parent:
        raise HTTPException(status_code=404, detail="Parent KVN page not found")
    
    parent_id = parent.get("id")
    children = await db.kvn.find(
        {"parent_id": parent_id},
        {"_id": 0}
    ).sort("title", 1).to_list(100)
    
    return {"items": children, "total": len(children), "parent": parent.get("title")}


@router.get("/kvn/{id_or_slug}", response_model=dict)
async def get_kvn(id_or_slug: str):
    """Get KVN page by ID or slug"""
    kvn = await get_by_id_or_slug("kvn", id_or_slug, "KVN page not found")
    
    # Разрешаем ссылки в модулях
    if kvn.get('modules'):
        kvn['modules'] = await LinkResolver.resolve_links_in_modules(kvn['modules'])
    
    return kvn


@router.get("/kvn-hierarchy", response_model=dict)
async def get_kvn_hierarchy(
    status: Optional[ContentStatus] = None
):
    """Get all KVN pages with hierarchy for admin panel"""
    db = await get_db()
    
    query = {}
    if status:
        query["status"] = status.value
    
    # We need _id to update records without 'id' field, so don't exclude it
    all_kvn = await db.kvn.find(query).sort([("level", 1), ("title", 1)]).to_list(1000)
    
    # Generate 'id' field for records that don't have it (for backward compatibility)

    records_to_update = []
    for k in all_kvn:
        if not k.get('id'):
            # Generate UUID and save it to database
            new_id = str(uuid.uuid4())
            k["id"] = new_id
            records_to_update.append((k["_id"], new_id))
    
    # Batch update records without 'id' field
    if records_to_update:
        from pymongo import UpdateMany
        bulk_ops = [UpdateMany({"_id": doc_id}, {"$set": {"id": new_id}}) for doc_id, new_id in records_to_update]
        if bulk_ops:
            await db.kvn.bulk_write(bulk_ops)
    
    # Remove _id from response (keep only 'id' field)
    for k in all_kvn:
        if "_id" in k:
            del k["_id"]
    
    kvn_by_id = {}
    for k in all_kvn:
        kvn_id = k.get('id')
        if kvn_id:  # Only add to dict if id exists
            kvn_by_id[kvn_id] = k
    
    root_kvn = []
    
    for kvn in all_kvn:
        kvn['children'] = []
        parent_id = kvn.get('parent_id')
        
        if not parent_id:
            root_kvn.append(kvn)
        else:
            parent = kvn_by_id.get(parent_id)
            if parent:
                if 'children' not in parent:
                    parent['children'] = []
                parent['children'].append(kvn)
    
    return {"items": root_kvn, "total": len(all_kvn)}


@router.put("/kvn/{id}", response_model=dict)
async def update_kvn(id: str, data: KVNUpdate):
    """Update KVN page"""
    try:
        db = await get_db()
    except Exception as e:
        logger.error(f"Error getting database connection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
    
    # For KVN, try to find by 'id' field (UUID) first, then by _id
    kvn = await db.kvn.find_one({"id": id})
    if not kvn:
        kvn = await db.kvn.find_one({"_id": id})
    
    if not kvn:
        raise HTTPException(status_code=404, detail="KVN page not found")
    
    # Get the actual _id for update operations
    kvn_id = kvn["_id"]
    
    update_data = {}
    
    if data.title is not None:
        update_data["title"] = data.title
    if data.slug is not None:
        await check_slug_unique("kvn", data.slug, exclude_id=id)
        update_data["slug"] = data.slug
    if data.name is not None:
        update_data["name"] = data.name
    if data.poster is not None:
        if isinstance(data.poster, dict) and not data.poster.get('url'):
            update_data["poster"] = None
        else:
            update_data["poster"] = data.poster.model_dump() if hasattr(data.poster, 'model_dump') else data.poster
    if data.description is not None:
        update_data["description"] = data.description
    if data.parent_id is not None:
        update_data["parent_id"] = data.parent_id
        if data.parent_id:
            # Find parent by 'id' field (UUID) first, then by _id
            parent = await db.kvn.find_one({"id": data.parent_id})
            if not parent:
                parent = await db.kvn.find_one({"_id": data.parent_id})
            if parent:
                parent_level = parent.get("level", 0)
                if parent_level >= 4:
                    raise HTTPException(status_code=400, detail="Maximum hierarchy level (4) reached")
                update_data["level"] = parent_level + 1
                parent_path = parent.get("full_path", parent.get("slug"))
                current_slug = data.slug or kvn.get("slug")
                update_data["full_path"] = f"{parent_path}/{current_slug}"
        else:
            current_slug = data.slug or kvn.get("slug")
            update_data["level"] = 0
            update_data["full_path"] = current_slug
    if data.facts is not None:
        update_data["facts"] = data.facts
    if getattr(data, "facts_order", None) is not None:
        update_data["facts_order"] = data.facts_order
    if data.social_links is not None:
        update_data["social_links"] = data.social_links.model_dump() if hasattr(data.social_links, 'model_dump') else data.social_links
    if data.modules is not None:
        update_data["modules"] = [
            m.model_dump() if hasattr(m, 'model_dump') else (m if isinstance(m, dict) else {})
            for m in data.modules
        ]
    if data.tags is not None:
        update_data["tags"] = data.tags
        await tag_service.sync_tags(data.tags)
    if data.seo is not None:
        update_data["seo"] = data.seo.model_dump() if hasattr(data.seo, 'model_dump') else data.seo
    if data.status is not None:
        update_data["status"] = data.status.value if hasattr(data.status, 'value') else data.status
    if data.team_ids is not None:
        update_data["team_ids"] = data.team_ids
    if data.person_ids is not None:
        update_data["person_ids"] = data.person_ids
    if data.related_kvn_ids is not None:
        update_data["related_kvn_ids"] = data.related_kvn_ids
    if data.jury_cards is not None:
        update_data["jury_cards"] = data.jury_cards
    if data.season_data is not None:
        # Валидируем и очищаем season_data перед сохранением
        # Убеждаемся, что все вложенные структуры сериализуемы
        try:

            from bson import ObjectId
            from datetime import datetime as dt, date
            
            # Преобразуем Pydantic модель в dict, если нужно
            season_data_dict = data.season_data
            if hasattr(season_data_dict, 'model_dump'):
                season_data_dict = season_data_dict.model_dump()
            elif hasattr(season_data_dict, 'dict'):
                season_data_dict = season_data_dict.dict()
            
            # Логируем наличие специальных символов в данных для диагностики
            try:
                season_data_str = json.dumps(season_data_dict, ensure_ascii=False)
                if '+' in season_data_str or '%2B' in season_data_str:
                    logger.info(f"Found '+' character in season_data, will handle properly")
            except:
                pass
            
            # Рекурсивно очищаем данные от несериализуемых объектов
            def clean_data(obj, depth=0, max_depth=15):
                if depth > max_depth:
                    logger.warning(f"Max depth reached in clean_data, converting to string")
                    return str(obj)
                
                # Обрабатываем специальные типы BSON и Python
                if isinstance(obj, ObjectId):
                    return str(obj)
                elif isinstance(obj, (dt, date)):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: clean_data(v, depth+1, max_depth) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_data(item, depth+1, max_depth) for item in obj]
                elif isinstance(obj, (str, int, float, bool, type(None))):
                    # Убеждаемся, что строки правильно обрабатываются
                    if isinstance(obj, str):
                        # Проверяем на наличие проблемных символов
                        if obj and ('+' in obj or '%' in obj):
                            logger.debug(f"Processing string with special characters: {obj[:50]}...")
                    return obj
                elif hasattr(obj, 'model_dump'):
                    # Pydantic модель
                    return clean_data(obj.model_dump(), depth+1, max_depth)
                elif hasattr(obj, '__dict__'):
                    # Объект с атрибутами - преобразуем в словарь
                    return clean_data(obj.__dict__, depth+1, max_depth)
                else:
                    # Преобразуем в строку если не сериализуемо
                    return str(obj)
            
            cleaned_data = clean_data(season_data_dict)
            
            # Автоматически добавляем league_slug, если его нет и есть родитель "Высшая лига КВН"
            if not cleaned_data.get("league_slug"):
                parent_id = kvn.get("parent_id")
                if parent_id:
                    # Находим родителя
                    parent = await db.kvn.find_one({"id": parent_id})
                    if not parent:
                        parent = await db.kvn.find_one({"_id": parent_id})
                    
                    if parent:
                        # Определяем league_slug из родителя
                        league_slug = get_league_slug_from_parent(parent)
                        
                        if league_slug:
                            cleaned_data["league_slug"] = league_slug
                            logger.info(f"Автоматически добавлен league_slug '{league_slug}' в season_data при обновлении")
            
            # Пробуем сериализовать для проверки
            try:
                json_str = json.dumps(cleaned_data, default=str, ensure_ascii=False)
                logger.info(f"Season data serialized successfully, size: {len(json_str)} bytes")
                # Если данные слишком большие - логируем предупреждение, но сохраняем
                if len(json_str) > 1000000:  # 1MB
                    logger.warning(f"Season data is large: {len(json_str)} bytes")
                update_data["season_data"] = cleaned_data
            except (TypeError, ValueError) as json_err:
                logger.error(f"JSON serialization error: {json_err}")
                logger.error(f"Problematic data type: {type(cleaned_data)}")
                # Пробуем более агрессивную очистку
                try:
                    # Конвертируем все в базовые типы
                    def force_serializable(obj):
                        if isinstance(obj, (str, int, float, bool, type(None))):
                            return obj
                        elif isinstance(obj, dict):
                            return {str(k): force_serializable(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [force_serializable(item) for item in obj]
                        else:
                            return str(obj)
                    cleaned_data = force_serializable(cleaned_data)
                    json_str = json.dumps(cleaned_data, ensure_ascii=False)
                    update_data["season_data"] = cleaned_data
                    logger.warning("Used force_serializable to fix JSON serialization")
                except Exception as e3:
                    logger.error(f"Even force_serializable failed: {e3}")
                    raise
        except Exception as e:
            logger.error(f"Error processing season_data: {e}", exc_info=True)
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Пробуем сохранить хотя бы структуру без проблемных данных
            try:
                # Упрощаем данные - убираем сложные вложенные структуры
                season_data_dict = data.season_data
                if hasattr(season_data_dict, 'model_dump'):
                    season_data_dict = season_data_dict.model_dump()
                elif hasattr(season_data_dict, 'dict'):
                    season_data_dict = season_data_dict.dict()
                simplified = json.loads(json.dumps(season_data_dict, default=str, ensure_ascii=False))
                update_data["season_data"] = simplified
                logger.warning("Used simplified season_data after serialization error")
            except Exception as e2:
                logger.error(f"Failed to simplify season_data: {e2}", exc_info=True)
                # В крайнем случае - не сохраняем season_data, но не падаем
                logger.error("Skipping season_data update due to serialization errors")
                # Не добавляем season_data в update_data
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Логируем размер данных для отладки
    try:

        update_data_size = len(json.dumps(update_data, default=str, ensure_ascii=False))
        logger.info(f"Updating KVN {id}, data size: {update_data_size} bytes")
        if 'season_data' in update_data:
            season_data_size = len(json.dumps(update_data['season_data'], default=str, ensure_ascii=False))
            logger.info(f"Season data size: {season_data_size} bytes")
    except Exception as e:
        logger.warning(f"Could not calculate data size: {e}")
    
    try:
        result = await db.kvn.update_one({"_id": kvn_id}, {"$set": update_data})
    except Exception as e:
        logger.error(f"Error updating KVN {id}: {e}", exc_info=True)
        # Логируем детали ошибки
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Проверяем, не связана ли ошибка с сериализацией
        if 'ObjectId' in str(e) or 'serialize' in str(e).lower() or 'bson' in str(e).lower():
            logger.error("Error appears to be related to BSON serialization")
            # Пробуем преобразовать ObjectId в строки
            try:
                def convert_objectid(obj):
                    if isinstance(obj, dict):
                        return {k: convert_objectid(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_objectid(item) for item in obj]
                    elif hasattr(obj, '__class__') and 'ObjectId' in str(type(obj)):
                        return str(obj)
                    return obj
                
                cleaned_update_data = convert_objectid(update_data)
                result = await db.kvn.update_one({"_id": kvn_id}, {"$set": cleaned_update_data})
                logger.info("Successfully updated after ObjectId conversion")
            except Exception as e2:
                logger.error(f"Error after ObjectId conversion: {e2}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Failed to update KVN after ObjectId conversion: {str(e2)}")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to update KVN: {str(e)}")
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="KVN page not found")
    
    # Update person links if provided (team_ids are already saved in update_data above)
    if data.person_ids is not None:
        # Use UUID for linking service
        kvn_uuid = kvn.get("id") or str(kvn_id)
        await linking_service.update_person_links("kvn", kvn_uuid, data.person_ids)
    # Note: team_ids are already saved in the document via update_data, no additional linking needed
    
    # Автоматически обновляем соседние сезоны, если изменился slug, year или league_slug
    should_update_adjacent = False
    old_slug = kvn.get("slug", "")
    new_slug = update_data.get("slug", old_slug)
    old_season_data = kvn.get("season_data", {})
    new_season_data = update_data.get("season_data", old_season_data)
    
    # Проверяем, изменился ли slug
    if old_slug != new_slug:
        should_update_adjacent = True
    
    # Проверяем, изменился ли year или league_slug в season_data
    if new_season_data:
        old_year = old_season_data.get("year", 0)
        new_year = new_season_data.get("year", 0)
        old_league_slug = old_season_data.get("league_slug", "")
        new_league_slug = new_season_data.get("league_slug", "")
        
        if old_year != new_year or old_league_slug != new_league_slug:
            should_update_adjacent = True
    
    if should_update_adjacent:
        # Сохраняем старые значения соседних сезонов
        old_prev_season = old_season_data.get("prev_season", "")
        old_next_season = old_season_data.get("next_season", "")
        
        # Получаем обновленный документ
        updated_doc = await db.kvn.find_one({"_id": kvn_id})
        if updated_doc:
            # Пересчитываем соседние сезоны для обновленного сезона
            prev_season_slug, next_season_slug = await find_adjacent_seasons(db, updated_doc)
            
            # Обновляем season_data с новыми соседними сезонами
            if updated_doc.get("season_data"):
                updated_doc["season_data"]["prev_season"] = prev_season_slug or ""
                updated_doc["season_data"]["next_season"] = next_season_slug or ""
            else:
                updated_doc["season_data"] = {
                    "prev_season": prev_season_slug or "",
                    "next_season": next_season_slug or ""
                }
            
            await db.kvn.update_one(
                {"_id": kvn_id},
                {"$set": {"season_data": updated_doc["season_data"]}}
            )
            
            # Пересчитываем соседние сезоны для предыдущего сезона (если он был)
            if old_prev_season:
                prev_season_doc = await db.kvn.find_one({"slug": old_prev_season})
                if prev_season_doc:
                    prev_prev_slug, prev_next_slug = await find_adjacent_seasons(db, prev_season_doc)
                    if prev_season_doc.get("season_data"):
                        prev_season_doc["season_data"]["prev_season"] = prev_prev_slug or ""
                        prev_season_doc["season_data"]["next_season"] = prev_next_slug or ""
                    else:
                        prev_season_doc["season_data"] = {
                            "prev_season": prev_prev_slug or "",
                            "next_season": prev_next_slug or ""
                        }
                    await db.kvn.update_one(
                        {"_id": prev_season_doc["_id"]},
                        {"$set": {"season_data": prev_season_doc["season_data"]}}
                    )
            
            # Пересчитываем соседние сезоны для следующего сезона (если он был)
            if old_next_season:
                next_season_doc = await db.kvn.find_one({"slug": old_next_season})
                if next_season_doc:
                    next_prev_slug, next_next_slug = await find_adjacent_seasons(db, next_season_doc)
                    if next_season_doc.get("season_data"):
                        next_season_doc["season_data"]["prev_season"] = next_prev_slug or ""
                        next_season_doc["season_data"]["next_season"] = next_next_slug or ""
                    else:
                        next_season_doc["season_data"] = {
                            "prev_season": next_prev_slug or "",
                            "next_season": next_next_slug or ""
                        }
                    await db.kvn.update_one(
                        {"_id": next_season_doc["_id"]},
                        {"$set": {"season_data": next_season_doc["season_data"]}}
                    )
            
            logger.info(f"Обновлены соседние сезоны для сезона {new_slug}")
            
            # Если slug изменился, нужно обновить все сезоны, которые ссылаются на старый slug
            if old_slug != new_slug and old_slug:
                # Ищем все сезоны, которые ссылаются на старый slug в prev_season или next_season
                seasons_to_update = await db.kvn.find({
                    "$or": [
                        {"season_data.prev_season": old_slug},
                        {"season_data.next_season": old_slug}
                    ]
                }).to_list(1000)
                
                # Обновляем найденные сезоны
                for season_to_update in seasons_to_update:
                    # Заменяем старый slug на новый в ссылках
                    if season_to_update.get("season_data"):
                        if season_to_update["season_data"].get("prev_season") == old_slug:
                            season_to_update["season_data"]["prev_season"] = new_slug
                        if season_to_update["season_data"].get("next_season") == old_slug:
                            season_to_update["season_data"]["next_season"] = new_slug
                        
                        # Пересчитываем соседние сезоны для этого сезона
                        prev_slug, next_slug = await find_adjacent_seasons(db, season_to_update)
                        season_to_update["season_data"]["prev_season"] = prev_slug or ""
                        season_to_update["season_data"]["next_season"] = next_slug or ""
                        
                        await db.kvn.update_one(
                            {"_id": season_to_update["_id"]},
                            {"$set": {"season_data": season_to_update["season_data"]}}
                        )
                
                if seasons_to_update:
                    logger.info(f"Обновлены {len(seasons_to_update)} сезонов, которые ссылались на старый slug {old_slug}")
    
    # Return updated document, converting ObjectIds to strings
    try:
        updated = await db.kvn.find_one({"_id": kvn_id}, {"_id": 0})
        if updated:
            updated = convert_objectids_to_strings(updated)
        return updated
    except Exception as e:
        logger.error(f"Error returning updated document for KVN {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving updated document: {str(e)}")


@router.delete("/kvn/{id}")
async def delete_kvn(id: str):
    """Delete KVN page"""
    db = await get_db()

    # For KVN, try to find by 'id' field (UUID) first, then by _id
    kvn = await db.kvn.find_one({"id": id})
    if not kvn:
        kvn = await db.kvn.find_one({"_id": id})
    
    if not kvn:
        raise HTTPException(status_code=404, detail="KVN page not found")

    # Get the actual _id for deletion
    kvn_id = kvn["_id"]
    kvn_uuid = kvn.get("id")  # UUID field

    if kvn.get("child_kvn_ids"):
        raise HTTPException(status_code=400, detail="Cannot delete KVN page with children. Delete children first.")

    # Update parent's child_kvn_ids if parent exists
    if kvn.get("parent_id"):
        parent_id = kvn["parent_id"]
        # Find parent by 'id' field (UUID) first, then by _id
        parent = await db.kvn.find_one({"id": parent_id})
        if not parent:
            parent = await db.kvn.find_one({"_id": parent_id})
        
        if parent:
            # Use the UUID for removing from child_kvn_ids
            child_id_to_remove = kvn_uuid if kvn_uuid else str(kvn_id)
            await db.kvn.update_one(
                {"_id": parent["_id"]},
                {"$pull": {"child_kvn_ids": child_id_to_remove}}
            )
    
    # Delete using the actual _id from the found document
    # Note: person_ids and team_ids are stored in the document itself,
    # so they will be deleted automatically when the document is deleted
    result = await db.kvn.delete_one({"_id": kvn_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="KVN page not found")
    
    return {"success": True}


