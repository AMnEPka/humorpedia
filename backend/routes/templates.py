"""Page templates management routes"""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional, List, Literal
from datetime import datetime, timezone

from models.modules import PageTemplate
from pydantic import BaseModel, Field
from utils.database import get_db
from routes.auth import get_current_user

router = APIRouter(prefix="/templates", tags=["templates"])


class ApplyTemplateToTeamsRequest(BaseModel):
    team_type: str = Field(default="kvn", description="Which team_type to target (e.g. kvn)")
    mode: Literal["replace", "merge", "if_empty"] = Field(
        default="merge",
        description="replace: overwrite modules; merge: keep existing modules and add missing from template; if_empty: only when modules empty/missing"
    )
    dry_run: bool = False


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


def _module_signature(m: dict) -> tuple:
    """
    Build a stable-ish signature to match modules across teams/templates.
    We intentionally DO NOT use module.id (it's per-page).
    
    For text_block: if title is same but content is different, they're NOT duplicates.
    Use content hash (first 50 chars) as part of signature to distinguish them.
    """
    m_type = (m.get("type") or "").strip()
    data = m.get("data") or {}

    if m_type == "text_block":
        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()
        # Include content hash to distinguish different content blocks with same title
        content_hash = content[:50] if content else ""
        return (m_type, title, content_hash)

    if m_type == "timeline":
        title = (data.get("title") or m.get("title") or "").strip()
        return (m_type, title)

    title = (m.get("title") or data.get("title") or "").strip()
    return (m_type, title)


def _merge_template_into_existing_modules(template_modules: list, existing_modules: list) -> list:
    """
    Safe mode:
    - preserves existing modules (and their data)
    - ensures all template modules exist (adds missing ones)
    - keeps any extra modules after template-defined ones
    - removes duplicates: if multiple modules have same signature, keeps only first one
    """
    tpl = [m for m in (template_modules or []) if isinstance(m, dict)]
    ex = [m for m in (existing_modules or []) if isinstance(m, dict)]

    used = [False] * len(ex)
    merged: list[dict] = []
    seen_signatures = set()  # Track signatures we've already added to prevent duplicates

    # First pass: match template modules to existing ones
    for tm in tpl:
        sig = _module_signature(tm)
        found_idx = None
        for i, em in enumerate(ex):
            if used[i]:
                continue
            if _module_signature(em) == sig and sig[0]:
                found_idx = i
                break
        if found_idx is not None:
            used[found_idx] = True
            merged.append(ex[found_idx])
            seen_signatures.add(sig)
        else:
            # Only add if we haven't seen this signature yet
            if sig not in seen_signatures:
                merged.append(_clone_modules_with_new_ids([tm])[0])
                seen_signatures.add(sig)

    # Second pass: add unused existing modules, but skip duplicates
    for i, em in enumerate(ex):
        if not used[i]:
            sig = _module_signature(em)
            # Only add if signature is unique (not already in merged list)
            if sig not in seen_signatures:
                merged.append(em)
                seen_signatures.add(sig)

    return merged


def _normalize_module_orders(modules: list) -> list:
    """Ensure module.order is 0..n-1 in current list order."""
    normalized = []
    for m in modules or []:
        if isinstance(m, dict):
            normalized.append(m)
    for i, m in enumerate(normalized):
        m["order"] = i
    return normalized


def _matches_section_title(title: str, base_title: str) -> bool:
    """
    Match titles like:
    - "История команды", "История команды 2", "История команды-2", "История команды — 2"
    """
    if not isinstance(title, str):
        return False
    t = title.strip()
    if t == base_title:
        return True
    if not t.startswith(base_title):
        return False
    # Accept any trailing separator/number
    suffix = t[len(base_title):].strip()
    if not suffix:
        return True
    # Normalize common separators
    suffix = suffix.lstrip("-–—:").strip()
    return suffix.isdigit()


