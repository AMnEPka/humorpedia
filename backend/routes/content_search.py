"""Search, resolve-link, and duplicate routes."""
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from utils.auth import require_editor_on_write
from typing import Optional
from datetime import datetime, timezone

import copy as copy_module
import logging
import re
import uuid

from utils.database import get_db
from utils.search import literal_search_pattern, normalize_search_text, search_variants, edit_distance
from services.crud import (
    generate_unique_slug, convert_objectids_to_strings,
)
from services.tags import tag_service
from services.show_teams import attach_show_info, team_id_or_kvn_slug_query, team_url

logger = logging.getLogger(__name__)

# Rate limiter for search endpoints (общий экземпляр)
from utils.rate_limit import limiter


def _normalized_search_query(query: str) -> str:
    """Normalize user text for matching and relevance comparisons."""
    return normalize_search_text(query)


def _partial_search_query(query: str, fields: list[str]) -> dict:
    """Build a literal, case-insensitive substring search for MongoDB."""
    escaped_query = literal_search_pattern(query)
    return {
        "$and": [
            {"status": {"$ne": "archived"}},
            {"$or": [
                {field: {"$regex": escaped_query, "$options": "i"}}
                for field in fields
            ]},
        ]
    }


def _relevance_key(document: dict, fields: list[str], query: str, type_order: int = 0) -> tuple:
    """Rank exact, title-prefix, word-prefix and substring matches in that order."""
    needle = _normalized_search_query(query).casefold()
    best = (4, 10**9, 10**9, len(fields), "")

    for field_order, field in enumerate(fields):
        values = document.get(field) or []
        for raw in values if isinstance(values, list) else [values]:
            haystack = _normalized_search_query(str(raw)).casefold()
            position = haystack.find(needle)
            if position < 0:
                continue
            if haystack == needle:
                match_kind = 0
            elif position == 0:
                match_kind = 1
            elif re.search(rf"(?<!\w){re.escape(needle)}", haystack):
                match_kind = 2
            else:
                match_kind = 3
            best = min(best, (match_kind, position, len(haystack), field_order, haystack))

    return (
        best[0], best[1], type_order, best[3], best[4], best[2],
        str(document.get("_id", "")),
    )


async def _find_ranked_matches(
    collection,
    fields: list[str],
    query: str,
    limit: int,
    projection: dict,
    fuzzy: bool = True,
) -> list[dict]:
    """Fetch a bounded candidate set and return its most relevant matches."""
    candidate_limit = min(max(limit * 5, 100), 500)
    cursor = collection.find(_partial_search_query(query, fields), projection).limit(candidate_limit)
    items = await cursor.to_list(candidate_limit)
    if items:
        return sorted(items, key=lambda item: _relevance_key(item, fields, query))[:limit]

    for variant in search_variants(query)[1:]:
        cursor = collection.find(_partial_search_query(variant, fields), projection).limit(candidate_limit)
        items = await cursor.to_list(candidate_limit)
        if items:
            return sorted(items, key=lambda item: _relevance_key(item, fields, variant))[:limit]

    # Typo fallback only for long enough names, with a bounded prefix candidate set.
    needle = _normalized_search_query(query)
    if not fuzzy or len(needle) < 5 or len(needle) > 40 or len(needle.split()) > 3:
        return []
    prefix = re.escape(needle[:3])
    typo_query = {'$and': [
        {'status': {'$ne': 'archived'}},
        {'$or': [{field: {'$regex': f'^{prefix}', '$options': 'i'}} for field in fields]},
    ]}
    cursor = collection.find(typo_query, projection).limit(candidate_limit)
    candidates = await cursor.to_list(candidate_limit)
    maximum = 1 if len(needle) < 9 else 2
    matches = []
    for item in candidates:
        values = []
        for field in fields:
            raw = item.get(field) or []
            values.extend(raw if isinstance(raw, list) else [raw])
        distance = min((edit_distance(needle, part, maximum) for value in values
                        for part in [_normalized_search_query(value), *_normalized_search_query(value).split()]),
                       default=maximum + 1)
        if distance <= maximum:
            matches.append((distance, item))
    return [item for _, item in sorted(matches, key=lambda row: (row[0], str(row[1].get('title') or '')))[:limit]]


