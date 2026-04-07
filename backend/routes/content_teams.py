"""Team routes — CRUD + bulk operations + KVN league results + scaffold."""
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal
from datetime import datetime, timezone
import re
import uuid
import logging

from models.base import ContentStatus, ContentType
from models.modules import ModuleType, PageModule
from models.content import Team, TeamCreate, TeamUpdate
from utils.database import get_db
from utils.slugify import generate_slug
from utils.team_matcher import normalize_team_name
from services.crud import (
    check_slug_unique, create_content, update_content,
    delete_content, get_by_id_or_slug,
    check_primary_tag_duplicate,
)
from services.tags import tag_service
from services.link_resolver import LinkResolver
from routes.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["teams"])


# ---------------------------------------------------------------------------
#  Team-specific slug generation
# ---------------------------------------------------------------------------

async def generate_unique_team_slug(base_slug: str) -> str:
    """
    Generate unique slug for teams using '-2', '-3', ... suffixes (more URL-friendly).
    """
    db = await get_db()
    collection = db.teams

    slug = base_slug
    existing = await collection.find_one({"slug": slug})
    if not existing:
        return slug

    counter = 2
    while True:
        slug = f"{base_slug}-{counter}"
        existing = await collection.find_one({"slug": slug})
        if not existing:
            return slug
        counter += 1
        if counter > 1000:  # Safety limit
            raise HTTPException(status_code=500, detail="Could not generate unique team slug")


# ---------------------------------------------------------------------------
#  Bulk operation models
# ---------------------------------------------------------------------------

class BulkTeamCheckItem(BaseModel):
    raw_line: str = ""
    name: str = ""
    city: str | None = None


class BulkTeamCheckRequest(BaseModel):
    items: List[BulkTeamCheckItem] = Field(default_factory=list)


class BulkTeamCheckResult(BaseModel):
    index: int
    status: Literal["found", "not_found", "invalid"]
    name: str = ""
    city: str | None = None
    team_id: str | None = None
    team_slug: str | None = None
    team_display_name: str | None = None


class BulkTeamCreateRow(BaseModel):
    action: Literal["create", "skip", "link_existing"]
    name: str | None = None
    city: str | None = None
    existing_team_id: str | None = None
    confirmed_skip: bool = False


class BulkTeamCreateRequest(BaseModel):
    rows: List[BulkTeamCreateRow] = Field(default_factory=list)


class RestoreTeamLogosRequest(BaseModel):
    """Request model for bulk logo restoration"""
    dry_run: bool = Field(default=True, description="If true, only report what would be changed")
    only_if_placeholder: bool = Field(default=True, description="Only restore if logo is missing or placeholder")
    team_type: Optional[str] = Field(default=None, description="Filter by team_type (e.g. 'kvn'). If None, restore all teams")


# ---------------------------------------------------------------------------
#  Team helper functions
# ---------------------------------------------------------------------------

def _team_placeholder_logo() -> dict:
    """
    Default placeholder logo used when a team has no logo yet.
    Must exist in frontend static/media.
    """
    url = "/media/imported/images/pattern-1.jpeg"
    return {"url": url, "alt": "", "caption": "", "thumbnail": url}


def _is_placeholder_logo(logo: any) -> bool:
    """
    Check if logo is a placeholder pattern image.
    """
    if not logo:
        return True
    if isinstance(logo, dict):
        url = logo.get("url") or logo.get("thumbnail") or ""
        return bool(url and "/media/imported/images/pattern-" in url)
    if isinstance(logo, str):
        return "/media/imported/images/pattern-" in logo
    return False


def _normalize_to_mediafile(value: any) -> Optional[dict]:
    """
    Convert string or dict to MediaFile format.
    Returns None if value is empty/invalid.
    """
    if not value:
        return None
    
    if isinstance(value, dict):
        # Already a dict - check if it has url/thumbnail
        url = value.get("url") or value.get("thumbnail") or ""
        if url and url.strip():
            return {
                "url": url,
                "alt": value.get("alt", ""),
                "caption": value.get("caption", ""),
                "thumbnail": value.get("thumbnail") or url
            }
        return None
    
    if isinstance(value, str) and value.strip():
        # String URL - convert to MediaFile
        url = value.strip()
        # Ensure absolute path starts with /
        if not url.startswith("/") and not url.startswith("http"):
            url = "/" + url
        return {
            "url": url,
            "alt": "",
            "caption": "",
            "thumbnail": url
        }
    
    return None


def _pick_team_logo(doc: dict) -> dict:
    """
    Smart logo picker: tries logo field first, then falls back to legacy image/poster fields.
    Returns MediaFile dict or placeholder if nothing found.
    
    Priority:
    1. logo (if valid and not placeholder)
    2. image (legacy field from import)
    3. poster (legacy field from import)
    4. placeholder
    """
    # Check existing logo first
    logo = doc.get("logo")
    if logo and not _is_placeholder_logo(logo):
        # Logo exists and is not placeholder - normalize it
        normalized = _normalize_to_mediafile(logo)
        if normalized:
            return normalized
    
    # Try legacy image field
    image = doc.get("image")
    if image:
        normalized = _normalize_to_mediafile(image)
        if normalized:
            return normalized
    
    # Try legacy poster field
    poster = doc.get("poster")
    if poster:
        normalized = _normalize_to_mediafile(poster)
        if normalized:
            return normalized
    
    # Fallback to placeholder
    return _team_placeholder_logo()


def _is_empty_text_block(m: dict) -> bool:
    if not isinstance(m, dict) or m.get("type") != "text_block":
        return False
    data = m.get("data") or {}
    content = data.get("content")
    if content is None:
        content = ""
    if not isinstance(content, str):
        return False
    return content.strip() == ""


def _is_empty_timeline(m: dict) -> bool:
    if not isinstance(m, dict) or m.get("type") != "timeline":
        return False
    data = m.get("data") or {}
    # support both events/items naming
    events = data.get("events")
    items = data.get("items")
    if isinstance(events, list) and len(events) > 0:
        return False
    if isinstance(items, list) and len(items) > 0:
        return False
    # If there are any other meaningful keys besides title, consider it non-empty
    meaningful = {k: v for k, v in data.items() if k not in ["title"] and v not in [None, "", [], {}]}
    return len(meaningful) == 0


def _prune_empty_modules(modules: list[dict]) -> list[dict]:
    """
    Remove empty text blocks and empty timelines.
    """
    pruned = []
    for m in modules or []:
        if not isinstance(m, dict):
            continue
        if _is_empty_text_block(m):
            continue
        if _is_empty_timeline(m):
            continue
        pruned.append(m)
    # Keep stable orders
    for i, m in enumerate(pruned):
        m["order"] = i
    return pruned


