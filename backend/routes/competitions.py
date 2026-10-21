"""Турниры, сезоны и перекрёстные ссылки участников. Модель — services/competitions.py."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from models.competition import SeasonUpdate
from models.content import KVNUpdate
from pydantic import ValidationError
from services.season_editor import season_editor_data, apply_editor_update
from services.season_projection import retry_season_projection, public_season
from services.cache import cache_service
from models.season_import import SeasonImportRequest
from services.season_import import apply_import, preview_import
from services.competitions import (
    SHOW_KVN, apply_season_update, load_team_lookup, save_season, sync_kvn_pages, unresolved_participants, page_filter,
)
from services.show_teams import team_id_or_kvn_slug_query
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


async def _season_response(db, season):
    result = public_season(season)
    result.update(_season_counts(season), unresolved=unresolved_participants(season),
                  editor_data=season_editor_data(season))
    if season.get('page_collection') == 'kvn' and season.get('page_id'):
        page = await db.kvn.find_one(page_filter(season['page_id']), {'updated_at': 1})
        result['page_updated_at'] = (page or {}).get('updated_at')
    return result


def _invalidate_season_cache():
    cache_service.invalidate_kvn()
    cache_service.invalidate_kvn_children()
    cache_service.invalidate_team()
    cache_service.breadcrumbs.clear()


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
        summary = {k: v for k, v in public_season(season).items() if k not in _SEASON_SUMMARY_PROJECTION}
        summary.update(_season_counts(season))
        seasons.append(summary)
    return {**tournament, "seasons": seasons}


# ─── Сезоны ────────────────────────────────────────────────────────────────────

@router.post("/seasons/import/preview")
async def preview_season_import(data: SeasonImportRequest):
    return await preview_import(await get_db(), data.package)


@router.post("/seasons/import")
async def import_season(data: SeasonImportRequest):
    if not data.preview_token:
        raise HTTPException(422, "Сначала проверьте пакет сезона")
    return await apply_import(await get_db(), data.package, data.preview_token)

@router.get("/seasons/by-page/{page_id}")
async def get_season_by_page(page_id: str):
    db = await get_db()
    page = await db.kvn.find_one({'$or': [page_filter(page_id), {'id': page_id}]}, {'_id': 1})
    season = await db.seasons.find_one({'page_collection': 'kvn', 'page_id': str(page['_id']) if page else page_id})
    if not season:
        raise HTTPException(status_code=404, detail="Канонический сезон не найден")
    return await _season_response(db, season)


@router.get("/seasons/{season_id}")
async def get_season(season_id: str):
    db = await get_db()
    return await _season_response(db, await _get_season(db, season_id))


@router.put("/seasons/{season_id}")
async def update_season(season_id: str, data: SeasonUpdate):
    if "expected_updated_at" not in data.model_fields_set:
        raise HTTPException(409, "Версия сезона не передана. Обновите страницу.")
    db = await get_db()
    season = await _get_season(db, season_id)
    if data.editor_data is not None:
        canonical_fields = data.model_fields_set - {'editor_data', 'page_update', 'expected_updated_at', 'expected_page_updated_at'}
        if canonical_fields:
            raise HTTPException(422, 'Передайте editor_data либо поля канонического сезона')
        if season.get('page_collection') != 'kvn' or not season.get('page_id'):
            raise HTTPException(422, 'Этот редактор предназначен для страницы КВН')
        if 'expected_page_updated_at' not in data.model_fields_set:
            raise HTTPException(409, 'Версия страницы не передана. Обновите страницу.')
        page = await db.kvn.find_one(page_filter(season['page_id']))
        if not page:
            raise HTTPException(409, 'Страница сезона отсутствует')
        # Both entry points share validation, claims and the canonical write workflow.
        from routes.content_kvn import update_kvn
        try:
            page_request = KVNUpdate.model_validate({
                **(data.page_update or {}), 'season_data': data.editor_data,
                'expected_updated_at': data.expected_page_updated_at,
                'expected_season_updated_at': data.expected_updated_at,
            })
        except ValidationError as exc:
            raise HTTPException(422, 'Некорректные поля страницы сезона') from exc
        await update_kvn(page.get('id') or str(page['_id']), page_request)
        saved = await _get_season(db, season_id)
    else:
        if data.page_update is not None:
            raise HTTPException(422, 'page_update требует editor_data')
        update = data.model_dump(exclude_unset=True)
        expected = update.pop('expected_updated_at')
        update.pop('expected_page_updated_at', None)
        update.pop('editor_data', None)
        update.pop('page_update', None)
        season = apply_season_update(season, update, await load_team_lookup(db))
        saved = await save_season(db, season, write_page=True, expected_updated_at=expected)
    _invalidate_season_cache()
    return await _season_response(db, saved)


@router.post("/seasons/{season_id}/projections/retry")
async def retry_projection(season_id: str, data: SeasonUpdate):
    if data.model_fields_set != {'expected_updated_at'}:
        raise HTTPException(409, 'Для повтора нужна только версия сохранённого сезона')
    db = await get_db()
    saved = await retry_season_projection(db, season_id, data.expected_updated_at)
    _invalidate_season_cache()
    return await _season_response(db, saved)


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
    """Восстановить проекции из канонических сезонов, без обратной записи из страниц."""
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
    team = await db.teams.find_one(team_id_or_kvn_slug_query(id_or_slug), {"_id": 1, "slug": 1, "name": 1, "title": 1})
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