def _entity_name_query(term: str, fields: list[str]) -> dict:
    """Match editorial names, aliases and short Russian inflection stems, never page HTML."""
    variants = search_variants(term)
    patterns = [literal_search_pattern(value) for value in variants]
    words = _normalized_search_query(term).split()
    if words and all(len(word) >= 4 for word in words):
        patterns.append('.*'.join(re.escape(word[:max(3, len(word) - 2)]) for word in words))
    return {'$and': [
        {'status': {'$ne': 'archived'}},
        {'$or': [{field: {'$regex': pattern, '$options': 'i'}}
                 for field in fields for pattern in dict.fromkeys(patterns)]},
    ]}


async def _named_entities(db, collection: str, term: str, fields: list[str], limit: int = 20) -> list[dict]:
    items = await getattr(db, collection).find(_entity_name_query(term, fields)).limit(100).to_list(100)
    variants = search_variants(term)
    ranked = sorted(items, key=lambda item: min(_relevance_key(item, fields, variant) for variant in variants))
    exact = [item for item in ranked if min(_relevance_key(item, fields, variant)[0]
                                             for variant in variants) == 0]
    return (exact or ranked)[:limit]


async def _visible_by_ids(db, collection: str, ids: list[str], limit: int) -> list[dict]:
    if not ids:
        return []
    return await getattr(db, collection).find({
        '_id': {'$in': list(dict.fromkeys(ids))}, 'status': {'$ne': 'archived'}
    }, {'modules': 0}).limit(limit).to_list(limit)


async def _structured_search(db, query: str, limit: int) -> Optional[dict[str, list[dict]]]:
    """Resolve relationship phrases through saved IDs in domain collections."""
    text = _normalized_search_query(query)
    member = re.match(r'^(капитан|участники?|игроки?)\s+(?:команды\s+)?(.+)$', text)
    if member:
        role, team_name = member.groups()
        teams = await _named_entities(db, 'teams', team_name, ['title', 'name', 'aliases', 'slug'])
        team_ids = [team['_id'] for team in teams]
        if not team_ids:
            return {'person': []}
        conditions = {'team_id': {'$in': team_ids}, 'person_id': {'$nin': [None, '']}}
        if role == 'капитан':
            conditions['roles'] = {'$regex': 'капитан', '$options': 'i'}
        rows = await db.memberships.find(conditions, {'person_id': 1}).limit(200).to_list(200)
        return {'person': await _visible_by_ids(db, 'people', [row['person_id'] for row in rows], limit)}

    show_people = re.match(r'^(?:комики|участники?|люди)\s+шоу\s+(.+)$', text)
    if show_people:
        shows = await _named_entities(db, 'shows', show_people.group(1), ['title', 'name', 'aliases', 'slug', 'full_path'])
        show_ids = [show['_id'] for show in shows]
        if not show_ids:
            return {'person': []}
        rows = await db.show_appearances.find(
            {'show_id': {'$in': show_ids}, 'person_id': {'$nin': [None, '']}, 'excluded': {'$ne': True}},
            {'person_id': 1}).limit(300).to_list(300)
        ids = [row['person_id'] for row in rows]
        ids.extend(person_id for show in shows for person_id in show.get('participant_ids') or [])
        return {'person': await _visible_by_ids(db, 'people', ids, limit)}

    show_teams = re.match(r'^команды\s+шоу\s+(.+)$', text)
    if show_teams:
        shows = await _named_entities(db, 'shows', show_teams.group(1), ['title', 'name', 'aliases', 'slug', 'full_path'])
        ids = [show['_id'] for show in shows]
        teams = await db.teams.find({'show_id': {'$in': ids}, 'status': {'$ne': 'archived'}},
                                    {'modules': 0}).limit(limit).to_list(limit)
        await attach_show_info(db, teams)
        return {'team': teams}

    city_teams = re.match(r'^команды(?:\s+квн)?\s+из\s+(.+)$', text)
    if city_teams:
        cities = await _named_entities(db, 'cities', city_teams.group(1), ['title', 'name', 'aliases', 'slug'])
        ids = [team_id for city in cities for team_id in city.get('related_team_ids') or []]
        teams = await db.teams.find({'_id': {'$in': ids}, 'show_id': None,
                                     'status': {'$ne': 'archived'}}, {'modules': 0}).limit(limit).to_list(limit)
        await attach_show_info(db, teams)
        return {'team': teams}

    city_people = re.match(r'^(?:люди|комики)\s+из\s+(.+)$', text)
    if city_people:
        cities = await _named_entities(db, 'cities', city_people.group(1), ['title', 'name', 'aliases', 'slug'])
        ids = [person_id for city in cities for person_id in city.get('related_person_ids') or []]
        return {'person': await _visible_by_ids(db, 'people', ids, limit)}

    league = re.match(r'^команды\s+(.+?)(?:\s+из\s+(.+))?$', text)
    if league:
        league_name, city_name = league.groups()
        tournaments = await _named_entities(db, 'tournaments', league_name,
                                             ['title', 'short_title', 'slug'])
        if tournaments:
            tournament_ids = [row['_id'] for row in tournaments]
            participations = await db.participations.find(
                {'tournament_id': {'$in': tournament_ids}, 'team_id': {'$nin': [None, '']}},
                {'team_id': 1}).limit(1000).to_list(1000)
            ids = [row['team_id'] for row in participations]
            if city_name:
                cities = await _named_entities(db, 'cities', city_name, ['title', 'name', 'aliases', 'slug'])
                city_ids = {team_id for city in cities for team_id in city.get('related_team_ids') or []}
                ids = [team_id for team_id in ids if team_id in city_ids]
            teams = await _visible_by_ids(db, 'teams', ids, limit)
            await attach_show_info(db, teams)
            return {'team': teams}
    return None

