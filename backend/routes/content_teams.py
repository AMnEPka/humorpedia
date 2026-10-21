"""Team routes — CRUD + bulk operations + KVN league results + scaffold."""
import copy
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from utils.auth import EDITOR_ROLES, get_current_user, require_editor_on_write
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
from services import content_commands
from services.content_commands import _team_placeholder_logo, _build_team_intro_html, _clone_modules_with_new_ids, _ensure_team_scaffold_fields, _normalized_orders
from utils.slugify import generate_slug
from utils.search import literal_search_pattern
from utils.team_matcher import normalize_team_name
from services.crud import (
    create_content, update_content,
    delete_content,
    check_primary_tag_duplicate,
    alphabet_letter_pattern,
    list_alphabetical_content,
)
from services.tags import tag_service
from services.link_resolver import LinkResolver
from services.cache import cache_service
from services.content_visibility import editor_can_view_archived, require_visible, visible_query
from services.views_counter import views_counter
from services.competitions import save_season
from services.memberships import import_team_rosters
from services.catalog_filters import team_conditions, teams_filter_options
from services.show_teams import (
    KVN_ONLY, attach_related_teams, attach_show_info, check_team_slug_free, get_team_show, kvn_team_query,
    split_team_path, sync_related_teams, team_id_or_kvn_slug_query, team_placement,
)
from utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["teams"], dependencies=[Depends(require_editor_on_write)])


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
    existing = await collection.find_one(kvn_team_query(slug))
    if not existing:
        return slug

    counter = 2
    while True:
        slug = f"{base_slug}-{counter}"
        existing = await collection.find_one(kvn_team_query(slug))
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


def _is_placeholder_logo(logo: any) -> bool:
    """
    Check if logo is a placeholder pattern image.
    """
    if not logo:
        return True
    if isinstance(logo, dict):
        url = logo.get("url") or logo.get("thumbnail") or ""
        return bool(url and (
            "/media/imported/images/pattern-" in url
            or "/media/imported/images/pattern/" in url
        ))
    if isinstance(logo, str):
        return "/media/imported/images/pattern-" in logo or "/media/imported/images/pattern/" in logo
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
    return _team_placeholder_logo(doc.get("slug") or doc.get("name") or doc.get("title"))


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


GAMES_TABLE_TITLE = "Список игр команды"


def _is_games_table_module(m: dict) -> bool:
    """
    Старый модуль «Список игр команды» (HTML-таблица, генерировалась из season_data).
    С этапа 2 игры команды показываются из participations (/api/competitions/teams/{slug}/participations),
    поэтому такие модули удаляются при самовосстановлении команды.
    """
    if not isinstance(m, dict) or m.get("type") != "text_block":
        return False
    data = m.get("data") or {}
    title = (data.get("title") or m.get("title") or "").strip().lower()
    if title.startswith(GAMES_TABLE_TITLE.lower()):
        return True
    content = (data.get("content") or "").lower()
    return "<table" in content and all(h in content for h in ("год", "лига", "стадия", "результат"))


def _remove_team_games_tables(modules: List[dict]) -> List[dict]:
    return [m for m in modules if not _is_games_table_module(m)]


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

    # Load only fields needed for matching (массовое добавление — для сезонов КВН, команды шоу не участвуют)
    cursor = db.teams.find(KVN_ONLY, {"_id": 1, "slug": 1, "name": 1, "title": 1, "aliases": 1})
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
            logo=_team_placeholder_logo(slug),
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


@router.post("/teams/restore-logos", response_model=dict, dependencies=[Depends(require_admin)])
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
    return await create_team_record(data)


async def create_team_record(data: TeamCreate, *, document_id=None, defer_links=False, page_package_id=None):
    """Совместимая обёртка над доменной операцией создания."""
    return await content_commands.create_team_record(await get_db(), data, document_id=document_id, defer_links=defer_links, page_package_id=page_package_id)


