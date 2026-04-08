"""
Redirect system: поддержка старых URL humorpedia.ru → новые URL.
Каждый документ может иметь поле old_urls: list[str] — массив старых путей.
API ищет по всем коллекциям и возвращает новый путь для редиректа.
"""

import os
import re
from fastapi import APIRouter, Query
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/redirects", tags=["redirects"])

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URL)
db = client.humorpedia


# ─── lookup ────────────────────────────────────────────────────────────────────
@router.get("/lookup")
async def lookup_redirect(path: str = Query(..., description="Old URL path (e.g. /kvn/team/negoden.html)")):
    """
    Ищет old_url в коллекциях kvn, teams, people, shows, articles, news.
    Возвращает { found: true, new_path: "/kvn/teams/negoden" } или { found: false }.
    """
    # Нормализуем путь
    clean = path.strip()
    if not clean.startswith("/"):
        clean = "/" + clean
    # Убираем trailing slash кроме корня
    if clean != "/" and clean.endswith("/"):
        clean = clean.rstrip("/")

    # Поиск по коллекциям: (collection_name, new_path_builder)
    search_targets = [
        ("kvn",      lambda doc: "/" + doc.get("full_path", doc.get("slug", ""))),
        ("teams",    lambda doc: "/kvn/teams/" + doc.get("slug", "")),
        ("people",   lambda doc: "/people/" + doc.get("slug", "")),
        ("shows",    lambda doc: "/shows/" + doc.get("slug", "")),
        ("articles", lambda doc: "/articles/" + doc.get("slug", "")),
        ("news",     lambda doc: "/news/" + doc.get("slug", "")),
    ]

    for coll_name, path_builder in search_targets:
        doc = await db[coll_name].find_one(
            {"old_urls": clean},
            {"slug": 1, "full_path": 1}
        )
        if doc:
            new_path = path_builder(doc)
            return {"found": True, "new_path": new_path, "collection": coll_name}

    # Фоллбэк: попробуем известные паттерны без обращения к БД
    fallback = _try_pattern_redirect(clean)
    if fallback:
        return {"found": True, "new_path": fallback, "collection": "pattern"}

    return {"found": False}


def _try_pattern_redirect(path: str) -> str | None:
    """Пытаемся распознать старый URL по паттерну (без запроса в БД)."""
    
    # /kvn/team/{slug}.html → /kvn/teams/{slug}
    m = re.match(r"^/kvn/team/([\w-]+)\.html$", path)
    if m:
        return f"/kvn/teams/{m.group(1)}"

    # /team/{slug}.html → /kvn/teams/{slug} (альтернативный путь на старом сайте)
    m = re.match(r"^/team/([\w-]+)\.html$", path)
    if m:
        return f"/kvn/teams/{m.group(1)}"

    # /kvn/vysshaya-liga/{year}.html → /kvn/vl-kvn/vl-{year}
    m = re.match(r"^/kvn/vysshaya-liga/(\d{4})\.html$", path)
    if m:
        return f"/kvn/vl-kvn/vl-{m.group(1)}"
    # /kvn/vysshaya-liga → /kvn/vl-kvn
    if path == "/kvn/vysshaya-liga":
        return "/kvn/vl-kvn"

    # /kvn/pervaya-liga/{year}.html → /kvn/1l-kvn/1l-{year}
    m = re.match(r"^/kvn/pervaya-liga/(\d{4})\.html$", path)
    if m:
        return f"/kvn/1l-kvn/1l-{m.group(1)}"
    if path in ("/kvn/pervaya-liga", "/kvn/pervaya-liga/"):
        return "/kvn/1l-kvn"

    # /kvn/mezhdunarodnaya-liga/{year}.html → /kvn/ml-kvn/ml-{year}
    m = re.match(r"^/kvn/mezhdunarodnaya-liga/(\d{4})\.html$", path)
    if m:
        return f"/kvn/ml-kvn/ml-{m.group(1)}"
    if path == "/kvn/mezhdunarodnaya-liga":
        return "/kvn/ml-kvn"

    # /kvn/premier-liga/{year}.html → /kvn/premier-liga/pl-{year}
    m = re.match(r"^/kvn/premier-liga/(\d{4})\.html$", path)
    if m:
        return f"/kvn/premier-liga/pl-{m.group(1)}"

    # /kvn/vul.html → /kvn/vul
    if path == "/kvn/vul.html":
        return "/kvn/vul"
    # /kvn/vul/{year}.html → /kvn/vul/vul-{year}
    m = re.match(r"^/kvn/vul/(\d{4})\.html$", path)
    if m:
        return f"/kvn/vul/vul-{m.group(1)}"

    # /kvn/league/{slug}.html → /kvn/league/{slug}
    m = re.match(r"^/kvn/league/([\w-]+)\.html$", path)
    if m:
        return f"/kvn/league/{m.group(1)}"

    # /people/{slug}.html → /people/{slug}
    m = re.match(r"^/people/([\w-]+)\.html$", path)
    if m:
        return f"/people/{m.group(1)}"

    # /articles/{slug}.html → /articles/{slug}
    m = re.match(r"^/articles/([\w-]+)\.html$", path)
    if m:
        return f"/articles/{m.group(1)}"

    # /novosti/{slug}.html → /novosti/{slug}
    m = re.match(r"^/novosti/([\w-]+)\.html$", path)
    if m:
        return f"/novosti/{m.group(1)}"

    # /kvn/{slug}.html → /kvn/{slug}
    m = re.match(r"^/kvn/([\w-]+)\.html$", path)
    if m:
        return f"/kvn/{m.group(1)}"

    # Убираем .html в конце
    if path.endswith(".html"):
        return path[:-5]

    return None