router = APIRouter(prefix="/content", tags=["search"], dependencies=[Depends(require_editor_on_write)])


# ---------------------------------------------------------------------------
#  Content search (for link insertion in editor)
# ---------------------------------------------------------------------------

@router.get("/search-for-links")
async def search_content_for_links(
    query: str = Query(..., description="Поисковый запрос"),
    types: Optional[str] = Query(None, description="Типы контента через запятую: person,team,show,kvn"),
    limit: int = Query(10, ge=1, le=50)
):
    """Поиск контента для вставки ссылок (для админ-редактора)."""
    db = await get_db()
    query_text = _normalized_search_query(query)

    types_list = [t.strip() for t in types.split(',')] if types else ['person', 'team', 'show', 'kvn']

    search_configs = {
        'person': {
            'collection': db.people,
            'search_fields': ["title", "full_name", "slug"],
            'projection': {"title": 1, "full_name": 1, "slug": 1},
            'title_fn': lambda d: d.get("full_name") or d.get("title"),
            'url_fn': lambda d: f"/people/{d.get('slug')}",
        },
        'team': {
            'collection': db.teams,
            'search_fields': ["name", "title", "slug"],
            'projection': {"name": 1, "title": 1, "slug": 1, "full_path": 1, "show_id": 1},
            'title_fn': lambda d: d.get("name") or d.get("title"),
            'url_fn': team_url,
        },
        'show': {
            'collection': db.shows,
            'search_fields': ["name", "title", "slug", "full_path"],
            'projection': {"name": 1, "title": 1, "slug": 1, "full_path": 1},
            'title_fn': lambda d: d.get("name") or d.get("title"),
            'url_fn': lambda d: f"/shows/{d.get('full_path') or d.get('slug')}",
        },
        'kvn': {
            'collection': db.kvn,
            'search_fields': ["name", "title", "slug", "full_path"],
            'projection': {"name": 1, "title": 1, "slug": 1, "full_path": 1},
            'title_fn': lambda d: d.get("name") or d.get("title"),
            'url_fn': lambda d: (
                f"/{(d.get('full_path') or d.get('slug', '')).lstrip('/')}"
                if d.get('full_path') else f"/kvn/{d.get('slug')}"
            ),
        },
    }

    ranked_results = []
    for type_order, content_type in enumerate(types_list):
        cfg = search_configs.get(content_type)
        if not cfg:
            continue

        items = await _find_ranked_matches(
            cfg['collection'], cfg['search_fields'], query_text, limit, cfg['projection']
        )
        if content_type == 'team':
            await attach_show_info(db, items)
        for doc in items:
            result = {
                "type": content_type,
                "id": str(doc["_id"]),
                "slug": doc.get("slug"),
                "title": cfg['title_fn'](doc),
                "url": cfg['url_fn'](doc),
            }
            ranked_results.append((
                _relevance_key(doc, cfg['search_fields'], query_text, type_order),
                result,
            ))

    ranked_results.sort(key=lambda item: item[0])
    return {"results": [item[1] for item in ranked_results[:limit]]}