@router.get("/teams", response_model=dict)
async def list_teams(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    team_type: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    letter: Optional[str] = None,
    show_id: Optional[str] = Query(None, description="команды шоу (_id шоу)"),
    city: Optional[str] = Query(None, max_length=100),
    league: Optional[str] = Query(None, max_length=100),
    year: Optional[int] = Query(None, ge=1900, le=2100),
    show: Optional[str] = Query(None, max_length=100),
    sort: Optional[Literal["popular"]] = None,
    request: Request = None,
):
    """List teams with pagination and filters"""
    editor = await editor_can_view_archived(request, get_current_user)
    if not editor and status == ContentStatus.ARCHIVED:
        raise HTTPException(status_code=404, detail="Teams not found")
    # ─── Кэш: проверяем ──────────────────────────────────────────────
    cache_key = f"tl:{int(editor)}:{skip}:{limit}:{status}:{team_type}:{tag}:{search}:{letter}:{show_id}:{city}:{league}:{year}:{show}:{sort}"
    cached = cache_service.get_team_list(cache_key)
    if cached is not None:
        return cached

    db = await get_db()
    conditions = []

    if status:
        conditions.append({"status": status.value})
    if tag:
        conditions.append({"tags": tag})
    if team_type == "kvn":
        # Исторически у части команд КВН team_type не заполнен
        conditions.append({"team_type": {"$in": ["kvn", None]}})
        conditions.append(KVN_ONLY)
    elif team_type:
        conditions.append({"team_type": team_type})
    if show_id:
        conditions.append({"show_id": show_id})

    conditions.extend(await team_conditions(db, city=city, league=league, year=year, show=show))
    availability_conditions = list(conditions)
    if not editor:
        conditions.append({"status": {"$ne": ContentStatus.ARCHIVED.value}})
        availability_conditions.append({"status": {"$ne": ContentStatus.ARCHIVED.value}})

    # Поиск подстроки (без учёта регистра) по name, title, slug и aliases
    if search and search.strip():
        search_escaped = literal_search_pattern(search.strip())
        conditions.append({"$or": [
            {"name": {"$regex": search_escaped, "$options": "i"}},
            {"title": {"$regex": search_escaped, "$options": "i"}},
            {"slug": {"$regex": search_escaped, "$options": "i"}},
            {"aliases": {"$regex": search_escaped, "$options": "i"}},
        ]})

    # Фильтр по первой букве
    if letter:
        letter_pattern = alphabet_letter_pattern(letter)
        conditions.append({"title": {"$regex": letter_pattern, "$options": "i"}})

    query = {"$and": conditions} if conditions else {}
    availability_query = (
        {"$and": availability_conditions} if availability_conditions else {}
    )
    
    result = await list_alphabetical_content(
        "teams", skip, limit, query, ["title", "name"],
        availability_query=availability_query,
        sort=sort,
    )
    items = result["items"]
    await attach_show_info(db, items, include_archived=editor)

    result["items"] = items
    result["filters"] = await teams_filter_options(db, kvn=team_type == "kvn")

    # ─── Кэш: сохраняем ──────────────────────────────────────────────
    cache_service.set_team_list(cache_key, result)

    return result


async def _find_team(db, id_or_slug: str) -> dict:
    """По _id (любая команда) или по slug (только команды КВН — slug команд шоу уникален лишь внутри шоу)."""
    team = await db.teams.find_one(team_id_or_kvn_slug_query(id_or_slug))
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


async def _add_show_context(db, team: dict, include_archived: bool = False) -> dict:
    """Шоу команды и хлебные крошки (шоу → страница-список «Команды …», если есть)."""
    team.pop("breadcrumbs", None)
    await attach_show_info(db, [team], include_archived=include_archived)
    if not team.get("show"):
        return team
    crumbs = []
    fields = {"title": 1, "full_path": 1, "slug": 1, "parent_id": 1}
    show_query = {"_id": team["show_id"]}
    if not include_archived:
        show_query.update({"status": {"$ne": ContentStatus.ARCHIVED.value}})
    current = await db.shows.find_one(show_query, fields)
    while current and len(crumbs) < 10:
        crumbs.insert(0, {"title": current.get("title"), "path": "/shows/" + (current.get("full_path") or current["slug"])})
        parent_id = current.get("parent_id")
        parent_query = {"_id": parent_id}
        if not include_archived:
            parent_query.update({"status": {"$ne": ContentStatus.ARCHIVED.value}})
        current = await db.shows.find_one(parent_query, fields) if parent_id else None
    teams_page = await db.shows.find_one(
        {"full_path": f"{team['show']['full_path']}/teams", "status": {"$ne": "archived"}},
        {"title": 1, "full_path": 1},
    )
    if teams_page:
        crumbs.append({"title": teams_page.get("title"), "path": "/shows/" + teams_page["full_path"]})
    team["breadcrumbs"] = crumbs
    return team