def _merge_team_text_blocks(modules: list, base_title: str) -> list:
    """
    Merge multiple text_block modules for a given section into one:
    - preserves order by module.order
    - concatenates non-empty contents with <hr/> separator
    - removes merged-away modules
    """
    ms = [m for m in (modules or []) if isinstance(m, dict)]
    candidates = []
    for idx, m in enumerate(ms):
        if m.get("type") != "text_block":
            continue
        data = m.get("data") or {}
        title = data.get("title") or ""
        if _matches_section_title(title, base_title):
            candidates.append((idx, m))

    if len(candidates) <= 1:
        return ms

    # Sort by declared order first, then by appearance
    def sort_key(pair):
        idx, m = pair
        return (m.get("order") if m.get("order") is not None else 10**9, idx)

    candidates_sorted = sorted(candidates, key=sort_key)
    keep_idx, keep_mod = candidates_sorted[0]

    contents = []
    for _, m in candidates_sorted:
        data = m.get("data") or {}
        c = (data.get("content") or "").strip()
        if c:
            contents.append(c)

    merged_content = "<hr/>".join(contents).strip()
    keep_data = dict((keep_mod.get("data") or {}))
    keep_data["title"] = base_title
    keep_data["content"] = merged_content
    keep_mod["data"] = keep_data
    keep_mod["title"] = base_title

    remove_indices = {idx for idx, _ in candidates_sorted[1:]}
    result = [m for i, m in enumerate(ms) if i not in remove_indices]
    return result


def _merge_team_required_sections(modules: list) -> list:
    """
    Project rule: merge split sections into one.
    Currently:
    - История команды (and История команды 2/История команды-2/…)
    - Список игр команды (and variants)
    """
    ms = [m for m in (modules or []) if isinstance(m, dict)]
    ms = _merge_team_text_blocks(ms, "История команды")
    ms = _merge_team_text_blocks(ms, "Список игр команды")
    return _normalize_module_orders(ms)


