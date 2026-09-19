"""Team routes — CRUD + bulk operations + KVN league results + scaffold."""
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from utils.auth import require_editor_on_write
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
from services.views_counter import views_counter
from services.competitions import sync_kvn_pages
from services.memberships import import_team_rosters
from services.show_teams import (
    KVN_ONLY, attach_related_teams, attach_show_info, check_team_slug_free, get_team_show, kvn_team_query,
    split_team_path, sync_related_teams, team_id_or_kvn_slug_query, team_placement,
)
from utils.auth import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["teams"], dependencies=[Depends(require_editor_on_write)])


def _pages_with_team_query(slug: str) -> dict:
    """Страницы сезонов КВН, где упоминается команда с данным slug."""
    return {"$or": [
        {"season_data.stages.games.teams.team_slug": slug},
        {"season_data.all_teams.slug": slug},
        {"season_data.winners.slug": slug},
    ]}


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

def _team_placeholder_logo(key: str = "team") -> dict:
    """
    Default placeholder logo used when a team has no logo yet.
    Must exist in frontend static/media.
    """
    value = str(key or "team")
    hash_value = 0
    for char in value:
        hash_value = ((hash_value * 31) + ord(char)) & 0xFFFFFFFF
    url = f"/media/imported/images/pattern/{hash_value % 4 + 1}.jpg"
    return {"url": url, "alt": "", "caption": "", "thumbnail": url}


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


def _build_team_intro_html(name: str, city: Optional[str]) -> str:
    city_part = f" ({city})" if city else ""
    # Keep exact requested pattern: "Название команды (город) - ... "
    return f"<p>{name}{city_part} - ...</p>"


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


