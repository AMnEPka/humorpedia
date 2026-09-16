"""Турниры, сезоны и перекрёстные ссылки участников. Модель — services/competitions.py."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from models.competition import SeasonUpdate
from services.competitions import (
    SHOW_KVN, apply_season_update, load_team_lookup, save_season, sync_kvn_pages, unresolved_participants,
)
from utils.auth import require_admin, require_editor_on_write
from utils.database import get_db

router = APIRouter(prefix="/competitions", tags=["competitions"], dependencies=[Depends(require_editor_on_write)])

# Поля сезона в списках (без этапов/игр)
_SEASON_SUMMARY_PROJECTION = {
    "stages": 0, "metadata": 0, "intro_html": 0, "description": 0, "extra": 0,
    "extra_sections": 0, "legacy_keys": 0,
}


def _season_counts(season: dict) -> dict:
    stages = season.get("stages") or []
    return {
        "stages_count": len(stages),
        "games_count": sum(len(s.get("games") or []) for s in stages),
        "teams_count": len(season.get("teams") or []),
    }


async def _get_tournament(db, show: str, slug: str) -> dict:
    tournament = await db.tournaments.find_one({"show": show, "slug": slug})
    if not tournament:
        raise HTTPException(status_code=404, detail="Турнир не найден")
    return tournament


async def _get_season(db, season_id: str) -> dict:
    season = await db.seasons.find_one({"_id": season_id})
    if not season:
        raise HTTPException(status_code=404, detail="Сезон не найден")
    return season


# ─── Турниры ───────────────────────────────────────────────────────────────────

@router.get("/tournaments")
async def list_tournaments(show: Optional[str] = None):
    db = await get_db()
    query = {"show": show} if show else {}
    items = await db.tournaments.find(query).sort([("show", 1), ("order", 1), ("title", 1)]).to_list(None)
    return {"items": items, "total": len(items)}


@router.get("/tournaments/{show}/{slug}")
async def get_tournament(show: str, slug: str):
    """Турнир и список его сезонов (без игр)."""
    db = await get_db()
    tournament = await _get_tournament(db, show, slug)
    seasons = []
    async for season in db.seasons.find({"tournament_id": tournament["_id"]}).sort([("year", 1), ("number", 1)]):
        summary = {k: v for k, v in season.items() if k not in _SEASON_SUMMARY_PROJECTION}
        summary.update(_season_counts(season))
        seasons.append(summary)
    return {**tournament, "seasons": seasons}


# ─── Сезоны ────────────────────────────────────────────────────────────────────

@router.get("/seasons/by-page/{page_id}")
async def get_season_by_page(page_id: str):
    db = await get_db()
    season = await db.seasons.find_one({"page_id": page_id})
    if not season:
        raise HTTPException(status_code=404, detail="Сезон не найден")
    return season


@router.get("/seasons/{season_id}")
async def get_season(season_id: str):
    db = await get_db()
    season = await _get_season(db, season_id)
    return {**season, **_season_counts(season), "unresolved": unresolved_participants(season)}


@router.put("/seasons/{season_id}")
async def update_season(season_id: str, data: SeasonUpdate):
    """
    Правка сезона. Для лиг КВН изменения записываются и в season_data страницы сезона,
    так что публичная страница и старый редактор видят их сразу.
    """
    db = await get_db()
    season = await _get_season(db, season_id)
    update = data.model_dump(exclude_unset=True)
    lookup = await load_team_lookup(db)
    season = apply_season_update(season, update, lookup)
    saved = await save_season(db, season, write_page=True)
    return {**saved, **_season_counts(saved), "unresolved": unresolved_participants(saved)}


@router.get("/unresolved")
async def list_unresolved(show: str = SHOW_KVN, tournament: Optional[str] = None):
    """Участники сезонов, не привязанные к командам/людям."""
    db = await get_db()
    query: dict = {"show": show}
    if tournament:
        query["tournament_slug"] = tournament
    items = []
    async for season in db.seasons.find(query).sort([("tournament_slug", 1), ("year", 1)]):
        for entry in unresolved_participants(season):
            items.append({
                "season_id": season["_id"], "season_title": season.get("title"),
                "season_path": season.get("page_path"), "tournament_slug": season.get("tournament_slug"),
                **entry,
            })
    return {"items": items, "total": len(items)}


@router.post("/sync", dependencies=[Depends(require_admin)])
async def sync_from_pages():
    """Пересинхронизировать все сезоны из season_data страниц КВН."""
    db = await get_db()
    return await sync_kvn_pages(db)


# ─── Перекрёстные ссылки ───────────────────────────────────────────────────────

@router.get("/teams/{id_or_slug}/participations")
async def team_participations(id_or_slug: str, games: bool = Query(False, description="Добавить результаты по играм")):
    """
    Участие команды в сезонах всех турниров: итог в сезоне (kind=season),
    при games=true — ещё и результаты по играм.
    """
    db = await get_db()
    team = await db.teams.find_one({"$or": [{"_id": id_or_slug}, {"slug": id_or_slug}]}, {"_id": 1, "slug": 1, "name": 1, "title": 1})
    if not team:
        raise HTTPException(status_code=404, detail="Команда не найдена")

    kinds = ["season", "game"] if games else ["season"]
    rows = await db.participations.find(
        {"team_id": team["_id"], "kind": {"$in": kinds}, "season_status": {"$ne": "draft"}}
    ).sort([("season_year", -1), ("stage_order", 1), ("game_order", 1)]).to_list(None)

    tournaments = {t["_id"]: t for t in await db.tournaments.find(
        {"_id": {"$in": list({r["tournament_id"] for r in rows})}},
        {"slug": 1, "show": 1, "title": 1, "short_title": 1, "page_path": 1, "order": 1},
    ).to_list(None)}

    seasons = [r for r in rows if r["kind"] == "season"]
    games_by_season: dict = {}
    for row in rows:
        if row["kind"] == "game":
            games_by_season.setdefault(row["season_id"], []).append(row)
    for season in seasons:
        season["tournament"] = tournaments.get(season["tournament_id"])
        if games:
            season["games"] = games_by_season.get(season["season_id"], [])

    return {
        "team": {"id": team["_id"], "slug": team.get("slug"), "name": team.get("name") or team.get("title")},
        "seasons": seasons,
        "total": len(seasons),
    }
