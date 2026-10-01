"""Создание сезона через обычные CRUD/синхронизацию, без изменения существующих сезонов."""
import asyncio
import hashlib
import json
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from models.content import KVNCreate
from models.season_import import SeasonImport
from services.competitions import season_to_legacy, stable_id, stage_code, sync_from_kvn_page
from services.show_teams import KVN_ONLY
from utils.team_matcher import normalize_team_name

@asynccontextmanager
async def import_lock(db):
    """Общая короткая аренда для всех workers. Время обработки ограничено сроком аренды."""
    owner = str(uuid4())
    now = datetime.now(timezone.utc)
    try:
        await db.season_import_locks.update_one(
            {"_id": "kvn", "$or": [{"until": {"$lte": now}}, {"until": {"$exists": False}}]},
            {"$set": {"owner": owner, "until": now + timedelta(minutes=5)}}, upsert=True)
    except DuplicateKeyError:
        raise HTTPException(409, "Другой импорт сезона выполняется. Повторите проверку после его завершения.")
    try:
        async with asyncio.timeout(180):
            yield
    except TimeoutError:
        raise HTTPException(503, "Время импорта истекло. Проверьте пакет и повторите импорт.")
    finally:
        await db.season_import_locks.delete_one({"_id": "kvn", "owner": owner})


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def package_fingerprint(package: SeasonImport) -> str:
    payload = package.model_dump(mode="json")
    if not payload.get("editorial_notes"):
        payload.pop("editorial_notes", None)
    return digest(payload)


def match_teams(package: SeasonImport, existing: list[dict]) -> tuple[list[dict], list[str]]:
    by_name = defaultdict(dict)
    by_slug = {team["slug"]: team for team in existing}
    for team in existing:
        for name in [team.get("name"), team.get("title"), *(team.get("aliases") or [])]:
            if name:
                by_name[normalize_team_name(name)][str(team["_id"])] = team
    rows, errors = [], []
    used_ids = set()
    for incoming in package.teams:
        candidates = {}
        if incoming.existing_slug:
            team = by_slug.get(incoming.existing_slug)
            if team:
                candidates[str(team["_id"])] = team
            else:
                errors.append(f"{incoming.name}: команда КВН {incoming.existing_slug} не найдена")
        else:
            for name in [incoming.name, *incoming.aliases]:
                candidates.update(by_name.get(normalize_team_name(name), {}))
            if len(candidates) > 1 and incoming.city:
                in_city = {key: team for key, team in candidates.items()
                           if normalize_team_name((team.get("facts") or {}).get("Город") or team.get("city") or "")
                           == normalize_team_name(incoming.city)}
                if len(in_city) == 1:
                    candidates = in_city
        row = {"key": incoming.key, "name": incoming.name, "city": incoming.city, "action": "create"}
        if len(candidates) > 1:
            errors.append(f"{incoming.name}: несколько совпадений; укажите existing_slug")
            row["candidates"] = [{"slug": team["slug"], "name": team.get("name") or team.get("title")}
                                 for team in candidates.values()]
        elif candidates:
            team = next(iter(candidates.values()))
            team_id = str(team["_id"])
            if team.get("status") == "archived":
                errors.append(f"{incoming.name}: совпавшая команда находится в архиве")
            if team_id in used_ids:
                errors.append(f"{incoming.name}: одна карточка указана для двух участников")
            used_ids.add(team_id)
            row.update(action="link", team_id=team_id, slug=team["slug"],
                       existing_name=team.get("name") or team.get("title"))
            city = (team.get("facts") or {}).get("Город") or team.get("city") or ""
            if city and incoming.city and normalize_team_name(city) != normalize_team_name(incoming.city):
                row["warning"] = f"В карточке город {city}; в сезоне будет {incoming.city}"
        rows.append(row)
    return rows, errors