@router.get("/{content_type}/{id_or_slug}/resolve-link")
async def resolve_content_link(content_type: str, id_or_slug: str):
    """Получить актуальный URL для контента."""
    db = await get_db()

    collection_map = {
        'person': (db.people, '/people/'),
        'team': (db.teams, '/kvn/teams/'),
        'show': (db.shows, '/shows/'),
        'kvn': (db.kvn, '/kvn/'),
    }

    if content_type not in collection_map:
        raise HTTPException(status_code=404, detail="Unknown content type")

    collection, url_prefix = collection_map[content_type]
    if content_type == 'team':
        query = team_id_or_kvn_slug_query(id_or_slug)
    else:
        query = {"$or": [{"_id": id_or_slug}, {"id": id_or_slug}, {"slug": id_or_slug}]}
    doc = await collection.find_one(query)

    if not doc:
        raise HTTPException(status_code=404, detail="Content not found")

    if content_type == 'kvn':
        full_path = doc.get('full_path') or doc.get('slug')
        url = f"/{full_path.lstrip('/')}" if full_path else f"{url_prefix}{doc.get('slug')}"
    elif content_type == 'show':
        url = f"{url_prefix}{doc.get('full_path') or doc.get('slug')}"
    elif content_type == 'team':
        url = team_url(doc)
    else:
        url = f"{url_prefix}{doc.get('slug')}"

    return {
        "id": str(doc["_id"]),
        "slug": doc.get("slug"),
        "title": doc.get("title") or doc.get("name") or doc.get("full_name"),
        "url": url
    }


# ---------------------------------------------------------------------------
#  Universal search (public)
# ---------------------------------------------------------------------------

@router.get("/search", response_model=dict)
@limiter.limit("60/minute")  # 60 requests per minute for public search
async def search_all(
    request: Request,
    q: str = Query(..., min_length=2),
    types: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
):
    """Search across all content types by a literal fragment of two or more characters."""
    db = await get_db()
    query_text = _normalized_search_query(q)
    if len(query_text) < 2:
        raise HTTPException(status_code=422, detail="Поисковый запрос должен содержать минимум 2 символа")

    search_types = [item.strip() for item in types.split(",")] if types else [
        "person", "team", "show", "city", "quiz", "article", "news", "wiki", "section"]

    collection_map = {
        "person": ("people", ["full_name", "title", "aliases", "slug"]),
        "team": ("teams", ["name", "title", "aliases", "slug"]),
        "show": ("shows", ["name", "title", "aliases", "slug", "full_path"]),
        "city": ("cities", ["name", "title", "aliases", "slug"]),
        "quiz": ("quizzes", ["title", "slug"]),
        "article": ("articles", ["title"]),
        "news": ("news", ["title"]),
        "wiki": ("wiki", ["title"]),
        "section": ("sections", ["title", "description"]),
    }

    structured = await _structured_search(db, query_text, limit)
    if structured is not None:
        return {kind: items for kind, items in structured.items() if kind in search_types and items}

    results = {}
    for content_type in search_types:
        if content_type not in collection_map:
            continue
        coll_name, fields = collection_map[content_type]
        collection = getattr(db, coll_name)

        # Draft pages are valid public results; only archived content is hidden.
        items = await _find_ranked_matches(
            collection, fields, query_text, limit, {"modules": 0},
            fuzzy=content_type in {"person", "team", "show", "city", "quiz"},
        )
        if content_type == "team":
            await attach_show_info(db, items)
        if items:
            results[content_type] = items

    return results


def _suggestion(item: dict, content_type: str, fields: list[str], query: str, order: int) -> dict:
    if content_type == 'section':
        path = item.get('full_path') or '#'
    elif content_type == 'team':
        path = team_url(item)
    elif content_type == 'show':
        path = f"/shows/{item.get('full_path') or item.get('slug') or item['_id']}"
    else:
        prefix = {'person': 'people', 'city': 'city', 'quiz': 'quizzes',
                  'article': 'articles', 'news': 'news'}.get(content_type, content_type)
        path = f"/{prefix}/{item.get('slug') or item['_id']}"

    media_key = {'person': 'photo', 'team': 'logo', 'show': 'poster',
                 'city': 'poster', 'quiz': 'cover_image', 'article': 'cover_image',
                 'news': 'cover_image'}.get(content_type)
    media = item.get(media_key) if media_key else None
    image = (media.get('thumbnail') or media.get('url')) if isinstance(media, dict) else media
    if content_type == 'team':
        context = (item.get('show') or {}).get('title') or (item.get('facts') or {}).get('Город') or 'КВН'
    elif content_type == 'person':
        context = ', '.join((item.get('bio') or {}).get('occupation') or [])
        context = context or (item.get('seo') or {}).get('meta_description') or ''
    elif content_type == 'show':
        context = 'Раздел шоу' if item.get('parent_id') else ''
    else:
        context = item.get('excerpt') or item.get('description') or ''
    context = re.sub(r'<[^>]+>', '', context)[:100].strip()
    title = next((item.get(field) for field in fields if field not in {'aliases', 'slug', 'full_path'}
                  and isinstance(item.get(field), str) and item.get(field)), item.get('title') or '')
    rank = _relevance_key(item, fields, query, order)
    entity = content_type in {'person', 'team', 'show', 'city', 'quiz'}
    tier = 0 if entity and rank[0] == 0 else 1 if rank[0] == 0 else 2 if entity else 3
    return {'id': str(item['_id']), 'title': title, 'type': content_type,
            'slug': item.get('slug'), 'path': path, 'image': image, 'context': context,
            '_relevance': (tier, *rank)}