def _build_team_intro_html(name: str, city: Optional[str]) -> str:
    city_part = f" ({city})" if city else ""
    # Keep exact requested pattern: "Название команды (город) - ... "
    return f"<p>{name}{city_part} - ...</p>"


def _stage_code(stage_name: str) -> str:
    """
    Convert stage name like '1/8 финала' -> '1/8', '1/4 финала' -> '1/4', '1/2 финала' -> '1/2', 'финал' -> 'Финал'.
    """
    if not stage_name:
        return ""
    s = stage_name.strip().lower()
    m = re.search(r"(\d+)\s*/\s*(\d+)", s)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    if "финал" in s:
        if "полу" in s:
            return "1/2"
        return "Финал"
    return stage_name.strip()


def _league_code_from_slug(league_slug: str) -> str:
    """Convert league_slug to short code (e.g., 'vl-kvn' -> 'ВЛ', 'ml-kvn' -> 'МЛ', 'premier-liga' -> 'ПЛ')"""
    if league_slug == "vl-kvn":
        return "ВЛ"
    if league_slug == "ml-kvn":
        return "МЛ"
    if league_slug == "premier-liga":
        return "ПЛ"
    if league_slug == "1l-kvn":
        return "1Л"
    # Add more leagues later
    return league_slug or ""


async def _get_team_league_results(team_slug: str, league_slug: str, db) -> List[Dict]:
    """
    Collect all results for a team from all seasons of a specific league.
    Returns list of result dicts with: year, league, stage, stage_name, result, place, out_of, date, game_name
    """
    if not team_slug or not league_slug:
        return []
    
    # Query all seasons of the specified league
    # Ищем по league_slug в season_data ИЛИ по full_path (на случай неправильного league_slug)
    # full_path имеет формат: kvn/premier-liga/pl-2006, kvn/ml-kvn/ml-2006 и т.д.
    path_pattern = f"kvn/{league_slug}/"
    
    # Ищем сезоны двумя способами:
    # 1. По season_data.league_slug
    # 2. По full_path (на случай если league_slug неправильный)
    seasons_query = {
        "$or": [
            {"season_data.league_slug": league_slug},
            {"full_path": {"$regex": f"^{re.escape(path_pattern)}"}}
        ]
    }
    
    seasons = await db.kvn.find(seasons_query).to_list(1000)
    
    results = []
    
    for season in seasons:
        season_data = season.get("season_data") or {}
        year = season_data.get("year")
        if not year:
            # Try to extract from slug
            slug = season.get("slug", "")
            m = re.search(r"(19|20)\d{2}", slug)
            if m:
                year = int(m.group(0))
            else:
                continue
        else:
            # Convert to int in case year is stored as string in MongoDB
            year = int(year)
        
        # Определяем фактическую лигу из full_path (источник истины)
        # full_path имеет формат: kvn/premier-liga/pl-2006, kvn/ml-kvn/ml-2006 и т.д.
        actual_league_slug = league_slug  # По умолчанию используем запрошенную лигу
        full_path = season.get("full_path", "")
        if full_path:
            clean_path = full_path.lstrip("/")
            path_parts = clean_path.split("/")
            if len(path_parts) >= 2 and path_parts[0] == "kvn":
                path_league = path_parts[1]
                valid_leagues = ["vl-kvn", "premier-liga", "1l-kvn", "ml-kvn", "vul"]
                if path_league in valid_leagues:
                    actual_league_slug = path_league
        
        # Если фактическая лига не совпадает с запрошенной, пропускаем сезон
        if actual_league_slug != league_slug:
            continue
        
        # Validate league_slug against year to prevent historical inaccuracies
        # Международная лига (ml-kvn) была создана в 2014 году
        if actual_league_slug == "ml-kvn" and year < 2014:
            # Skip seasons before 2014 that incorrectly have ml-kvn
            continue
        
        league = _league_code_from_slug(actual_league_slug)
        
        stages = season_data.get("stages") or []
        for stage in stages:
            stage_name = stage.get("name") or ""
            stage_code = _stage_code(stage_name)
            games = stage.get("games") or []
            
            for game in games:
                teams = game.get("teams") or []
                # Filter valid teams
                valid_teams = [t for t in teams if isinstance(t, dict) and t.get("team_slug")]
                n = len(valid_teams)
                if n <= 0:
                    continue
                
                # Find our team in this game
                our_team = None
                for t in valid_teams:
                    if t.get("team_slug") == team_slug:
                        our_team = t
                        break
                
                if not our_team:
                    continue
                
                place = our_team.get("place")
                is_winner = our_team.get("is_winner", False)
                our_total = our_team.get("total")
                passed = our_team.get("passed")
                
                # Special handling for champions: if is_winner=True, treat as place=1
                # This handles cases like 1992 final where both teams are champions (place=0, is_winner=True)
                if is_winner and (place is None or place == 0):
                    place = 1
                
                # Handle ties: if multiple teams have the same total score, they should all have place=1
                # Example: 1994 semifinal where ЕРМИ and Ворошиловские стрелки both have total=22.6
                if our_total is not None and place is not None:
                    # Find all teams with the same total
                    teams_with_same_total = [t for t in valid_teams if t.get("total") == our_total]
                    if len(teams_with_same_total) > 1:
                        # All teams with same total should be considered tied for first place
                        # Check if any of them has place=1
                        has_first_place = any(t.get("place") == 1 for t in teams_with_same_total)
                        if has_first_place:
                            place = 1
                
                # Determine result text
                # If we have a valid place (> 0), show "X из Y"
                # If place is 0 or None but we have passed status, show "Прошел" or "Не прошел"
                # If neither, skip this entry
                if place is not None and place > 0:
                    result_text = f"{place} из {n}"
                elif passed is not None:
                    # passed can be True or False
                    result_text = "Прошел" if passed else "Не прошел"
                else:
                    # No valid place and no passed status - skip this entry
                    continue
                
                results.append({
                    "year": year,
                    "league": league,
                    "stage": stage_code,
                    "stage_name": stage_name,
                    "result": result_text,
                    "place": place,
                    "out_of": n,
                    "date": game.get("date") or "",
                    "game_name": game.get("name") or "",
                })
    
    # Sort: first by year (ascending), then by stage order within year
    # Stage order: 1/8 < 1/4 < 1/2 < Финал
    def _stage_order(stage: str) -> int:
        """Convert stage to numeric order for sorting"""
        if not stage:
            return 99
        stage_lower = stage.lower()
        # Check exact matches first
        if stage == "1/8" or "1/8" in stage:
            return 1
        if stage == "1/4" or "1/4" in stage:
            return 2
        if stage == "1/2" or "полу" in stage_lower:
            return 3
        if "финал" in stage_lower and "полу" not in stage_lower:
            return 4
        return 99  # Unknown stages go last
    
    def sort_key(r):
        year = r.get("year", 0)
        stage = r.get("stage") or ""
        return (year, _stage_order(stage))
    
    results.sort(key=sort_key)
    return results