@router.post("", response_model=dict)
async def create_template(data: PageTemplate, request: Request):
    """Create a new page template"""
    user = await get_current_user(request)
    if not user or user.get("role") not in ["admin", "editor"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    db = await get_db()
    
    # Check name uniqueness
    existing = await db.templates.find_one({"name": data.name})
    if existing:
        raise HTTPException(status_code=400, detail="Шаблон с таким именем уже существует")
    
    doc = data.model_dump()
    doc["_id"] = data.id
    doc["created_by"] = user["_id"]
    
    await db.templates.insert_one(doc)
    
    return {"id": doc["_id"], "name": data.name}


@router.get("", response_model=dict)
async def list_templates(
    content_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """List all templates"""
    db = await get_db()
    
    query = {}
    if content_type:
        query["content_type"] = content_type
    
    total = await db.templates.count_documents(query)
    cursor = db.templates.find(query).skip(skip).limit(limit).sort("name", 1)
    items = await cursor.to_list(limit)
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/default/{content_type}", response_model=dict)
async def get_default_template(content_type: str):
    """Get default template for content type"""
    db = await get_db()
    
    template = await db.templates.find_one({
        "content_type": content_type,
        "is_default": True
    })
    
    if not template:
        # Return empty template
        return {
            "id": None,
            "name": f"Стандартный {content_type}",
            "content_type": content_type,
            "modules": [],
            "is_default": True
        }
    
    return template


@router.get("/{template_id}", response_model=dict)
async def get_template(template_id: str):
    """Get template by ID"""
    db = await get_db()
    
    template = await db.templates.find_one({"_id": template_id})
    
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    return template


@router.put("/{template_id}", response_model=dict)
async def update_template(template_id: str, data: PageTemplate, request: Request):
    """Update template"""
    user = await get_current_user(request)
    if not user or user.get("role") not in ["admin", "editor"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    db = await get_db()
    
    update_data = data.model_dump(exclude={"id"})
    update_data["updated_by"] = user["_id"]
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.templates.update_one({"_id": template_id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    return {"id": template_id, "updated": True}


@router.post("/{template_id}/set-default", response_model=dict)
async def set_default_template(template_id: str, request: Request):
    """Set template as default for its content type"""
    user = await get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    
    db = await get_db()
    
    template = await db.templates.find_one({"_id": template_id})
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    # Remove default from other templates of same type
    await db.templates.update_many(
        {"content_type": template["content_type"]},
        {"$set": {"is_default": False}}
    )
    
    # Set this one as default
    await db.templates.update_one(
        {"_id": template_id},
        {"$set": {"is_default": True}}
    )
    
    return {"id": template_id, "is_default": True}


@router.delete("/{template_id}")
async def delete_template(template_id: str, request: Request):
    """Delete template"""
    user = await get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    
    db = await get_db()
    
    result = await db.templates.delete_one({"_id": template_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    return {"id": template_id, "deleted": True}


# === APPLY TEMPLATE TO EXISTING CONTENT ===

@router.post("/{template_id}/apply-to-teams", response_model=dict)
async def apply_template_to_teams(template_id: str, body: ApplyTemplateToTeamsRequest, request: Request):
    """
    Apply a template to teams by team_type (KVN teams use team_type='kvn').
    """
    user = await get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")

    db = await get_db()

    template = await db.templates.find_one({"_id": template_id})
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    if template.get("content_type") != "team":
        raise HTTPException(status_code=400, detail="Этот шаблон можно применять только к типу 'team'")

    # Target teams
    team_type = body.team_type
    query = {"team_type": team_type}

    matched = await db.teams.count_documents(query)
    modified = 0

    if matched == 0:
        return {"matched": 0, "modified": 0, "dry_run": body.dry_run}

    # We must iterate because we also want to keep per-team intro (name/city) consistent
    # and ensure stable order via the existing scaffold normalizer.
    from routes.content import (
        _ensure_team_scaffold_fields,
        _team_placeholder_logo,
        _pick_team_logo,
        _is_placeholder_logo,
        _prune_empty_modules
    )

    cursor = db.teams.find(query)
    async for team in cursor:
        existing_modules = team.get("modules") or []
        if body.mode == "if_empty" and existing_modules:
            continue

        facts = team.get("facts") if isinstance(team.get("facts"), dict) else {}
        name = (team.get("name") or team.get("title") or "").strip()
        city = facts.get("Город") or facts.get("city")

        if body.mode == "replace":
            base_modules = _clone_modules_with_new_ids(template.get("modules") or [])
        elif body.mode == "merge":
            base_modules = _merge_template_into_existing_modules(template.get("modules") or [], existing_modules)
        else:  # if_empty
            base_modules = _clone_modules_with_new_ids(template.get("modules") or [])
        new_facts, new_order, new_modules = _ensure_team_scaffold_fields(
            {"facts": facts, "facts_order": team.get("facts_order") or [], "modules": base_modules},
            name=name or (team.get("title") or ""),
            city=city,
        )

        # Project rule: merge split sections into single blocks (avoid empty duplicates)
        new_modules = _merge_team_required_sections(new_modules)
        
        # Auto-update "Список игр команды" module for KVN teams
        team_slug = team.get("slug")
        if team.get("team_type") == "kvn" and team_slug:
            try:
                from routes.content import _update_team_games_module
                new_modules = await _update_team_games_module(team_slug, new_modules, db)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to auto-update team games module for {team_slug}: {e}")
        
        # Remove empty placeholders unless team is intentionally empty (bulk import)
        if not team.get("allow_empty_modules"):
            new_modules = _prune_empty_modules(new_modules)

        changes = {
            "modules": new_modules,
            "facts": new_facts,
            "facts_order": new_order,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Logo handling: in merge mode, never touch logo. In other modes, use smart picker.
        if body.mode == "merge":
            # Safe mode: preserve existing logo completely
            pass  # Don't add logo to changes
        else:
            # Replace/if_empty modes: use smart picker to restore from legacy fields if needed
            picked_logo = _pick_team_logo(team)
            current_logo = team.get("logo")
            # Only update if logo is missing, placeholder, or different from picked
            if not current_logo or _is_placeholder_logo(current_logo) or current_logo != picked_logo:
                changes["logo"] = picked_logo

        if body.dry_run:
            continue

        res = await db.teams.update_one({"_id": team["_id"]}, {"$set": changes})
        if res.modified_count:
            modified += 1

    return {"matched": matched, "modified": modified, "dry_run": body.dry_run, "mode": body.mode, "team_type": team_type}


# === MODULE TYPES INFO ===

@router.get("/modules/types", response_model=list)
async def list_module_types():
    """Get all available module types with descriptions"""
    return [
        {
            "type": "poster_photo",
            "name": "Фото/Постер",
            "description": "Фото/постер в сайдбаре",
            "icon": "image",
            "for_types": ["person", "team", "show", "article", "news", "quiz", "wiki", "page"]
        },
        {
            "type": "facts_table",
            "name": "Информация",
            "description": "Таблица фактов из поля facts",
            "icon": "table",
            "for_types": ["person", "team", "show", "wiki"]
        },
        {
            "type": "rating_widget",
            "name": "Оценка",
            "description": "Рейтинг/оценка страницы",
            "icon": "star",
            "for_types": ["person", "team", "show", "article", "news", "wiki"]
        },
        {
            "type": "tags_cloud",
            "name": "Облако тегов",
            "description": "Отображение тегов страницы (облако/бейджи)",
            "icon": "tag",
            "for_types": ["all"]
        },
        {
            "type": "social_links",
            "name": "Ссылки",
            "description": "Социальные ссылки (vk/yt/tg/...)",
            "icon": "link",
            "for_types": ["person", "team", "show"]
        },
        {
            "type": "hero_card",
            "name": "Карточка с фото",
            "description": "Фото с краткими фактами",
            "icon": "user",
            "for_types": ["person", "team", "show"]
        },
        {
            "type": "text_block",
            "name": "Текстовый блок",
            "description": "Блок текста с заголовком",
            "icon": "file-text",
            "for_types": ["all"]
        },
        {
            "type": "timeline",
            "name": "Хронология",
            "description": "Таймлайн событий",
            "icon": "clock",
            "for_types": ["person", "team", "show"]
        },
        {
            "type": "tags",
            "name": "Теги",
            "description": "Отображение тегов",
            "icon": "tag",
            "for_types": ["all"]
        },
        {
            "type": "table",
            "name": "Таблица",
            "description": "Таблица данных с сортировкой",
            "icon": "table",
            "for_types": ["all"]
        },
        {
            "type": "gallery",
            "name": "Галерея",
            "description": "Галерея изображений",
            "icon": "image",
            "for_types": ["all"]
        },
        {
            "type": "video",
            "name": "Видео",
            "description": "Встроенное видео",
            "icon": "play",
            "for_types": ["all"]
        },
        {
            "type": "quote",
            "name": "Цитата",
            "description": "Блок цитаты",
            "icon": "quote",
            "for_types": ["article", "news"]
        },
        {
            "type": "team_members",
            "name": "Состав команды",
            "description": "Список участников",
            "icon": "users",
            "for_types": ["team"]
        },
        {
            "type": "tv_appearances",
            "name": "ТВ эфиры",
            "description": "Таблица ТВ эфиров",
            "icon": "tv",
            "for_types": ["team"]
        },
        {
            "type": "games_list",
            "name": "Список игр",
            "description": "Список игр команды",
            "icon": "list",
            "for_types": ["team"]
        },
        {
            "type": "episodes_list",
            "name": "Список выпусков",
            "description": "Список эпизодов шоу",
            "icon": "film",
            "for_types": ["show"]
        },
        {
            "type": "participants",
            "name": "Участники",
            "description": "Список участников шоу",
            "icon": "users",
            "for_types": ["show"]
        },
        {
            "type": "quiz_questions",
            "name": "Вопросы квиза",
            "description": "Блок вопросов",
            "icon": "help-circle",
            "for_types": ["quiz"]
        },
        {
            "type": "quiz_results",
            "name": "Результаты квиза",
            "description": "Описание результатов",
            "icon": "award",
            "for_types": ["quiz"]
        },
        {
            "type": "best_articles",
            "name": "Лучшие статьи",
            "description": "Виджет лучших статей",
            "icon": "star",
            "for_types": ["page"]
        },
        {
            "type": "interesting",
            "name": "Интересное",
            "description": "Виджет интересного контента",
            "icon": "zap",
            "for_types": ["page"]
        },
        {
            "type": "random_page",
            "name": "Случайная страница",
            "description": "Ссылка на случайную страницу",
            "icon": "shuffle",
            "for_types": ["page"]
        },
        {
            "type": "table_of_contents",
            "name": "Оглавление",
            "description": "Навигация по странице (по timeline или секциям)",
            "icon": "list",
            "for_types": ["person", "team", "article", "wiki"]
        }
    ]