async def preview_import(db, package: SeasonImport) -> dict:
    league = await db.kvn.find_one({"full_path": {"$in": [f"kvn/{package.league_slug}", f"/kvn/{package.league_slug}"]}})
    if not league or league.get("status") == "archived":
        raise HTTPException(404, "Страница лиги не найдена или в архиве")
    existing = await db.teams.find(KVN_ONLY, {"_id": 1, "slug": 1, "name": 1, "title": 1,
                                           "aliases": 1, "facts": 1, "city": 1, "status": 1}).to_list(None)
    rows, errors = match_teams(package, existing)
    page = await db.kvn.find_one({"slug": package.slug})
    fingerprint = package_fingerprint(package)
    unchanged = bool(page and (page.get("season_data") or {}).get("import_source", {}).get("fingerprint") == fingerprint)
    if page and not unchanged:
        errors.append("Сезон с этим адресом уже существует. Измените его в редакторе; импорт не перезаписывает страницы.")
    token = digest({"package": fingerprint, "teams": rows, "page": str(page["_id"]) if page else None,
                    "league": str(league["_id"]), "errors": errors})
    return {"title": package.title, "path": f"kvn/{package.league_slug}/{package.slug}",
            "page_id": str(page["_id"]) if page else None, "unchanged": unchanged,
            "teams": rows, "errors": errors, "preview_token": token,
            "games_count": sum(len(stage.games) for stage in package.stages),
            "results_count": sum(len(game.results) for stage in package.stages for game in stage.games),
            "teams_to_create": sum(row["action"] == "create" for row in rows)}


def build_season_data(package: SeasonImport, refs: dict, league_name: str) -> dict:
    stages = []
    for stage in package.stages:
        games = []
        for game in stage.games:
            results = [{**refs[row.team_key], **row.model_dump(exclude={"team_key"})} for row in game.results]
            games.append({**game.model_dump(mode="json", exclude={"results"}), "results": results,
                          "id": stable_id(package.league_slug, package.slug, stage.order, game.order),
                          "host": game.host or package.host})
        stages.append({**stage.model_dump(exclude={"games"}), "games": games,
                       "id": stable_id(package.league_slug, package.slug, stage.order), "code": stage_code(stage.name)})
    season = {"tournament_slug": package.league_slug, "year": package.year, "number": package.number,
              "league_name": league_name, "intro_html": package.intro_html, "host": package.host,
              "editors": package.editors, "teams": list(refs.values()), "stages": stages,
              "winners": [refs[key] for key in package.winners],
              "extra": {"editorial_notes": package.editorial_notes,
                        "import_source": {"url": str(package.source_url), "as_of": package.as_of.isoformat(),
                                          "fingerprint": package_fingerprint(package)}}}
    return season_to_legacy(season)


async def apply_import(db, package: SeasonImport, preview_token: str) -> dict:
    # После ошибки повторный запуск связывает уже созданные команды.
    async with import_lock(db):
        preview = await preview_import(db, package)
        if preview["preview_token"] != preview_token:
            raise HTTPException(409, "Данные изменились после проверки. Проверьте пакет заново.")
        if preview["errors"]:
            raise HTTPException(422, "; ".join(preview["errors"]))
        if preview["unchanged"]:
            page = await db.kvn.find_one({"_id": preview["page_id"]})
            await sync_from_kvn_page(db, page)
            return {**preview, "created": False, "created_teams": []}
        # Используем тот же обработчик, что и «Команды → импорт списком».
        from routes.content_teams import BulkTeamCreateRequest, BulkTeamCreateRow, bulk_create_teams
        from routes.content_kvn import create_kvn

        missing = [row for row in preview["teams"] if row["action"] == "create"]
        created = await bulk_create_teams(BulkTeamCreateRequest(rows=[
            BulkTeamCreateRow(action="create", name=row["name"], city=row["city"]) for row in missing
        ])) if missing else {"created": []}
        created_by_key = {missing[row["index"]]["key"]: row for row in created["created"]}
        refs = {}
        for row in preview["teams"]:
            new = created_by_key.get(row["key"])
            refs[row["key"]] = {"team_id": new["id"] if new else row["team_id"],
                                "slug": new["slug"] if new else row["slug"],
                                "name": row["name"], "city": row["city"], "had_city": True}
        league = await db.kvn.find_one({"full_path": {"$in": [f"kvn/{package.league_slug}", f"/kvn/{package.league_slug}"]}})
        data = build_season_data(package, refs, league.get("name") or league.get("title"))
        result = await create_kvn(KVNCreate(title=package.title, name=package.title, slug=package.slug,
                                          parent_id=league.get("id") or str(league["_id"]),
                                          status=package.status, season_data=data,
                                          team_ids=[ref["team_id"] for ref in refs.values()]))
        return {**preview, "page_id": result["id"], "created": True, "created_teams": created["created"]}