async def _get_team_vl_results(team_slug: str, db) -> List[Dict]:
    """
    Collect all VL (Высшая лига) results for a team from all seasons.
    Returns list of result dicts with: year, league, stage, stage_name, result, place, out_of, date, game_name
    """
    return await _get_team_league_results(team_slug, "vl-kvn", db)


async def _get_team_all_results(team_slug: str, db) -> List[Dict]:
    """
    Collect all results for a team from all supported leagues (VL, ПЛ, МЛ, etc.).
    Returns combined list of result dicts sorted by year and stage.
    """
    if not team_slug:
        return []
    
    # Get results from all supported leagues
    all_results = []
    
    # Высшая лига
    vl_results = await _get_team_league_results(team_slug, "vl-kvn", db)
    all_results.extend(vl_results)
    
    # Премьер-лига
    pl_results = await _get_team_league_results(team_slug, "premier-liga", db)
    all_results.extend(pl_results)
    
    # Международная лига
    ml_results = await _get_team_league_results(team_slug, "ml-kvn", db)
    all_results.extend(ml_results)
    
    # Add more leagues here in the future
    
    # Sort: first by year (ascending), then by stage order within year
    def _stage_order(stage: str) -> int:
        """Convert stage to numeric order for sorting"""
        if not stage:
            return 99
        stage_lower = stage.lower()
        # Check exact matches first
        if stage == "1/8" or "1/8" in stage:
            return 1
        if stage == "1/4" or "1/4" in stage:
            return 2
        if stage == "1/2" or "полу" in stage_lower:
            return 3
        if "финал" in stage_lower and "полу" not in stage_lower:
            return 4
        return 99  # Unknown stages go last
    
    def sort_key(r):
        year = r.get("year", 0)
        stage = r.get("stage") or ""
        return (year, _stage_order(stage))
    
    all_results.sort(key=sort_key)
    return all_results


def _build_team_games_table_html(results: List[Dict]) -> str:
    """
    Build HTML table for team games results.
    Format matches the screenshot: legend at top, then table with columns: Год, Лига, Стадия, Результат
    """
    if not results:
        return ""
    
    # Build legend for all leagues used
    leagues_used = sorted(set(r.get("league") for r in results if r.get("league")))
    legend_parts = []
    if "ВЛ" in leagues_used:
        legend_parts.append("ВЛ – Высшая лига")
    if "МЛ" in leagues_used:
        legend_parts.append("МЛ – Международная лига")
    # Add more leagues later: ГК – Голосящий КиВиН, etc.
    
    legend_html = ""
    if legend_parts:
        legend_html = f'<div style="margin-bottom: 1rem;"><strong>Обозначения:</strong> {", ".join(legend_parts)}.</div>\n'
    
    # Build table
    table_rows = []
    for r in results:
        year = r.get("year", "")
        league = r.get("league", "")
        stage = r.get("stage", "")
        result = r.get("result", "")
        
        table_rows.append(f"    <tr>\n      <td>{year}</td>\n      <td>{league}</td>\n      <td>{stage}</td>\n      <td>{result}</td>\n    </tr>")
    
    table_html = f"""<div style="text-align: justify;">{legend_html}<table style="width: 100%; border-collapse: collapse;">
  <thead>
    <tr>
      <th style="text-align: left; padding: 0.5rem; border-bottom: 1px solid #ddd;"><strong>Год</strong></th>
      <th style="text-align: left; padding: 0.5rem; border-bottom: 1px solid #ddd;"><strong>Лига</strong></th>
      <th style="text-align: left; padding: 0.5rem; border-bottom: 1px solid #ddd;"><strong>Стадия</strong></th>
      <th style="text-align: left; padding: 0.5rem; border-bottom: 1px solid #ddd;"><strong>Результат</strong></th>
    </tr>
  </thead>
  <tbody>
{chr(10).join(table_rows)}
  </tbody>
</table></div>"""
    
    return table_html


async def _update_team_games_module(team_slug: str, modules: List[dict], db) -> List[dict]:
    """
    Update or create "Список игр команды" module with auto-generated table from all supported leagues (VL, ML, etc.).
    Only for KVN teams (team_type='kvn').
    REMOVES ALL existing "Список игр команды" modules (manual or auto) and creates a single auto-generated one.
    Returns updated modules list.
    """
    if not team_slug:
        return modules
    
    # Get team to check team_type
    team = await db.teams.find_one({"slug": team_slug}, {"team_type": 1})
    if not team or team.get("team_type") != "kvn":
        return modules
    
    # Get results from all supported leagues (VL, ML, etc.)
    results = await _get_team_all_results(team_slug, db)
    
    # Remove ALL existing "Список игр команды" modules (manual or auto) to prevent duplicates
    # We identify them by:
    # 1. Title matches "Список игр команды" (exact or partial)
    # 2. OR content contains the games table structure (table with headers "Год", "Лига", "Стадия", "Результат")
    target_title = "Список игр команды"
    updated_modules = []
    removed_count = 0
    removed_ids = []
    
    def is_games_table_module(m: dict) -> bool:
        """Check if module is a games table (by title or content structure)"""
        if not isinstance(m, dict) or m.get("type") != "text_block":
            return False
        
        data = m.get("data") or {}
        content = (data.get("content") or "").strip()
        title = (data.get("title") or m.get("title") or "").strip()
        
        # Check by title
        if title and (title == target_title or 
                     title.lower() == target_title.lower() or
                     title.lower().startswith(target_title.lower())):
            return True
        
        # Check by content structure - look for games table headers
        # Manual tables have: <th>Год</th>, <th>Лига</th>, <th>Стадия</th>, <th>Результат</th>
        if content and ("<th" in content.lower() or "<table" in content.lower()):
            # Check if it contains all the required headers
            content_lower = content.lower()
            has_year = "год" in content_lower
            has_league = "лига" in content_lower
            has_stage = "стадия" in content_lower
            has_result = "результат" in content_lower
            
            # If it has table structure with these headers, it's likely a games table
            if has_year and has_league and has_stage and has_result:
                return True
        
        return False
    
    for m in modules:
        if is_games_table_module(m):
            removed_count += 1
            removed_ids.append(m.get("id", "unknown"))
            title = ((m.get("data") or {}).get("title") or m.get("title") or "").strip()
            logger.debug(f"Removing games module {m.get('id')} (title: '{title}') for team {team_slug}")
            continue  # Remove this module
        
        updated_modules.append(m)
    
    # Log if we removed multiple modules (indicates duplicate issue)
    if removed_count > 0:
        logger.info(f"Removed {removed_count} 'Список игр команды' module(s) for team {team_slug} (IDs: {removed_ids})")
    
    # Always create a fresh auto-generated module (even if empty)

    new_module = {
        "id": str(uuid.uuid4()),
        "type": "text_block",
        "order": len(updated_modules),  # Will be normalized later
        "title": "",
        "visible": bool(results),  # Hide if no results
        "data": {
            "title": target_title,
            "content": _build_team_games_table_html(results) if results else "",
            "auto_generated": True,  # Mark as auto-generated
            "source": "kvn-leagues"  # Updated to reflect multiple leagues
        }
    }
    updated_modules.append(new_module)
    
    return updated_modules