def _ensure_team_scaffold_fields(doc: dict, *, name: str, city: Optional[str],
                                 kvn: bool = True) -> tuple[dict, list[str], list[dict]]:
    """
    Ensure KVN team has baseline facts + modules scaffold.
    У команды шоу (kvn=False) — только системные модули: факты «Год основания»/«Капитан», вступление
    и пустые разделы не добавляются (у команд шоу капитана может не быть).
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
    if kvn and ("Год основания" not in facts or not str(facts.get("Год основания") or "").strip()):
        facts["Год основания"] = "—"
    if kvn and ("Капитан" not in facts or not str(facts.get("Капитан") or "").strip()):
        facts["Капитан"] = "—"

    # Facts order: prefer explicit order if present, otherwise seed with desired keys
    current_order = list(doc.get("facts_order") or [])
    desired_prefix = ["Город", "Год основания", "Капитан"] if kvn else []
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
    if not kvn:
        return facts, ordered, _normalized_orders(modules)

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
    # NOTE: "Список игр команды" не добавляется: игры команды показываются из participations
    # to prevent duplicates and ensure it's always auto-generated for KVN teams
    required_sections = ["Состав команды", "История команды"]
    base_order = 12
    for idx, title in enumerate(required_sections):
        text_block_sig = ("text_block", title)
        if text_block_sig not in existing_signatures:
            add_module(PageModule(type=ModuleType.TEXT_BLOCK, order=base_order + idx, visible=True, data={"title": title, "content": ""}))

    return facts, ordered, _normalized_orders(modules)


def _normalized_orders(modules: list) -> list[dict]:
    """Normalize orders to be stable"""
    modules_sorted = sorted(
        [m for m in modules if isinstance(m, dict)],
        key=lambda x: (x.get("order") or 0)
    )
    for i, m in enumerate(modules_sorted):
        m["order"] = i
    return modules_sorted

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
    """Create a new team (команда шоу — с show_id, адрес /shows/{путь шоу}/teams/{slug})"""
    db = await get_db()
    show = await get_team_show(db, data.show_id)
    await check_team_slug_free(db, data.slug, show)
    placement = await team_placement(db, show, data.slug)
    
    # Устанавливаем primary_tag по умолчанию, если не задан
    primary_tag = data.primary_tag or data.name or data.title

    # Default placeholder logo when none provided
    logo = data.logo if data.logo is not None else _team_placeholder_logo(data.slug)

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
        city=city,
        kvn=show is None,
    )

    team = Team(
        title=data.title, slug=data.slug, name=data.name,
        team_type=placement.get("team_type") or data.team_type,
        show_id=placement["show_id"], full_path=placement["full_path"],
        logo=logo,
        related_team_ids=[],
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

    if data.related_team_ids:
        related = await sync_related_teams(db, result["id"], data.related_team_ids)
        await db.teams.update_one({"_id": result["id"]}, {"$set": {"related_team_ids": related}})

    # Составы: текстовый блок «Состав команды» → записи «человек — команда»
    created = await db.teams.find_one({"_id": result["id"]})
    if created:
        await import_team_rosters(db, created)

    # ─── Инвалидация кэша ─────────────────────────────────────────────
    cache_service.invalidate_team(data.slug)
    cache_service.invalidate_team_lists()

    return result


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
):
    """List teams with pagination and filters"""
    # ─── Кэш: проверяем ──────────────────────────────────────────────
    cache_key = f"tl:{skip}:{limit}:{status}:{team_type}:{tag}:{search}:{letter}:{show_id}"
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
    
    result = await list_alphabetical_content(
        "teams", skip, limit, query, ["title", "name"]
    )
    items = result["items"]
    await attach_show_info(db, items)

    result["items"] = items

    # ─── Кэш: сохраняем ──────────────────────────────────────────────
    cache_service.set_team_list(cache_key, result)

    return result


async def _find_team(db, id_or_slug: str) -> dict:
    """По _id (любая команда) или по slug (только команды КВН — slug команд шоу уникален лишь внутри шоу)."""
    team = await db.teams.find_one(team_id_or_kvn_slug_query(id_or_slug))
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


async def _add_show_context(db, team: dict) -> dict:
    """Шоу команды и хлебные крошки (шоу → страница-список «Команды …», если есть)."""
    await attach_show_info(db, [team])
    if not team.get("show"):
        return team
    crumbs = []
    fields = {"title": 1, "full_path": 1, "slug": 1, "parent_id": 1}
    current = await db.shows.find_one({"_id": team["show_id"]}, fields)
    while current and len(crumbs) < 10:
        crumbs.insert(0, {"title": current.get("title"), "path": "/shows/" + (current.get("full_path") or current["slug"])})
        parent_id = current.get("parent_id")
        current = await db.shows.find_one({"_id": parent_id}, fields) if parent_id else None
    teams_page = await db.shows.find_one(
        {"full_path": f"{team['show']['full_path']}/teams", "status": {"$ne": "archived"}},
        {"title": 1, "full_path": 1},
    )
    if teams_page:
        crumbs.append({"title": teams_page.get("title"), "path": "/shows/" + teams_page["full_path"]})
    team["breadcrumbs"] = crumbs
    return team


@router.get("/teams/by-path/{path:path}", response_model=dict)
async def get_team_by_path(path: str):
    """Команда шоу по адресу: «liga-gorodov/teams/eto-oni» (публичная страница /shows/liga-gorodov/teams/eto-oni)."""
    path = path.strip("/")
    if not split_team_path(path):
        raise HTTPException(status_code=404, detail="Team not found")
    cache_key = "path:" + path
    cached = cache_service.get_team(cache_key)
    if cached is not None:
        views_counter.increment("teams", cached["_id"])
        return cached
    db = await get_db()
    team = await db.teams.find_one({"full_path": path})
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    views_counter.increment("teams", team["_id"])
    await _add_show_context(db, team)
    await attach_related_teams(db, team)
    await LinkResolver.resolve_document(team)
    cache_service.set_team(cache_key, team)
    return team


@router.get("/teams/{id_or_slug}", response_model=dict)
async def get_team(id_or_slug: str, raw: bool = Query(False, description="без обработки ссылок (для админки)")):
    """Get team by ID or slug — чистое чтение, без write-on-read."""
    db = await get_db()
    if raw:
        team = await _find_team(db, id_or_slug)
        await attach_show_info(db, [team])
        await attach_related_teams(db, team, public=False)
        return team

    # ─── Кэш: проверяем ──────────────────────────────────────────────
    cached = cache_service.get_team(id_or_slug)
    if cached is not None:
        views_counter.increment("teams", cached["_id"])
        return cached

    team = await _find_team(db, id_or_slug)
    views_counter.increment("teams", team["_id"])
    await _add_show_context(db, team)
    await attach_related_teams(db, team)

    # Ссылки в тексте: актуальные адреса, на отсутствующие страницы — текстом
    await LinkResolver.resolve_document(team)

    # ─── Кэш: сохраняем ──────────────────────────────────────────────
    team_slug = team.get("slug", id_or_slug)
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

    # Если изменился slug команды КВН — обновляем ссылки во всех сезонах.
    # Названия в сезонах НЕ трогаем: там хранится название, под которым команда играла в том сезоне.
    if was_kvn and not updated_team.get("show_id") and old_slug and new_slug and old_slug != new_slug:
        logger.info(f"Team slug changed: '{old_slug}' -> '{new_slug}', updating in all seasons...")
        team_id = updated_team.get("_id") or updated_team.get("id")
        await update_team_slug_in_seasons(old_slug, new_slug, None, team_id, db)
        await sync_kvn_pages(db, _pages_with_team_query(new_slug))

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
    team = await db.teams.find_one({"_id": id}, {"slug": 1})
    result = await delete_content("teams", id, "Team not found")
    await db.memberships.delete_many({"team_id": id})
    await db.teams.update_many({"related_team_ids": id}, {"$pull": {"related_team_ids": id}})
    # Модель соревнований: ссылки на удалённую команду в сезонах становятся непривязанными
    if team and team.get("slug"):
        await sync_kvn_pages(db, _pages_with_team_query(team["slug"]))
    # ─── Инвалидация кэша ─────────────────────────────────────────────
    cache_service.invalidate_team()  # flush all team cache
    cache_service.invalidate_team_lists()
    return result

