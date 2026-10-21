"""Создание страниц и явные операции связывания с одной переданной БД."""
import re
from typing import Optional

from fastapi import HTTPException
from models.content import Person, PersonCreate, Team, TeamCreate, Show, ShowCreate
from models.modules import ModuleType, PageModule
from services import memberships, show_appearances
from services.cache import cache_service
from services.crud import check_slug_unique, create_content
from services.show_teams import get_team_show, check_team_slug_free, team_placement, sync_related_teams


def _without_legacy_marker(value: Optional[str]) -> Optional[str]:
    return re.sub(r"\s*\*+\s*", " ", value).strip() if value else value


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


def _build_team_intro_html(name: str, city: Optional[str]) -> str:
    city_part = f" ({city})" if city else ""
    # Keep exact requested pattern: "Название команды (город) - ... "
    return f"<p>{name}{city_part} - ...</p>"


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


def _full_path(parent: Optional[dict], slug: str) -> str:
    return f"{parent['full_path'].strip('/')}/{slug}" if parent else slug


async def _get_parent(db, parent_id: Optional[str]) -> Optional[dict]:
    if not parent_id:
        return None
    parent = await db.shows.find_one({"_id": parent_id})
    if not parent:
        raise HTTPException(status_code=400, detail="Родительское шоу не найдено")
    if not parent.get("full_path"):
        raise HTTPException(status_code=400, detail="У родительского шоу не задан путь (full_path)")
    return parent


async def _check_path_free(db, full_path: str, exclude_id: Optional[str] = None) -> None:
    query = {"full_path": full_path}
    if exclude_id:
        query["_id"] = {"$ne": exclude_id}
    if await db.shows.find_one(query, {"_id": 1}) or await db.teams.find_one({"full_path": full_path}, {"_id": 1}):
        raise HTTPException(status_code=400, detail=f"Адрес /shows/{full_path} уже занят")


async def create_person_record(db, data: PersonCreate, *, document_id=None, defer_links=False, page_package_id=None):
    """Create a new person."""
    await check_slug_unique("people", data.slug, db=db)

    def swap_name_order(name):
        if not name:
            return name
        parts = name.strip().split()
        if len(parts) == 2:
            return f"{parts[1]} {parts[0]}"
        return name

    title = _without_legacy_marker(data.title) if data.foreign_agent else data.title
    full_name = _without_legacy_marker(data.full_name) if data.foreign_agent else data.full_name
    primary_tag = _without_legacy_marker(data.primary_tag) if data.foreign_agent else data.primary_tag
    if not primary_tag:
        primary_tag = swap_name_order(title) or swap_name_order(full_name)

    person = Person(
        **({'id': document_id} if document_id else {}),
        title=title, slug=data.slug, full_name=full_name, aliases=data.aliases,
        foreign_agent=data.foreign_agent,
        photo=data.photo, bio=data.bio or {}, social_links=data.social_links or {},
        facts=data.facts or {}, facts_order=data.facts_order or [], primary_tag=primary_tag,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status
    )
    result = await create_content("people", person, data.tags, db=db, **({'page_package_id': page_package_id} if page_package_id else {}))
    if not defer_links:
        await link_person_everywhere(db, result["id"])
    return result


async def create_team_record(db, data: TeamCreate, *, document_id=None, defer_links=False, page_package_id=None):
    """Create a new team (команда шоу — с show_id, адрес /shows/{путь шоу}/teams/{slug})"""
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
        **({'id': document_id} if document_id else {}),
        title=data.title, slug=data.slug, name=data.name, aliases=data.aliases,
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
    result = await create_content("teams", team, data.tags, db=db, **({'page_package_id': page_package_id} if page_package_id else {}))

    if data.related_team_ids:
        related = await sync_related_teams(db, result["id"], data.related_team_ids)
        await db.teams.update_one({"_id": result["id"]}, {"$set": {"related_team_ids": related}})

    # Составы: текстовый блок «Состав команды» → записи «человек — команда»
    created = await db.teams.find_one({"_id": result["id"]})
    if created and not defer_links:
        await memberships.import_team_rosters(db, created)

    # ─── Инвалидация кэша ─────────────────────────────────────────────
    cache_service.invalidate_team(data.slug)
    cache_service.invalidate_team_lists()

    return result


async def create_show_record(db, data: ShowCreate, *, document_id=None, page_package_id=None):
    """Create a new show."""
    parent = await _get_parent(db, data.parent_id)
    full_path = _full_path(parent, data.slug)
    await _check_path_free(db, full_path)

    facts = data.facts or {}
    show = Show(
        **({'id': document_id} if document_id else {}),
        title=data.title, slug=data.slug, name=data.name, aliases=data.aliases, poster=data.poster,
        facts=facts, facts_order=data.facts_order or list(facts), social_links=data.social_links or {},
        description=data.description,
        parent_id=parent["_id"] if parent else None, full_path=full_path,
        level=(parent.get("level", 0) + 1) if parent else 0, order=data.order or 0,
        modules=data.modules, tags=data.tags, seo=data.seo or {}, status=data.status,
        related_person_ids=data.related_person_ids or []
    )
    return await create_content("shows", show, data.tags, db=db, **({'page_package_id': page_package_id} if page_package_id else {}))


async def link_person_everywhere(db, person_id: str) -> None:
    """Связать человека с записями составов, где он упомянут по slug старого сайта или однозначному имени."""
    person = await db.people.find_one({"_id": person_id})
    if person:
        await memberships.link_person(db, person)
        await show_appearances.link_new_person(db, person)