async def _update_team_vl_results_module(team_slug: str, modules: List[dict], db) -> List[dict]:
    """
    Create/update a dedicated module with VL results table.
    We keep "Список игр команды" for manual editing; this module is auto-generated.
    """
    if not team_slug:
        return modules

    team = await db.teams.find_one({"slug": team_slug}, {"team_type": 1})
    if not team or team.get("team_type") != "kvn":
        return modules

    results = await _get_team_vl_results(team_slug, db)

    target_title = "Результаты в Высшей лиге"
    updated_modules = []
    found = False

    for m in modules or []:
        if not isinstance(m, dict):
            updated_modules.append(m)
            continue
        m_type = m.get("type")
        data = m.get("data") or {}
        title = (data.get("title") or "").strip()

        if m_type == "text_block" and title == target_title:
            m2 = dict(m)
            d2 = dict(data)
            d2["auto_generated"] = True
            d2["source"] = "vl-kvn"
            if results:
                d2["content"] = _build_team_games_table_html(results)
                m2["visible"] = True
            else:
                d2["content"] = ""
                m2["visible"] = False
            m2["data"] = d2
            updated_modules.append(m2)
            found = True
        else:
            updated_modules.append(m)

    if not found:
        import uuid
        updated_modules.append(
            {
                "id": str(uuid.uuid4()),
                "type": "text_block",
                "order": len(updated_modules),
                "title": "",
                "visible": bool(results),
                "data": {
                    "title": target_title,
                    "content": _build_team_games_table_html(results) if results else "",
                    "auto_generated": True,
                    "source": "vl-kvn",
                },
            }
        )

    return updated_modules


def _clone_modules_with_new_ids(modules: list) -> list:
    """
    Clone modules and assign fresh UUIDs to each module.id to avoid accidental reuse/collisions.
    """
    import uuid
    cloned = []
    for m in modules or []:
        if not isinstance(m, dict):
            continue
        m2 = dict(m)
        m2["id"] = str(uuid.uuid4())
        cloned.append(m2)
    return cloned


def _ensure_team_scaffold_fields(doc: dict, *, name: str, city: Optional[str]) -> tuple[dict, list[str], list[dict]]:
    """
    Ensure KVN team has baseline facts + modules scaffold.
    Returns: (facts, facts_order, modules_as_dicts)
    """
    facts = dict(doc.get("facts") or {})

    # City: store as human-readable key (requested)
    if city and not facts.get("Город"):
        facts["Город"] = city
    # Backward-compat: migrate old 'city' key to 'Город'
    if facts.get("city") and not facts.get("Город"):
        facts["Город"] = facts.get("city")
    if "city" in facts:
        del facts["city"]

    # Required visible facts with placeholders
    if "Год основания" not in facts or not str(facts.get("Год основания") or "").strip():
        facts["Год основания"] = "—"
    if "Капитан" not in facts or not str(facts.get("Капитан") or "").strip():
        facts["Капитан"] = "—"

    # Facts order: prefer explicit order if present, otherwise seed with desired keys
    current_order = list(doc.get("facts_order") or [])
    desired_prefix = ["Город", "Год основания", "Капитан"]
    ordered = [k for k in desired_prefix if k in facts]
    # Keep any existing order items that still exist and aren't already included
    for k in current_order:
        if k in facts and k not in ordered:
            ordered.append(k)
    # Append any remaining keys
    for k in facts.keys():
        if k not in ordered:
            ordered.append(k)

    # Modules scaffold
    modules = list(doc.get("modules") or [])
    existing_types = {m.get("type") for m in modules if isinstance(m, dict)}
    
    # Build signature set for duplicate detection (type + title for text_block/timeline)
    def _module_sig(m: dict) -> tuple:
        m_type = (m.get("type") or "").strip()
        data = m.get("data") or {}
        if m_type == "text_block":
            title = (data.get("title") or "").strip()
            return (m_type, title)
        if m_type == "timeline":
            title = (data.get("title") or m.get("title") or "").strip()
            return (m_type, title)
        return (m_type, "")

    existing_signatures = {_module_sig(m) for m in modules if isinstance(m, dict)}

    def add_module(mod: PageModule):
        modules.append(mod.model_dump())

    # Sidebar/system modules
    if ModuleType.POSTER_PHOTO.value not in existing_types:
        add_module(PageModule(type=ModuleType.POSTER_PHOTO, order=0, visible=True, data={"size": "medium", "shape": "rounded"}))
    if ModuleType.FACTS_TABLE.value not in existing_types:
        add_module(PageModule(type=ModuleType.FACTS_TABLE, order=1, visible=True, data={"title": "Информация", "style": "table"}))
    if ModuleType.RATING_WIDGET.value not in existing_types:
        add_module(PageModule(type=ModuleType.RATING_WIDGET, order=2, visible=True, data={"style": "stars", "scale": 5}))
    if ModuleType.TAGS_CLOUD.value not in existing_types:
        add_module(PageModule(type=ModuleType.TAGS_CLOUD, order=3, visible=True, data={"style": "badges", "max_tags": 0}))
    if ModuleType.SOCIAL_LINKS.value not in existing_types:
        add_module(PageModule(type=ModuleType.SOCIAL_LINKS, order=4, visible=True, data={"title": "Ссылки"}))

    # Content modules
    # Intro paragraph text block (no title)
    has_intro = any(
        isinstance(m, dict)
        and m.get("type") == ModuleType.TEXT_BLOCK.value
        and not (m.get("data") or {}).get("title")
        for m in modules
    )
    if not has_intro:
        add_module(PageModule(type=ModuleType.TEXT_BLOCK, order=10, visible=True, data={"content": _build_team_intro_html(name, city)}))

    # Timeline: check by signature (type + title) not just type
    timeline_sig = ("timeline", "Хронология")
    if timeline_sig not in existing_signatures:
        # Frontend supports data.events or data.items; we use events for admin UX.
        add_module(PageModule(type=ModuleType.TIMELINE, order=11, visible=True, data={"title": "Хронология", "events": []}))

    # Required empty text sections - check by signature (type + title)
    # NOTE: "Список игр команды" is NOT added here - it's handled by _update_team_games_module
    # to prevent duplicates and ensure it's always auto-generated for KVN teams
    required_sections = ["Состав команды", "История команды"]
    base_order = 12
    for idx, title in enumerate(required_sections):
        text_block_sig = ("text_block", title)
        if text_block_sig not in existing_signatures:
            add_module(PageModule(type=ModuleType.TEXT_BLOCK, order=base_order + idx, visible=True, data={"title": title, "content": ""}))

    # Normalize orders to be stable
    modules_sorted = sorted(
        [m for m in modules if isinstance(m, dict)],
        key=lambda x: (x.get("order") or 0)
    )
    for i, m in enumerate(modules_sorted):
        m["order"] = i

    return facts, ordered, modules_sorted