@router.get("/search/autocomplete", response_model=list)
@limiter.limit("120/minute")  # Higher limit for autocomplete (fast typing)
async def search_autocomplete(
    request: Request,
    q: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=20)
):
    """Autocomplete by a literal fragment, globally ordered by relevance."""
    db = await get_db()
    query_text = _normalized_search_query(q)
    if len(query_text) < 2:
        raise HTTPException(status_code=422, detail="Поисковый запрос должен содержать минимум 2 символа")

    structured = await _structured_search(db, query_text, limit)
    if structured is not None:
        suggestions = []
        for content_type, items in structured.items():
            fields = ['full_name', 'title'] if content_type == 'person' else ['name', 'title']
            for item in items:
                suggestions.append(_suggestion(item, content_type, fields, query_text, 0))
        for item in suggestions:
            item.pop('_relevance')
        return suggestions[:limit]

    suggestions = []
    collections_config = [
        ("people", ["full_name", "title", "aliases", "slug"], "person"),
        ("teams", ["name", "title", "aliases", "slug"], "team"),
        ("shows", ["name", "title", "aliases", "slug", "full_path"], "show"),
        ("cities", ["name", "title", "aliases", "slug"], "city"),
        ("quizzes", ["title", "slug"], "quiz"),
        ("articles", ["title"], "article"),
        ("news", ["title"], "news"),
        ("sections", ["title"], "section"),
    ]

    for type_order, (coll_name, fields, content_type) in enumerate(collections_config):
        collection = getattr(db, coll_name)

        projection = {
            "_id": 1, "slug": 1, "full_path": 1, "show_id": 1,
            "photo": 1, "logo": 1, "poster": 1, "cover_image": 1,
            "facts": 1, "bio": 1, "seo": 1, "excerpt": 1, "parent_id": 1,
            **{field: 1 for field in fields},
        }
        items = await _find_ranked_matches(collection, fields, query_text, limit, projection,
                                           fuzzy=content_type in {'person', 'team', 'show', 'city', 'quiz'})

        if content_type == "team":
            await attach_show_info(db, items)
        suggestions.extend(_suggestion(item, content_type, fields, query_text, type_order) for item in items)

    suggestions.sort(key=lambda item: item["_relevance"])
    result = suggestions[:limit]
    for item in result:
        item.pop("_relevance")
    return result