@router.get("/teams/by-path/{path:path}", response_model=dict)
async def get_team_by_path(path: str, request: Request = None):
    """Команда шоу по адресу: «liga-gorodov/teams/eto-oni» (публичная страница /shows/liga-gorodov/teams/eto-oni)."""
    path = path.strip("/")
    if not split_team_path(path):
        raise HTTPException(status_code=404, detail="Team not found")
    editor = await editor_can_view_archived(request, get_current_user)
    db = await get_db()
    cache_key = "path:" + path
    cached = cache_service.get_team(cache_key) if not editor else None
    if cached is not None:
        if cached.get("status") == ContentStatus.ARCHIVED.value and not editor:
            raise HTTPException(status_code=404, detail="Team not found")
        current = await db.teams.find_one({"_id": cached["_id"]}, {"status": 1})
        require_visible(current, editor, "Team not found")
        views_counter.increment("teams", cached["_id"])
        return cached
    team = await db.teams.find_one(visible_query({"full_path": path}, editor))
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    require_visible(team, editor, "Team not found")
    views_counter.increment("teams", team["_id"])
    await _add_show_context(db, team, include_archived=editor)
    await attach_related_teams(db, team, public=not editor)
    await LinkResolver.resolve_document(team)
    if not editor and team.get("status") != ContentStatus.ARCHIVED.value:
        cache_service.set_team(cache_key, team)
    return team


@router.get("/teams/{id_or_slug}", response_model=dict)
async def get_team(id_or_slug: str, raw: bool = Query(False, description="без обработки ссылок (для админки)"), request: Request = None):
    """Get team by ID or slug — чистое чтение, без write-on-read."""
    editor = await editor_can_view_archived(request, get_current_user)
    db = await get_db()
    if raw:
        team = require_visible(await _find_team(db, id_or_slug), editor, "Team not found")
        await attach_show_info(db, [team], include_archived=editor)
        await attach_related_teams(db, team, public=not editor)
        return team

    # ─── Кэш: проверяем ──────────────────────────────────────────────
    cached = cache_service.get_team(id_or_slug) if not editor else None
    if cached is not None:
        if cached.get("status") == ContentStatus.ARCHIVED.value and not editor:
            raise HTTPException(status_code=404, detail="Team not found")
        current = await db.teams.find_one({"_id": cached["_id"]}, {"status": 1})
        require_visible(current, editor, "Team not found")
        views_counter.increment("teams", cached["_id"])
        return cached

    team = require_visible(await _find_team(db, id_or_slug), editor, "Team not found")
    views_counter.increment("teams", team["_id"])
    await _add_show_context(db, team, include_archived=editor)
    await attach_related_teams(db, team, public=not editor)

    # Ссылки в тексте: актуальные адреса, на отсутствующие страницы — текстом
    await LinkResolver.resolve_document(team)

    # ─── Кэш: сохраняем ──────────────────────────────────────────────
    team_slug = team.get("slug", id_or_slug)
    if not editor and team.get("status") != ContentStatus.ARCHIVED.value:
        cache_service.set_team(team_slug, team)
        if team_slug != id_or_slug:
            cache_service.set_team(id_or_slug, team)

    return team


# ─── Self-healing: выделенные эндпоинты (НЕ на каждом чтении) ──────────────