# ---------------------------------------------------------------------------
#  Bulk operations routes
# ---------------------------------------------------------------------------

@router.post("/teams/bulk-check", response_model=dict)
async def bulk_check_teams(data: BulkTeamCheckRequest):
    """
    Bulk check team existence by normalized name (including aliases).
    Intended for admin bulk import UI.
    """
    db = await get_db()

    # Load only fields needed for matching
    cursor = db.teams.find({}, {"_id": 1, "slug": 1, "name": 1, "title": 1, "aliases": 1})
    existing_teams = await cursor.to_list(length=None)

    # Build lookup: normalized_name -> team doc (first wins)
    by_norm: Dict[str, Dict] = {}
    for team in existing_teams:
        base_name = (team.get("name") or team.get("title") or "").strip()
        if base_name:
            key = normalize_team_name(base_name)
            if key and key not in by_norm:
                by_norm[key] = team
        for alias in team.get("aliases") or []:
            if not isinstance(alias, str):
                continue
            key = normalize_team_name(alias.strip())
            if key and key not in by_norm:
                by_norm[key] = team

    results: List[dict] = []
    for idx, item in enumerate(data.items):
        name = (item.name or "").strip()
        city = (item.city or None)
        if city is not None:
            city = city.strip() or None

        if not name:
            results.append(BulkTeamCheckResult(index=idx, status="invalid", name="", city=city).model_dump())
            continue

        key = normalize_team_name(name)
        matched = by_norm.get(key)
        if matched:
            display_name = (matched.get("name") or matched.get("title") or "").strip() or None
            results.append(
                BulkTeamCheckResult(
                    index=idx,
                    status="found",
                    name=name,
                    city=city,
                    team_id=str(matched.get("_id")),
                    team_slug=matched.get("slug"),
                    team_display_name=display_name,
                ).model_dump()
            )
        else:
            results.append(BulkTeamCheckResult(index=idx, status="not_found", name=name, city=city).model_dump())

    return {"items": results}


@router.post("/teams/bulk-create", response_model=dict)
async def bulk_create_teams(data: BulkTeamCreateRequest):
    """
    Bulk-create missing teams (and validate user decisions for found/link_existing rows).
    """
    db = await get_db()

    created: List[dict] = []
    skipped: List[dict] = []

    for idx, row in enumerate(data.rows):
        if row.action == "skip":
            skipped.append({"index": idx, "reason": "skipped_by_user"})
            continue

        if row.action == "link_existing":
            if not row.existing_team_id:
                raise HTTPException(status_code=400, detail=f"Row {idx}: existing_team_id is required for link_existing")
            if not row.confirmed_skip:
                raise HTTPException(status_code=400, detail=f"Row {idx}: confirmation is required to skip existing team")
            skipped.append({"index": idx, "reason": "linked_existing", "existing_team_id": row.existing_team_id})
            continue

        # create
        name = (row.name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail=f"Row {idx}: name is required for create")

        facts = {}
        city = (row.city or "").strip()
        if city:
            facts["Город"] = city

        base_slug = generate_slug(name)
        if not base_slug:
            base_slug = "team"
        slug = await generate_unique_team_slug(base_slug)

        title = name
        # Baseline scaffold (facts + modules)
        scaffold_facts, scaffold_order, scaffold_modules = _ensure_team_scaffold_fields(
            {"facts": facts, "facts_order": list(facts.keys()), "modules": []},
            name=name,
            city=city or None
        )

        team = Team(
            title=title,
            slug=slug,
            name=name,
            team_type="kvn",
            logo=_team_placeholder_logo(),
            facts=scaffold_facts,
            facts_order=scaffold_order,
            social_links={},
            primary_tag=name,
            modules=scaffold_modules,
            tags=[],
            seo={"meta_title": title, "meta_description": "", "keywords": []},
            status=ContentStatus.DRAFT,
        )

        # Use universal create handler (syncs tags/primary_tag, timestamps, etc.)
        result = await create_content("teams", team, [])
        # Mark as intentionally empty (bulk import pages are allowed to have empty placeholder modules)
        await db.teams.update_one({"_id": result.get("id")}, {"$set": {"allow_empty_modules": True}})
        created.append({"index": idx, "id": result.get("id"), "slug": result.get("slug"), "name": name})

    return {"created": created, "skipped": skipped}