# ─── admin: update old_urls ───────────────────────────────────────────────────
@router.put("/{collection}/{doc_id}/old-urls")
async def update_old_urls(collection: str, doc_id: str, body: dict):
    """Обновляет old_urls для документа."""
    allowed = {"kvn", "teams", "people", "shows", "articles", "news"}
    if collection not in allowed:
        return {"error": f"Collection {collection} not supported"}

    old_urls = body.get("old_urls", [])
    # Нормализуем пути
    normalized = []
    for url in old_urls:
        url = url.strip()
        if not url:
            continue
        if not url.startswith("/"):
            url = "/" + url
        if url != "/" and url.endswith("/"):
            url = url.rstrip("/")
        normalized.append(url)

    result = await db[collection].update_one(
        {"id": doc_id},
        {"$set": {"old_urls": normalized}}
    )
    if result.matched_count == 0:
        return {"error": "Document not found"}
    return {"success": True, "old_urls": normalized}


# ─── auto-populate ────────────────────────────────────────────────────────────
@router.post("/auto-populate")
async def auto_populate_old_urls():
    """
    Автоматически заполняет old_urls для всех документов в kvn, teams, people
    на основе известных паттернов старого сайта humorpedia.ru.
    """
    stats = {"kvn": 0, "teams": 0, "people": 0}

    # ─── Teams ────────────────────────────────────────────────────────────
    async for team in db.teams.find({}, {"id": 1, "_id": 1, "slug": 1, "old_urls": 1}):
        slug = team.get("slug", "")
        if not slug:
            continue
        doc_id = team.get("id") or str(team.get("_id", ""))
        old_urls = set(team.get("old_urls") or [])
        # Основной паттерн: /kvn/team/{slug}.html
        old_urls.add(f"/kvn/team/{slug}.html")
        old_urls_list = sorted(old_urls)
        await db.teams.update_one({"_id": team["_id"]}, {"$set": {"old_urls": old_urls_list}})
        stats["teams"] += 1

    # ─── KVN pages ────────────────────────────────────────────────────────
    # Маппинг league slug → old league name
    league_old_names = {
        "vl-kvn": "vysshaya-liga",
        "1l-kvn": "pervaya-liga",
        "ml-kvn": "mezhdunarodnaya-liga",
        "premier-liga": "premier-liga",
        "vul": "vul",
    }

    async for kvn_doc in db.kvn.find({}, {"id": 1, "_id": 1, "slug": 1, "full_path": 1, "season_data": 1, "old_urls": 1, "parent_id": 1}):
        slug = kvn_doc.get("slug", "")
        full_path = kvn_doc.get("full_path", "")
        if not slug:
            continue

        old_urls = set(kvn_doc.get("old_urls") or [])
        season_data = kvn_doc.get("season_data") or {}
        league_slug = season_data.get("league_slug", "")

        # League root pages
        if slug in league_old_names:
            old_name = league_old_names[slug]
            if slug == "vul":
                old_urls.add("/kvn/vul.html")
                old_urls.add("/kvn/vul")
            elif slug == "1l-kvn":
                old_urls.add(f"/kvn/{old_name}")
                old_urls.add(f"/kvn/{old_name}/")
            elif slug == "vl-kvn":
                old_urls.add(f"/kvn/{old_name}")
            elif slug == "ml-kvn":
                old_urls.add(f"/kvn/{old_name}")
            elif slug == "premier-liga":
                # premier-liga slug is the same
                pass

        # Season pages: /kvn/{old_league_name}/{year}.html
        elif league_slug and league_slug in league_old_names:
            year = season_data.get("year")
            old_name = league_old_names[league_slug]
            if year:
                if league_slug == "vul":
                    old_urls.add(f"/kvn/vul/{year}.html")
                else:
                    old_urls.add(f"/kvn/{old_name}/{year}.html")

        # Generic KVN pages: /kvn/{slug}.html
        if full_path and full_path.startswith("kvn/"):
            parts = full_path.split("/")
            if len(parts) == 2:
                # e.g., kvn/letniy → /kvn/letniy.html
                old_urls.add(f"/kvn/{slug}.html")

        if old_urls:
            old_urls_list = sorted(old_urls)
            await db.kvn.update_one({"_id": kvn_doc["_id"]}, {"$set": {"old_urls": old_urls_list}})
            stats["kvn"] += 1

    # ─── People ───────────────────────────────────────────────────────────
    async for person in db.people.find({}, {"id": 1, "_id": 1, "slug": 1, "old_urls": 1}):
        slug = person.get("slug", "")
        if not slug:
            continue
        old_urls = set(person.get("old_urls") or [])
        old_urls.add(f"/people/{slug}.html")
        old_urls_list = sorted(old_urls)
        await db.people.update_one({"_id": person["_id"]}, {"$set": {"old_urls": old_urls_list}})
        stats["people"] += 1

    # Создаём индексы для быстрого поиска
    for coll_name in ["kvn", "teams", "people", "shows", "articles", "news"]:
        await db[coll_name].create_index("old_urls")

    return {"success": True, "stats": stats}
