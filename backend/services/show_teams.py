"""
Команды шоу (не КВН): адреса, привязка к шоу, подписи.

Команда КВН: `show_id` пустой, адрес `/kvn/teams/{slug}`, slug уникален среди команд КВН.
Команда шоу: `show_id` = `_id` шоу, `full_path` = `{full_path шоу}/teams/{slug}`, адрес `/shows/{full_path}`;
slug уникален в пределах шоу («Союз» есть и в КВН, и в «Звёздах»), `team_type` = slug корневого шоу.

Поиск команды по одному slug (старые API, сезоны КВН) — только среди команд КВН: `kvn_team_query(slug)`.
"""
from __future__ import annotations

from typing import Iterable, Optional

from fastapi import HTTPException

TEAMS_SEGMENT = "teams"
KVN_TEAM_TYPE = "kvn"
# у команд КВН show_id не хранится или null — оба варианта
KVN_ONLY = {"show_id": None}


def kvn_team_query(slug: str) -> dict:
    return {"slug": slug, **KVN_ONLY}


def team_id_or_kvn_slug_query(value: str) -> dict:
    """`_id` любой команды или slug команды КВН."""
    return {"$or": [{"_id": value}, kvn_team_query(value)]}


def team_full_path(show: dict, slug: str) -> str:
    return f"{(show.get('full_path') or show['slug']).strip('/')}/{TEAMS_SEGMENT}/{slug}"


def team_url(doc: dict) -> str:
    """Адрес страницы команды на сайте. Нужны поля slug, show_id, full_path
    (у части старых команд КВН full_path = slug — это не адрес шоу)."""
    if doc.get("show_id") and doc.get("full_path"):
        return "/shows/" + doc["full_path"].strip("/")
    return f"/kvn/teams/{doc.get('slug', '')}"


def split_team_path(path: str) -> Optional[tuple]:
    """«liga-gorodov/teams/eto-oni» → («liga-gorodov», «eto-oni»); иначе None."""
    parts = (path or "").strip("/").split("/")
    if len(parts) >= 3 and parts[-2] == TEAMS_SEGMENT and parts[-1]:
        return "/".join(parts[:-2]), parts[-1]
    return None


async def root_show(db, show: dict) -> dict:
    current = show
    for _ in range(10):
        if not current.get("parent_id"):
            return current
        parent = await db.shows.find_one({"_id": current["parent_id"]})
        if not parent:
            return current
        current = parent
    return current


async def get_team_show(db, show_id: Optional[str]) -> Optional[dict]:
    if not show_id:
        return None
    show = await db.shows.find_one({"_id": show_id}, {"title": 1, "name": 1, "slug": 1, "full_path": 1, "parent_id": 1})
    if not show:
        raise HTTPException(status_code=400, detail="Шоу команды не найдено")
    if not show.get("full_path") and not show.get("slug"):
        raise HTTPException(status_code=400, detail="У шоу не задан адрес")
    return show


async def check_team_slug_free(db, slug: str, show: Optional[dict], exclude_id: Optional[str] = None) -> None:
    """slug уникален среди команд своего шоу (КВН — среди команд КВН); адрес не должен совпадать со страницей шоу."""
    query = {"slug": slug, "show_id": show["_id"] if show else None}
    if exclude_id:
        query["_id"] = {"$ne": exclude_id}
    if await db.teams.find_one(query, {"_id": 1}):
        where = f"в шоу «{show.get('title')}»" if show else "среди команд КВН"
        raise HTTPException(status_code=400, detail=f"Команда с адресом «{slug}» уже есть {where}")
    if show and await db.shows.find_one({"full_path": team_full_path(show, slug)}, {"_id": 1}):
        raise HTTPException(status_code=400, detail=f"Адрес /shows/{team_full_path(show, slug)} занят страницей шоу")


async def team_placement(db, show: Optional[dict], slug: str) -> dict:
    """Поля привязки команды к шоу для записи в документ."""
    if not show:
        return {"show_id": None, "full_path": None}
    root = await root_show(db, show)
    return {"show_id": show["_id"], "full_path": team_full_path(show, slug), "team_type": root.get("slug") or KVN_TEAM_TYPE}


async def attach_show_info(db, items: Iterable[dict]) -> None:
    """Добавить командам шоу `show: {id, title, full_path}` и `url` (для поиска, списков, страниц людей)."""
    items = [i for i in items if isinstance(i, dict)]
    show_ids = {i["show_id"] for i in items if i.get("show_id")}
    shows = {}
    if show_ids:
        async for s in db.shows.find({"_id": {"$in": list(show_ids)}}, {"title": 1, "name": 1, "full_path": 1, "slug": 1}):
            shows[s["_id"]] = {"id": s["_id"], "title": s.get("title") or s.get("name"),
                               "full_path": s.get("full_path") or s.get("slug")}
    for item in items:
        if item.get("show_id") and item["show_id"] in shows:
            item["show"] = shows[item["show_id"]]
        item["url"] = team_url(item)


async def move_show_teams(db, show_id: str, show_full_path: str) -> None:
    """После смены адреса шоу — пересчитать адреса его команд."""
    async for team in db.teams.find({"show_id": show_id}, {"slug": 1}):
        await db.teams.update_one(
            {"_id": team["_id"]},
            {"$set": {"full_path": f"{show_full_path.strip('/')}/{TEAMS_SEGMENT}/{team['slug']}"}},
        )


# ─── Та же команда в других шоу (related_team_ids) ────────────────────────────

async def sync_related_teams(db, team_id: str, new_ids, old_ids=()) -> list:
    """Связь двусторонняя: добавленным командам дописать team_id, у убранных — удалить. Возвращает очищенный список."""
    new_ids = [i for i in dict.fromkeys(new_ids or []) if i and i != team_id]
    existing = {t["_id"] async for t in db.teams.find({"_id": {"$in": new_ids}}, {"_id": 1})}
    new_ids = [i for i in new_ids if i in existing]
    added = set(new_ids) - set(old_ids or [])
    removed = set(old_ids or []) - set(new_ids)
    if added:
        await db.teams.update_many({"_id": {"$in": list(added)}}, {"$addToSet": {"related_team_ids": team_id}})
    if removed:
        await db.teams.update_many({"_id": {"$in": list(removed)}}, {"$pull": {"related_team_ids": team_id}})
    return new_ids


async def attach_related_teams(db, team: dict, public: bool = True) -> None:
    """`related_teams`: [{id, name, url, show, status}] для страницы команды (кроме архивных)."""
    ids = team.get("related_team_ids") or []
    query = {"_id": {"$in": ids}}
    if public:
        query["status"] = {"$ne": "archived"}
    items = await db.teams.find(query, {"name": 1, "title": 1, "slug": 1, "show_id": 1, "full_path": 1, "status": 1,
                                        "facts": 1}).to_list(None)
    await attach_show_info(db, items)
    order = {i: n for n, i in enumerate(ids)}
    team["related_teams"] = [
        {"id": t["_id"], "name": t.get("name") or t.get("title"), "url": t["url"], "show": t.get("show"),
         "status": t.get("status"), "city": (t.get("facts") or {}).get("Город")}
        for t in sorted(items, key=lambda t: order.get(t["_id"], 0))
    ]