async def _run_team_self_healing(team_doc: dict, db) -> dict:
    """
    Self-healing для одной команды: scaffold, games module, logo, tags.
    Возвращает dict с изменениями (или пустой dict).
    """
    name = (team_doc.get("name") or team_doc.get("title") or "").strip()
    facts = team_doc.get("facts") if isinstance(team_doc.get("facts"), dict) else {}
    city = facts.get("Город") or facts.get("city")

    is_kvn = not team_doc.get("show_id")
    new_facts, new_order, new_modules = _ensure_team_scaffold_fields(
        {"facts": facts, "facts_order": team_doc.get("facts_order") or [], "modules": team_doc.get("modules") or []},
        name=name or (team_doc.get("title") or ""),
        city=city,
        kvn=is_kvn,
    )

    # Старые HTML-таблицы «Список игр команды» удаляются: игры показываются из participations
    if is_kvn:
        new_modules = _remove_team_games_tables(new_modules)

    if not team_doc.get("allow_empty_modules"):
        new_modules = _prune_empty_modules(new_modules)

    changes = {}

    picked_logo = _pick_team_logo(team_doc)
    current_logo = team_doc.get("logo")
    if not current_logo or _is_placeholder_logo(current_logo) or current_logo != picked_logo:
        changes["logo"] = picked_logo

    if new_facts != facts:
        changes["facts"] = new_facts
    if new_order != (team_doc.get("facts_order") or []):
        changes["facts_order"] = new_order
    if new_modules != (team_doc.get("modules") or []):
        changes["modules"] = new_modules

    primary_tag = team_doc.get("primary_tag")
    if not primary_tag:
        candidate = name or team_doc.get("title")
        if candidate:
            try:
                await check_primary_tag_duplicate("teams", candidate, exclude_id=team_doc.get("_id"))
                changes["primary_tag"] = candidate
                primary_tag = candidate
            except HTTPException:
                primary_tag = None

    if primary_tag:
        tags = list(team_doc.get("tags") or [])
        if not any(isinstance(t, str) and t.lower() == primary_tag.lower() for t in tags):
            tags.append(primary_tag)
            changes["tags"] = tags
            await tag_service.sync_tags(tags)

    if changes:
        changes["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.teams.update_one({"_id": team_doc["_id"]}, {"$set": changes})

    return changes


@router.post("/teams/{id_or_slug}/refresh", response_model=dict)
async def refresh_team(id_or_slug: str):
    """
    Принудительный self-healing для одной команды.
    Пересчитывает scaffold, «Список игр», лого, теги.
    """
    db = await get_db()
    team_doc = await db.teams.find_one({"$or": [kvn_team_query(id_or_slug), {"id": id_or_slug}, {"_id": id_or_slug}]})
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")

    changes = await _run_team_self_healing(team_doc, db)
    cache_service.invalidate_team()

    return {"success": True, "slug": team_doc.get("slug"), "changes_count": len(changes)}


@router.post("/teams-refresh-all", response_model=dict)
async def refresh_all_teams(
    limit: int = Query(default=0, description="Сколько команд обработать (0 = все)"),
    only_kvn: bool = Query(default=True, description="Только KVN-команды"),
):
    """
    Массовый self-healing всех команд. Запускать после импорта данных или обновления сезонов.
    """
    db = await get_db()
    query = {"team_type": "kvn"} if only_kvn else {}
    cursor = db.teams.find(query)
    if limit > 0:
        cursor = cursor.limit(limit)

    total = 0
    updated = 0
    errors = 0
    async for team_doc in cursor:
        total += 1
        try:
            changes = await _run_team_self_healing(team_doc, db)
            if changes:
                updated += 1
        except Exception as e:
            errors += 1
            logger.warning(f"Refresh failed for {team_doc.get('slug')}: {e}")

    cache_service.invalidate_team()  # flush all team cache
    cache_service.invalidate_team_lists()

    return {"success": True, "total": total, "updated": updated, "errors": errors}



_SEASON_TEAM_REF_PATHS = ("teams", "winners", "stages.games.results")


def _season_team_refs_query(team_id: str, slug: str | None = None) -> dict:
    clauses = [
        {f"{path}.team_id": team_id}
        for path in _SEASON_TEAM_REF_PATHS
        if team_id
    ]
    if slug:
        clauses.extend({f"{path}.slug": slug} for path in _SEASON_TEAM_REF_PATHS)
    return {"$or": clauses} if clauses else {"_id": {"$exists": False}}


def _iter_season_team_refs(season: dict):
    for key in ("teams", "winners"):
        refs = season.get(key)
        if isinstance(refs, list):
            yield from (ref for ref in refs if isinstance(ref, dict))
    for stage in season.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        for game in stage.get("games") or []:
            if isinstance(game, dict):
                yield from (ref for ref in (game.get("results") or []) if isinstance(ref, dict))


def _has_active_season_claim(season: dict) -> bool:
    projection = season.get("_projection")
    projection_state = projection.get("state") if isinstance(projection, dict) else None
    return bool(season.get("_write_claim")) or projection_state not in (None, "ready")


async def _assert_team_seasons_unclaimed(db, team_id: str, slug: str | None) -> None:
    async for season in db.seasons.find(_season_team_refs_query(team_id, slug)):
        if _has_active_season_claim(season):
            raise HTTPException(status_code=409, detail="Сезон команды обрабатывается; удаление отклонено.")


async def _has_team_season_refs(db, team_id: str) -> bool:
    async for _season in db.seasons.find(_season_team_refs_query(team_id)):
        return True
    return False


async def update_team_slug_in_seasons(old_slug: str, new_slug: str, team_id: str, db) -> int:
    """Update canonical team links; names remain the historical season labels."""
    if not team_id or not new_slug:
        return 0

    # Once a rename has committed, retry by ID only. Matching the new slug here
    # could claim refs intentionally detached by a previous team deletion.
    legacy_slug = old_slug if old_slug and old_slug != new_slug else None
    updated_seasons = 0
    async for stored in db.seasons.find(_season_team_refs_query(team_id, legacy_slug)):
        season = copy.deepcopy(stored)
        changed = False
        for ref in _iter_season_team_refs(season):
            ref_team_id = ref.get("team_id")
            matches_id = ref_team_id == team_id
            matches_legacy_slug = bool(legacy_slug and ref_team_id in (None, "") and ref.get("slug") == legacy_slug)
            if not (matches_id or matches_legacy_slug):
                continue
            if ref.get("slug") != new_slug:
                ref["slug"] = new_slug
                changed = True
            if matches_legacy_slug:
                ref["team_id"] = team_id
                changed = True
        if changed:
            saved = await save_season(
                db, copy.deepcopy(season), write_page=True,
                expected_updated_at=stored.get("updated_at"),
            )
            if saved.get("projection_status") == "error":
                raise HTTPException(409, f"Команда и сезон сохранены; восстановите проекции сезона {stored['_id']} перед повтором")
            updated_seasons += 1
    return updated_seasons


async def detach_team_from_seasons(team_id: str, db) -> int:
    """Detach by canonical ID only; do not reclaim historical slug-only refs."""
    if not team_id:
        return 0
    detached_seasons = 0
    async for stored in db.seasons.find(_season_team_refs_query(team_id)):
        if _has_active_season_claim(stored):
            raise HTTPException(status_code=409, detail="Сезон команды обрабатывается; отвязка отклонена.")
        season = copy.deepcopy(stored)
        changed = False
        for ref in _iter_season_team_refs(season):
            if ref.get("team_id") == team_id:
                ref["team_id"] = None
                changed = True
        if changed:
            saved = await save_season(
                db, copy.deepcopy(season), write_page=True,
                expected_updated_at=stored.get("updated_at"),
            )
            if saved.get("projection_status") == "error":
                raise HTTPException(409, f"Команда и сезон сохранены; восстановите проекции сезона {stored['_id']} перед повтором")
            detached_seasons += 1
    return detached_seasons

@router.put("/teams/{id}", response_model=dict)
async def update_team(id: str, data: TeamUpdate):
    """Update team"""
    db = await get_db()
    
    # Получаем текущую команду для сравнения
    current_team = await db.teams.find_one({"_id": id})
    if not current_team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    old_slug = current_team.get("slug")
    was_kvn = not current_team.get("show_id")

    # Привязка к шоу и адрес: slug уникален в пределах шоу (у КВН — среди команд КВН)
    new_show_id = (data.show_id or None) if data.show_id is not None else current_team.get("show_id")
    new_slug_value = data.slug or old_slug
    # show_id, адрес и тип команды шоу пишутся здесь, а не через update_content (None там — «не менять»)
    changes = {"show_id": None} if not new_show_id else {"show_id": None, "team_type": None}
    if (new_show_id != current_team.get("show_id") or new_slug_value != old_slug
            or (new_show_id and not current_team.get("full_path"))):
        show = await get_team_show(db, new_show_id)
        await check_team_slug_free(db, new_slug_value, show, exclude_id=id)
        placement = await team_placement(db, show, new_slug_value)
        if not show and not was_kvn:
            placement["team_type"] = "kvn"
        await db.teams.update_one({"_id": id}, {"$set": placement})
    if data.related_team_ids is not None:
        changes["related_team_ids"] = await sync_related_teams(
            db, id, data.related_team_ids, current_team.get("related_team_ids") or [])
    data = data.model_copy(update=changes)

    # Выполняем обновление
    result = await update_content("teams", id, data, "Team not found")

    # Получаем обновленную команду, чтобы узнать финальные значения
    updated_team = await db.teams.find_one({"_id": id})
    if not updated_team:
        return result
    
    new_slug = updated_team.get("slug")
    
    # Составы: текстовый блок «Состав команды» мог измениться — переразобрать
    if data.modules is not None:
        await import_team_rosters(db, updated_team)

    # The canonical writer is safe to repeat when a prior season CAS failed
    # after the team itself had already moved to its requested slug.
    if was_kvn and not updated_team.get("show_id") and data.slug is not None and new_slug:
        team_id = updated_team.get("_id") or updated_team.get("id")
        await update_team_slug_in_seasons(old_slug, new_slug, team_id, db)

    # ─── Self-healing при сохранении ─────────────────────────────────
    # Пересчитываем scaffold и «Список игр» только при сохранении из админки
    try:
        refreshed_team = await db.teams.find_one({"_id": id})
        if refreshed_team:
            await _run_team_self_healing(refreshed_team, db)
    except Exception as e:
        logger.warning(f"Self-healing after update failed for {id}: {e}")

    # ─── Инвалидация кэша ─────────────────────────────────────────────
    cache_service.invalidate_team()
    cache_service.invalidate_team_lists()

    return result


@router.delete("/teams/{id}")
async def delete_team(id: str):
    """Delete team"""
    db = await get_db()
    team = await db.teams.find_one({"_id": id}, {"slug": 1, "show_id": 1})
    team_id = (team.get("_id") or id) if team else id
    if team is None:
        # Resume per-season cleanup after a previous delete committed but a CAS
        # projection failed. Slug-only matches are unsafe once the team is gone.
        if not await _has_team_season_refs(db, team_id):
            await delete_content("teams", id, "Team not found")
        await _assert_team_seasons_unclaimed(db, team_id, None)
        await detach_team_from_seasons(team_id, db)
        result = {"id": id, "deleted": True}
    else:
        is_kvn_team = not team.get("show_id")
        if is_kvn_team:
            await _assert_team_seasons_unclaimed(db, team_id, team.get("slug"))
        result = await delete_content("teams", id, "Team not found")
        if is_kvn_team:
            await detach_team_from_seasons(team_id, db)
    await db.memberships.delete_many({"team_id": id})
    await db.teams.update_many({"related_team_ids": id}, {"$pull": {"related_team_ids": id}})
    # ─── Инвалидация кэша ─────────────────────────────────────────────
    cache_service.invalidate_team()  # flush all team cache
    cache_service.invalidate_team_lists()
    return result