@router.post("/teams/restore-logos", response_model=dict)
async def restore_team_logos(data: RestoreTeamLogosRequest, request: Request):
    """
    Bulk restore team logos from legacy image/poster fields.
    Only affects teams where logo is missing or is a placeholder pattern.
    """
    user = await get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    
    db = await get_db()
    
    # Build query: teams with missing/placeholder logos
    query = {}
    if data.team_type:
        query["team_type"] = data.team_type
    
    # Find teams that need logo restoration
    cursor = db.teams.find(query)
    matched = 0
    modified = 0
    restored_from_image = 0
    restored_from_poster = 0
    skipped_no_source = 0
    
    async for team in cursor:
        current_logo = team.get("logo")
        
        # Check if we should restore this team's logo
        should_restore = False
        if data.only_if_placeholder:
            # Only restore if logo is missing or is placeholder
            if not current_logo or _is_placeholder_logo(current_logo):
                should_restore = True
        else:
            # Restore all teams (even if they have a logo, try to improve from legacy fields)
            should_restore = True
        
        if not should_restore:
            continue
        
        matched += 1
        
        # Try to restore from legacy fields
        picked_logo = _pick_team_logo(team)
        
        # Check if we actually found a source (not just placeholder)
        if _is_placeholder_logo(picked_logo):
            skipped_no_source += 1
            continue
        
        # Determine source for reporting by tracing through _pick_team_logo's priority logic
        # This ensures we count the actual source used, not just what fields exist
        source_determined = False
        
        # Check if picked_logo came from existing logo (priority 1)
        if current_logo and not _is_placeholder_logo(current_logo):
            normalized_current = _normalize_to_mediafile(current_logo)
            if normalized_current and normalized_current.get("url") == picked_logo.get("url"):
                # Logo came from existing logo, not from image/poster - don't count as restored
                source_determined = True
        
        # If not from existing logo, check if it came from image (priority 2)
        if not source_determined:
            image = team.get("image")
            if image:
                normalized_image = _normalize_to_mediafile(image)
                if normalized_image and normalized_image.get("url") == picked_logo.get("url"):
                    restored_from_image += 1
                    source_determined = True
        
        # If not from image, check if it came from poster (priority 3)
        if not source_determined:
            poster = team.get("poster")
            if poster:
                normalized_poster = _normalize_to_mediafile(poster)
                if normalized_poster and normalized_poster.get("url") == picked_logo.get("url"):
                    restored_from_poster += 1
                    source_determined = True
        
        if data.dry_run:
            continue
        
        # Update logo
        changes = {
            "logo": picked_logo,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        res = await db.teams.update_one({"_id": team["_id"]}, {"$set": changes})
        if res.modified_count:
            modified += 1
    
    return {
        "matched": matched,
        "modified": modified,
        "restored_from_image": restored_from_image,
        "restored_from_poster": restored_from_poster,
        "skipped_no_source": skipped_no_source,
        "dry_run": data.dry_run,
        "team_type": data.team_type
    }

# ---------------------------------------------------------------------------
#  Team CRUD routes
# ---------------------------------------------------------------------------

# === TEAM ROUTES ===

@router.post("/teams", response_model=dict)
async def create_team(data: TeamCreate):
    """Create a new team"""
    await check_slug_unique("teams", data.slug)
    
    # Устанавливаем primary_tag по умолчанию, если не задан
    primary_tag = data.primary_tag or data.name or data.title

    # Default placeholder logo when none provided
    logo = data.logo if data.logo is not None else _team_placeholder_logo()

    # If modules are not provided, try to use default team template (if configured)
    base_modules_input = [m.model_dump() if hasattr(m, "model_dump") else m for m in (data.modules or [])]
    if not base_modules_input:
        try:
            db = await get_db()
            tpl = await db.templates.find_one({"content_type": "team", "is_default": True})
            if tpl and isinstance(tpl.get("modules"), list) and tpl.get("modules"):
                base_modules_input = _clone_modules_with_new_ids(tpl.get("modules") or [])
        except Exception:
            # If templates collection is unavailable or template invalid, fall back to scaffold.
            base_modules_input = []

    # Ensure baseline scaffold (facts + modules) if modules are empty or missing core blocks
    city = None
    try:
        if isinstance(data.facts, dict):
            city = (data.facts or {}).get("Город") or (data.facts or {}).get("city")
    except Exception:
        city = None
    scaffold_facts, scaffold_order, scaffold_modules = _ensure_team_scaffold_fields(
        {"facts": data.facts or {}, "facts_order": data.facts_order or [], "modules": base_modules_input},
        name=data.name,
        city=city
    )
    
    team = Team(
        title=data.title, slug=data.slug, name=data.name, team_type=data.team_type,
        logo=logo,
        facts=scaffold_facts,
        facts_order=scaffold_order,
        social_links=data.social_links or {},
        primary_tag=primary_tag,
        modules=scaffold_modules,
        tags=data.tags,
        seo=data.seo or {},
        status=data.status
    )
    result = await create_content("teams", team, data.tags)
    
    # Auto-update "Список игр команды" module for KVN teams
    if data.team_type == "kvn" and data.slug:
        try:
            db = await get_db()
            team_doc = await db.teams.find_one({"_id": result.get("id")}, {"modules": 1})
            if team_doc:
                updated_modules = await _update_team_games_module(data.slug, team_doc.get("modules") or [], db)
                # Normalize orders
                for i, m in enumerate(updated_modules):
                    if isinstance(m, dict):
                        m["order"] = i
                await db.teams.update_one(
                    {"_id": result.get("id")},
                    {"$set": {"modules": updated_modules, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
        except Exception as e:
            logger.warning(f"Failed to auto-update team games module for {data.slug}: {e}")
    
    return result


@router.get("/teams", response_model=dict)
async def list_teams(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    team_type: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    letter: Optional[str] = None
):
    """List teams with pagination and filters"""
    db = await get_db()
    query = {}
    
    if status:
        query["status"] = status.value
    if tag:
        query["tags"] = tag
    if team_type:
        query["team_type"] = team_type
    
    # Улучшенный поиск для команд: ищем по name, title, slug и aliases
    if search:
        # Экранируем специальные символы regex для безопасности
        # re.escape экранирует только специальные символы (., *, +, ?, ^, $, [, ], {, }, |, \, (, )),
        # обычные буквы и цифры остаются без изменений
        search_term = search.strip()
        search_escaped = re.escape(search_term)
        
        # Для массива строк MongoDB автоматически применяет regex к каждому элементу
        # Используем частичное совпадение - ищем подстроку в любом месте поля
        # MongoDB regex с опцией "i" (case-insensitive) ищет подстроки, так что "бай" должно находить "Байкал"
        search_conditions = [
            {"name": {"$regex": search_escaped, "$options": "i"}},
            {"title": {"$regex": search_escaped, "$options": "i"}},
            {"slug": {"$regex": search_escaped, "$options": "i"}},
            {"aliases": {"$regex": search_escaped, "$options": "i"}}
        ]
        query["$or"] = search_conditions
    
    # Фильтр по первой букве (применяется дополнительно к поиску, если указан)
    if letter:
        letter_condition = {"name": {"$regex": f"^{re.escape(letter)}", "$options": "i"}}
        if "$or" in query:
            # Если есть поиск, добавляем фильтр по букве через $and
            query = {"$and": [{"$or": query["$or"]}, letter_condition]}
        else:
            query.update(letter_condition)
    
    total = await db.teams.count_documents(query)
    cursor = db.teams.find(query, {"modules": 0}).skip(skip).limit(limit).sort("name", 1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/teams/{id_or_slug}", response_model=dict)
async def get_team(id_or_slug: str):
    """Get team by ID or slug"""
    team = await get_by_id_or_slug("teams", id_or_slug, "Team not found")

    # Self-healing: ensure baseline scaffold exists for older/empty teams
    try:
        db = await get_db()
        name = (team.get("name") or team.get("title") or "").strip()
        facts = team.get("facts") if isinstance(team.get("facts"), dict) else {}
        city = facts.get("Город") or facts.get("city")

        new_facts, new_order, new_modules = _ensure_team_scaffold_fields(
            {"facts": facts, "facts_order": team.get("facts_order") or [], "modules": team.get("modules") or []},
            name=name or (team.get("title") or ""),
            city=city
        )

        # Auto-update "Список игр команды" module for KVN teams
        team_slug = team.get("slug")
        if team.get("team_type") == "kvn" and team_slug:
            try:
                new_modules = await _update_team_games_module(team_slug, new_modules, db)
            except Exception as e:
                logger.warning(f"Failed to auto-update team games module for {team_slug}: {e}")

        # Remove empty placeholder blocks unless this team was intentionally created empty via bulk import
        if not team.get("allow_empty_modules"):
            new_modules = _prune_empty_modules(new_modules)

        changes = {}

        # Smart logo picker: preserve existing logo or restore from legacy image/poster fields
        # This prevents overwriting real logos with placeholders
        picked_logo = _pick_team_logo(team)
        current_logo = team.get("logo")
        # Only update if logo is missing, placeholder, or different from picked
        if not current_logo or _is_placeholder_logo(current_logo) or current_logo != picked_logo:
            changes["logo"] = picked_logo

        if new_facts != facts:
            changes["facts"] = new_facts
        if new_order != (team.get("facts_order") or []):
            changes["facts_order"] = new_order
        if new_modules != (team.get("modules") or []):
            changes["modules"] = new_modules

        # Ensure tags contain primary_tag if possible (avoid breaking on duplicates)
        primary_tag = team.get("primary_tag")
        if not primary_tag:
            candidate = name or team.get("title")
            if candidate:
                try:
                    await check_primary_tag_duplicate("teams", candidate, exclude_id=team.get("_id"))
                    changes["primary_tag"] = candidate
                    primary_tag = candidate
                except HTTPException:
                    primary_tag = None

        if primary_tag:
            tags = list(team.get("tags") or [])
            if not any(isinstance(t, str) and t.lower() == primary_tag.lower() for t in tags):
                tags.append(primary_tag)
                changes["tags"] = tags
                await tag_service.sync_tags(tags)

        if changes:
            changes["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db.teams.update_one({"_id": team["_id"]}, {"$set": changes})
            team.update(changes)
    except Exception as e:
        logger.warning(f"Team scaffold self-heal skipped: {e}")

    # Разрешаем ссылки в модулях для ответа
    if team.get('modules'):
        team['modules'] = await LinkResolver.resolve_links_in_modules(team['modules'])

    return team


async def update_team_slug_in_seasons(old_slug: str, new_slug: str, new_name: str, team_id: str, db):
    """
    Обновляет slug команды во всех сезонах КВН, где она упоминается.
    Также обновляет team_name в играх, используя актуальное название команды.
    Обновляет:
    - season_data.all_teams[].slug (если это dict) или заменяет строку
    - season_data.winners[].slug (если это dict) или заменяет строку
    - season_data.stages[].games[].teams[].team_slug
    - season_data.stages[].games[].teams[].team_name (используя new_name)
    
    Ищет команду по team_id (если есть) или по любому из возможных slug'ов команды.
    """
    if not old_slug or not new_slug or old_slug == new_slug:
        return
    
    updated_seasons = 0
    
    # Получаем команду, чтобы узнать все возможные slug'ы (включая старые)
    team = await db.teams.find_one({"slug": new_slug})
    if not team:
        team = await db.teams.find_one({"_id": team_id}) if team_id else None
    
    # Собираем все возможные slug'ы команды для поиска
    possible_slugs = {old_slug, new_slug}
    if team:
        # Добавляем текущий slug команды
        if team.get("slug"):
            possible_slugs.add(team.get("slug"))
        # Можем также проверить исторические slug'ы, если они хранятся
    
    logger.info(f"Searching for team in seasons by possible slugs: {possible_slugs}, team_id: {team_id}")
    
    # Находим все сезоны, где упоминается эта команда
    # Ищем по team_id (если есть) или по любому из возможных slug'ов
    query = {"season_data": {"$exists": True}}
    
    # Если есть team_id, ищем также по team_id в играх
    # Но сначала просто ищем все сезоны и проверяем вручную
    async for season in db.kvn.find(query):
        season_data = season.get("season_data", {})
        if not season_data:
            continue
        
        needs_update = False
        
        # Обновляем в all_teams
        all_teams = season_data.get("all_teams", [])
        for i, team_entry in enumerate(all_teams):
            # Проверяем по slug (любому из возможных) или по team_id
            should_update = False
            if isinstance(team_entry, dict):
                entry_slug = team_entry.get("slug")
                entry_team_id = team_entry.get("team_id") or team_entry.get("id")
                # Обновляем, если slug совпадает с любым из возможных или team_id совпадает
                if entry_slug in possible_slugs or (team_id and entry_team_id == team_id):
                    should_update = True
            elif isinstance(team_entry, str) and team_entry in possible_slugs:
                should_update = True
            
            if should_update:
                if isinstance(team_entry, dict):
                    team_entry["slug"] = new_slug
                    # Обновляем название, если оно есть и отличается
                    if new_name and team_entry.get("name"):
                        old_name = team_entry.get("name", "")
                        # Сохраняем город, если он был в скобках
                        city_match = re.search(r'\s*\(([^)]+)\)\s*$', old_name)
                        if city_match:
                            city = city_match.group(1)
                            updated_name = f"{new_name} ({city})"
                        else:
                            updated_name = new_name
                        team_entry["name"] = updated_name
                    # Обновляем team_id, если его нет
                    if team_id and not team_entry.get("team_id"):
                        team_entry["team_id"] = team_id
                else:
                    all_teams[i] = new_slug
                needs_update = True
        
        # Обновляем в winners
        winners = season_data.get("winners", [])
        for i, winner in enumerate(winners):
            # Проверяем по slug (любому из возможных) или по team_id
            should_update = False
            if isinstance(winner, dict):
                winner_slug = winner.get("slug")
                winner_team_id = winner.get("team_id") or winner.get("id")
                if winner_slug in possible_slugs or (team_id and winner_team_id == team_id):
                    should_update = True
            elif isinstance(winner, str) and winner in possible_slugs:
                should_update = True
            
            if should_update:
                if isinstance(winner, dict):
                    winner["slug"] = new_slug
                    # Обновляем название, если оно есть и отличается
                    if new_name and winner.get("name"):
                        old_name = winner.get("name", "")
                        city_match = re.search(r'\s*\(([^)]+)\)\s*$', old_name)
                        if city_match:
                            city = city_match.group(1)
                            updated_name = f"{new_name} ({city})"
                        else:
                            updated_name = new_name
                        winner["name"] = updated_name
                    # Обновляем team_id, если его нет
                    if team_id and not winner.get("team_id"):
                        winner["team_id"] = team_id
                else:
                    winners[i] = new_slug
                needs_update = True
        
        # Обновляем в играх (stages -> games -> teams)
        stages = season_data.get("stages", [])
        games_updated = 0
        for stage in stages:
            games = stage.get("games", [])
            for game in games:
                teams = game.get("teams", [])
                for team in teams:
                    if isinstance(team, dict):
                        team_slug = team.get("team_slug")
                        team_team_id = team.get("team_id")
                        # Обновляем, если slug совпадает с любым из возможных или team_id совпадает
                        if team_slug in possible_slugs or (team_id and team_team_id == team_id):
                            old_team_slug = team.get("team_slug")
                            team["team_slug"] = new_slug
                            games_updated += 1
                            logger.info(f"  Updating team_slug in game '{game.get('name', 'N/A')}': '{old_team_slug}' -> '{new_slug}'")
                            # ВАЖНО: Обновляем team_name, используя актуальное название команды
                            if new_name:
                                old_team_name = team.get("team_name", "")
                                # Сохраняем город, если он был в скобках
                                city_match = re.search(r'\s*\(([^)]+)\)\s*$', old_team_name)
                                if city_match:
                                    city = city_match.group(1)
                                    updated_team_name = f"{new_name} ({city})"
                                else:
                                    updated_team_name = new_name
                                team["team_name"] = updated_team_name
                                logger.info(f"  Updating team_name in game: '{old_team_name}' -> '{updated_team_name}'")
                            # Обновляем team_id, если его нет
                            if team_id and not team.get("team_id"):
                                team["team_id"] = team_id
                            needs_update = True
        
        # Сохраняем обновления, если были изменения
        if needs_update:
            try:
                season_path = season.get('full_path', season.get('_id', 'unknown'))
                # Обновляем team_data_version, чтобы фронтенд знал, что данные изменились
                result = await db.kvn.update_one(
                    {"_id": season["_id"]},
                    {"$set": {
                        "season_data": season_data, 
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "team_data_version": datetime.now(timezone.utc).isoformat()
                    }}
                )
                if result.modified_count > 0:
                    updated_seasons += 1
                    logger.info(f"  ✅ Updated season: {season_path}")
                else:
                    logger.warning(f"  ⚠️  Season {season_path} marked for update but no changes were saved (modified_count=0)")
            except Exception as e:
                logger.error(f"Failed to update season {season.get('full_path', season.get('_id'))}: {e}", exc_info=True)
    
    if updated_seasons > 0:
        logger.info(f"✅ Updated team slug '{old_slug}' -> '{new_slug}' and name '{new_name}' in {updated_seasons} seasons")
    else:
        logger.warning(f"⚠️  No seasons found with team slug '{old_slug}' to update. Team may not be in any seasons yet.")


async def update_team_name_in_seasons(team_slug: str, new_name: str, db):
    """
    Обновляет название команды во всех сезонах КВН, где она упоминается.
    Обновляет:
    - season_data.all_teams[].name (сохраняет город, если он был: "Новое название (Город)")
    - season_data.stages[].games[].teams[].team_name (сохраняет город, если он был)
    """
    if not team_slug or not new_name:
        return
    
    updated_seasons = 0
    
    # Находим все сезоны, где упоминается эта команда
    async for season in db.kvn.find({"season_data": {"$exists": True}}):
        season_data = season.get("season_data", {})
        if not season_data:
            continue
        
        needs_update = False
        
        # Обновляем в all_teams
        all_teams = season_data.get("all_teams", [])
        for team_entry in all_teams:
            if isinstance(team_entry, dict) and team_entry.get("slug") == team_slug:
                old_name = team_entry.get("name", "")
                # Если старое название содержит город в скобках, сохраняем его
                city_match = re.search(r'\s*\(([^)]+)\)\s*$', old_name)
                if city_match:
                    city = city_match.group(1)
                    updated_name = f"{new_name} ({city})"
                else:
                    updated_name = new_name
                
                if old_name != updated_name:
                    team_entry["name"] = updated_name
                    needs_update = True
            elif isinstance(team_entry, str) and team_entry == team_slug:
                # Если all_teams содержит только slug'и, пропускаем (не обновляем)
                pass
        
        # Обновляем в играх (stages -> games -> teams)
        stages = season_data.get("stages", [])
        for stage in stages:
            games = stage.get("games", [])
            for game in games:
                teams = game.get("teams", [])
                for team in teams:
                    if isinstance(team, dict) and team.get("team_slug") == team_slug:
                        old_team_name = team.get("team_name", "")
                        # Если старое название содержит город в скобках, сохраняем его
                        city_match = re.search(r'\s*\(([^)]+)\)\s*$', old_team_name)
                        if city_match:
                            city = city_match.group(1)
                            updated_team_name = f"{new_name} ({city})"
                        else:
                            updated_team_name = new_name
                        
                        if old_team_name != updated_team_name:
                            team["team_name"] = updated_team_name
                            needs_update = True
        
        # Сохраняем обновления, если были изменения
        if needs_update:
            try:
                await db.kvn.update_one(
                    {"_id": season["_id"]},
                    {"$set": {"season_data": season_data, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                updated_seasons += 1
            except Exception as e:
                logger.error(f"Failed to update season {season.get('full_path', season.get('_id'))}: {e}")
    
    if updated_seasons > 0:
        logger.info(f"Updated team name '{new_name}' in {updated_seasons} seasons for team slug '{team_slug}'")


@router.put("/teams/{id}", response_model=dict)
async def update_team(id: str, data: TeamUpdate):
    """Update team"""
    db = await get_db()
    
    # Получаем текущую команду для сравнения
    current_team = await db.teams.find_one({"_id": id})
    if not current_team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    old_name = current_team.get("name") or current_team.get("title")
    old_slug = current_team.get("slug")
    
    # Выполняем обновление
    result = await update_content("teams", id, data, "Team not found")
    
    # Получаем обновленную команду, чтобы узнать финальные значения
    updated_team = await db.teams.find_one({"_id": id})
    if not updated_team:
        return result
    
    new_name = updated_team.get("name") or updated_team.get("title")
    new_slug = updated_team.get("slug")
    
    # Если изменился slug команды, обновляем его во всех сезонах
    # При этом также обновляем team_name, используя актуальное название
    if old_slug and new_slug and old_slug != new_slug:
        logger.info(f"Team slug changed: '{old_slug}' -> '{new_slug}', updating in all seasons...")
        team_id = updated_team.get("_id") or updated_team.get("id")
        await update_team_slug_in_seasons(old_slug, new_slug, new_name, team_id, db)
        # Используем новый slug для обновления названия (если оно тоже изменилось)
        team_slug = new_slug
        # Если название тоже изменилось, обновляем его отдельно (для случаев, когда slug не менялся)
        if new_name and new_name != old_name:
            logger.info(f"Team name also changed: '{old_name}' -> '{new_name}', updating in all seasons...")
            await update_team_name_in_seasons(team_slug, new_name, db)
    else:
        team_slug = old_slug or new_slug
        # Если изменилось только название (без изменения slug), обновляем его в сезонах
        if team_slug and new_name and new_name != old_name:
            logger.info(f"Team name changed: '{old_name}' -> '{new_name}', updating in all seasons...")
            await update_team_name_in_seasons(team_slug, new_name, db)
    
    return result


@router.delete("/teams/{id}")
async def delete_team(id: str):
    """Delete team"""
    return await delete_content("teams", id, "Team not found")