@router.get("/search/by-tag/{tag}", response_model=dict)
async def search_by_tag(
    tag: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """Search all content by tag."""
    db = await get_db()

    results = {}
    total_count = 0

    collection_map = {
        "people": "person",
        "teams": "team",
        "shows": "show",
        "articles": "article",
        "news": "news",
        "wiki": "wiki",
        "quizzes": "quiz",
        "sections": "section",
    }

    for coll_name, content_type in collection_map.items():
        collection = getattr(db, coll_name)
        query = {"status": {"$ne": "archived"}, "tags": tag}
        count = await collection.count_documents(query)
        total_count += count
        if count > 0:
            cursor = collection.find(query, {"modules": 0}).sort("created_at", -1).limit(limit)
            items = await cursor.to_list(limit)
            if content_type == "team":
                await attach_show_info(db, items)
            results[content_type] = {"count": count, "items": items}

    return {"tag": tag, "total": total_count, "results": results, "skip": skip, "limit": limit}


# ---------------------------------------------------------------------------
#  Duplicate content
# ---------------------------------------------------------------------------

COLLECTION_MAP = {
    "person": "people", "people": "people",
    "team": "teams", "teams": "teams",
    "show": "shows", "shows": "shows",
    "article": "articles", "articles": "articles",
    "news": "news",
    "quiz": "quizzes", "quizzes": "quizzes",
    "wiki": "wiki",
    "kvn": "kvn",
    "section": "sections", "sections": "sections"
}


@router.post("/{content_type}/{id}/duplicate", response_model=dict)
async def duplicate_content(content_type: str, id: str):
    """Create a copy of a content page."""
    try:
        db = await get_db()

        collection_name = COLLECTION_MAP.get(content_type)
        if not collection_name:
            raise HTTPException(status_code=400, detail=f"Unknown content type: {content_type}")

        collection = getattr(db, collection_name)

        # Find original content
        if content_type == "kvn":
            original = await collection.find_one({"id": id})
            if not original:
                original = await collection.find_one({"_id": id})
        else:
            original = await collection.find_one({"_id": id})

        if not original:
            raise HTTPException(status_code=404, detail="Content not found")

        # Deep copy
        copy_data = copy_module.deepcopy(dict(original))
        copy_data.pop("_id", None)
        copy_data.pop("created_at", None)
        copy_data.pop("updated_at", None)
        copy_data.pop("views", None)
        copy_data = convert_objectids_to_strings(copy_data)

        # Generate unique slug
        base_slug = copy_data.get("slug", "")
        if not base_slug:
            raise HTTPException(status_code=400, detail="Original content has no slug")

        parent_path_for_slug = None
        if content_type in ["kvn", "section", "sections"]:
            parent_id = copy_data.get("parent_id")
            if parent_id:
                if content_type == "kvn":
                    parent_doc = await db.kvn.find_one({"id": parent_id})
                    if not parent_doc:
                        parent_doc = await db.kvn.find_one({"_id": parent_id})
                else:
                    parent_doc = await db.sections.find_one({"_id": parent_id})
                if parent_doc:
                    parent_path_for_slug = parent_doc.get("full_path", parent_doc.get("slug", ""))

        new_slug = await generate_unique_slug(collection_name, base_slug, parent_path_for_slug)
        copy_data["slug"] = new_slug

        now = datetime.now(timezone.utc).isoformat()
        copy_data["created_at"] = now
        copy_data["updated_at"] = now
        copy_data["views"] = 0

        # KVN-specific: new UUID id + clear children
        if content_type == "kvn":
            copy_data["id"] = str(uuid.uuid4())
            copy_data["child_kvn_ids"] = []

        result = await collection.insert_one(copy_data)

        # Update full_path for sections
        if content_type in ["section", "sections"]:
            from routes.sections import build_full_path
            parent_id = copy_data.get("parent_id")
            new_full_path, new_level = await build_full_path(parent_id, new_slug, db)
            await collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {"full_path": new_full_path, "level": new_level}}
            )

        # Update full_path for KVN
        if content_type == "kvn":
            parent_id = copy_data.get("parent_id")
            level = 0
            full_path = new_slug

            if parent_id:
                parent = await db.kvn.find_one({"id": parent_id})
                if not parent:
                    parent = await db.kvn.find_one({"_id": parent_id})
                if parent:
                    parent_level = parent.get("level", 0)
                    if parent_level >= 4:
                        level = 0
                        full_path = new_slug
                    else:
                        level = parent_level + 1
                        parent_path = parent.get("full_path", parent.get("slug", ""))
                        full_path = f"{parent_path}/{new_slug}"

            await collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {"full_path": full_path, "level": level}}
            )

            if parent_id:
                new_id = copy_data.get("id")
                if new_id:
                    parent_doc = await db.kvn.find_one({"id": parent_id})
                    if not parent_doc:
                        parent_doc = await db.kvn.find_one({"_id": parent_id})
                    if parent_doc:
                        await db.kvn.update_one(
                            {"_id": parent_doc["_id"]},
                            {"$addToSet": {"child_kvn_ids": new_id}}
                        )

        if "tags" in copy_data and copy_data["tags"]:
            await tag_service.sync_tags(copy_data["tags"])

        inserted_id_str = str(result.inserted_id)

        if content_type == "kvn":
            return {
                "id": copy_data.get("id") or inserted_id_str,
                "_id": inserted_id_str,
                "slug": new_slug,
                "message": "Content duplicated successfully"
            }
        return {"id": inserted_id_str, "slug": new_slug, "message": "Content duplicated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating {content_type} {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error duplicating content: {str(e)}")
