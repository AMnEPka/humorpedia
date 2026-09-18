"""
Модель соревнований: турнир → сезон → этап → игра → результат участника.

Коллекции:
- tournaments     — турнир/лига/проект (Высшая лига КВН, ИГРА, …); participant_type: team | person
- seasons         — сезон турнира: список команд, победители, этапы, игры, результаты
- participations  — производная таблица для перекрёстных ссылок, пересобирается при сохранении сезона:
                    kind="season" — итог участника в сезоне, kind="game" — результат в конкретной игре

Переходный период (этапы 1–3): публичные страницы и старый редактор работают с kvn.season_data.
Источник истины — seasons; синхронизация в обе стороны идёт через save_season():
- PUT страницы КВН с season_data → sync_from_kvn_page() → seasons + participations;
- PUT /api/competitions/seasons/{id} → seasons + participations + запись season_data обратно в страницу.

Функции без БД (legacy_to_season, season_to_legacy, build_participations) покрыты тестами.
"""
from __future__ import annotations

import copy
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from bson import ObjectId

from services.memberships import PersonLookup, load_person_lookup, name_key
from services.show_teams import KVN_ONLY

logger = logging.getLogger(__name__)

SHOW_KVN = "kvn"
PARTICIPANT_TEAM = "team"
PARTICIPANT_PERSON = "person"

# Пространство имён для детерминированных UUID (повторная миграция не плодит дубликаты)
_NAMESPACE = uuid.UUID("5f0e3c1a-7b8d-4c2e-9a41-6d1f2b3c4e5f")

# Поля season_data, которые вычисляются при выдаче страницы и не хранятся в сезоне
_LEGACY_COMPUTED_KEYS = {"prev_season", "next_season"}

# Известные поля — остальное сохраняется в extra и возвращается при обратной конвертации
_SEASON_KNOWN = {
    "league_slug", "league_name", "year", "season_number", "intro_html", "description",
    "metadata", "hosts", "host", "editors", "jury", "extra_sections", "late_joined_teams",
    "all_teams", "winners", "stages",
} | _LEGACY_COMPUTED_KEYS
_STAGE_KNOWN = {"name", "order", "comment", "notes", "additional_teams", "additional_notes", "games"}
_GAME_KNOWN = {"id", "name", "order", "date", "date_raw", "host", "jury", "contests", "notes", "is_cancelled", "teams"}
_RESULT_KNOWN = {"team_id", "team_slug", "team_name", "city", "place", "total", "scores", "passed", "is_winner", "is_additional"}
_TEAM_REF_KNOWN = {"slug", "name", "city"}

KVN_LEAGUE_ORDER = {"vl-kvn": 10, "premier-liga": 20, "1l-kvn": 30, "ml-kvn": 40, "vul": 50}


def stable_id(*parts: Any) -> str:
    return str(uuid.uuid5(_NAMESPACE, ":".join(str(p) for p in parts)))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Нормализация ──────────────────────────────────────────────────────────────

def stage_code(stage_name: str) -> str:
    """'1/8 финала' → '1/8', 'Полуфинал' → '1/2', 'Финал' → 'final', прочее → ''."""
    if not stage_name:
        return ""
    s = stage_name.strip().lower()
    m = re.search(r"(\d+)\s*/\s*(\d+)", s)
    if m:
        if "+" in s:  # комбинированный этап («1/8 + 1/4 финала»)
            return ""
        return f"{m.group(1)}/{m.group(2)}"
    if "утешител" in s:
        return "consolation"
    if "финал" in s:
        return "1/2" if "полу" in s else "final"
    return ""


def year_from_text(text: str) -> Optional[int]:
    m = re.search(r"(19|20)\d{2}", text or "")
    return int(m.group(0)) if m else None


def to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def to_number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _extra(source: dict, known: set) -> dict:
    return {k: copy.deepcopy(v) for k, v in source.items() if k not in known}


class TeamLookup:
    """Сопоставление ссылок на команды из данных сезона с коллекцией teams."""

    def __init__(self, teams: Iterable[dict] = ()):
        self.by_slug: dict[str, str] = {}
        self.slug_by_id: dict[str, str] = {}
        self.ids: set[str] = set()
        for team in teams:
            team_id = str(team["_id"])
            self.ids.add(team_id)
            if team.get("slug"):
                self.by_slug[team["slug"]] = team_id
                self.slug_by_id[team_id] = team["slug"]

    def slug_for(self, team_id: str) -> Optional[str]:
        return self.slug_by_id.get(team_id)

    def resolve(self, slug: str = "", team_id: str = "") -> Optional[str]:
        if team_id and team_id in self.ids:
            return team_id
        if slug and slug in self.by_slug:
            return self.by_slug[slug]
        return None


def _team_ref(raw: Any, lookup: TeamLookup) -> dict:
    """Команда в списке сезона/победителях: строка (старый формат) или {slug, name, city}."""
    if isinstance(raw, str):
        raw = {"slug": raw, "name": raw}
    raw = raw or {}
    slug = (raw.get("slug") or "").strip()
    return {
        "team_id": lookup.resolve(slug=slug),
        "slug": slug,
        "name": raw.get("name") or slug,
        "city": raw.get("city") or "",
        "had_city": "city" in raw,
        "extra": _extra(raw, _TEAM_REF_KNOWN),
    }


# ─── season_data (страница КВН) → сезон ────────────────────────────────────────

def legacy_to_season(page: dict, tournament: dict, lookup: TeamLookup) -> dict:
    """Построить документ сезона из страницы КВН с season_data. Без обращений к БД."""
    sd = page.get("season_data") or {}
    page_id = str(page["_id"])
    season_id = stable_id("kvn-page", page_id)

    year = to_int(sd.get("year")) or year_from_text(page.get("slug", "")) or year_from_text(page.get("full_path", ""))

    stages = []
    used_game_ids: set = set()
    for stage_index, raw_stage in enumerate(sd.get("stages") or []):
        games = []
        for game_index, raw_game in enumerate(raw_stage.get("games") or []):
            # id игры в данных бывает скопирован между этапами — внутренний id делаем уникальным,
            # исходный храним в legacy_id и возвращаем при обратной конвертации
            legacy_id = raw_game.get("id")
            game_id = legacy_id if legacy_id and legacy_id not in used_game_ids else stable_id(season_id, "game", stage_index, game_index)
            used_game_ids.add(game_id)
            results = []
            for raw in raw_game.get("teams") or []:
                slug = (raw.get("team_slug") or "").strip()
                results.append({
                    "team_id": lookup.resolve(slug=slug, team_id=raw.get("team_id") or ""),
                    "person_id": None,
                    "slug": slug,
                    "name": raw.get("team_name") or slug,
                    "city": raw.get("city") or "",
                    "place": to_int(raw.get("place")),
                    "total": to_number(raw.get("total")),
                    "scores": copy.deepcopy(raw.get("scores") or {}),
                    "passed": bool(raw.get("passed")),
                    "is_winner": bool(raw.get("is_winner")),
                    "is_additional": bool(raw.get("is_additional")),
                    "legacy_team_id": raw.get("team_id"),
                    "extra": _extra(raw, _RESULT_KNOWN),
                })
            games.append({
                "id": game_id,
                "had_legacy_id": "id" in raw_game,
                "legacy_id": legacy_id,
                "name": raw_game.get("name") or "",
                "order": to_number(raw_game.get("order")) if raw_game.get("order") is not None else game_index + 1,
                "date": raw_game.get("date") or "",
                "date_raw": raw_game.get("date_raw"),
                "host": raw_game.get("host") or "",
                "jury": list(raw_game.get("jury") or []),
                "contests": list(raw_game.get("contests") or []),
                "notes": raw_game.get("notes") or "",
                "is_cancelled": raw_game.get("is_cancelled"),
                "results": results,
                "extra": _extra(raw_game, _GAME_KNOWN),
            })
        name = raw_stage.get("name") or ""
        stages.append({
            "id": stable_id(season_id, "stage", stage_index),
            "name": name,
            "code": stage_code(name),
            # order бывает дробным: 2.5 — утешительный этап между 1/4 и 1/2
            "order": to_number(raw_stage.get("order")) if raw_stage.get("order") is not None else stage_index + 1,
            "comment": raw_stage.get("comment") or "",
            "notes": raw_stage.get("notes") or "",
            "additional_teams": list(raw_stage.get("additional_teams") or []),
            "additional_notes": raw_stage.get("additional_notes") or "",
            "games": games,
            "extra": _extra(raw_stage, _STAGE_KNOWN),
        })

    return {
        "_id": season_id,
        "tournament_id": tournament["_id"],
        "tournament_slug": tournament["slug"],
        "show": tournament.get("show", SHOW_KVN),
        "participant_type": tournament.get("participant_type", PARTICIPANT_TEAM),
        "title": page.get("title") or page.get("name") or "",
        "slug": page.get("slug") or "",
        "year": year,
        "number": to_int(sd.get("season_number")),
        "page_collection": "kvn",
        "page_id": page_id,
        "page_path": (page.get("full_path") or "").lstrip("/"),
        "status": page.get("status") or "draft",
        "league_name": sd.get("league_name"),
        "intro_html": sd.get("intro_html"),
        "description": sd.get("description"),
        "metadata": copy.deepcopy(sd.get("metadata")) if "metadata" in sd else None,
        "hosts": copy.deepcopy(sd.get("hosts")) if "hosts" in sd else None,
        "host": sd.get("host"),
        "editors": copy.deepcopy(sd.get("editors")) if "editors" in sd else None,
        "jury": copy.deepcopy(sd.get("jury")) if "jury" in sd else None,
        "extra_sections": copy.deepcopy(sd.get("extra_sections")) if "extra_sections" in sd else None,
        "late_joined_teams": copy.deepcopy(sd.get("late_joined_teams")) if "late_joined_teams" in sd else None,
        "teams": [_team_ref(t, lookup) for t in sd.get("all_teams") or []],
        "winners": [_team_ref(t, lookup) for t in sd.get("winners") or []],
        "stages": stages,
        "legacy_keys": sorted(k for k in sd.keys() if k not in _LEGACY_COMPUTED_KEYS),
        "extra": _extra(sd, _SEASON_KNOWN),
    }


# ─── сезон → season_data (для страниц и старого редактора) ─────────────────────

def _legacy_team_ref(ref: dict) -> dict:
    out = {"slug": ref.get("slug") or "", "name": ref.get("name") or ""}
    if ref.get("city") or ref.get("had_city"):
        out["city"] = ref.get("city") or ""
    out.update(ref.get("extra") or {})
    return out


def season_to_legacy(season: dict, tournament_slug: Optional[str] = None) -> dict:
    """Обратная конвертация в формат season_data. Поля, которых не было в исходнике, не добавляются."""
    legacy_keys = set(season.get("legacy_keys") or [])

    def put(target: dict, key: str, value: Any, always: bool = False):
        if always or key in legacy_keys or value not in (None, "", [], {}):
            target[key] = value

    sd: dict = {}
    put(sd, "league_slug", tournament_slug or season.get("tournament_slug"), always=True)
    put(sd, "league_name", season.get("league_name"))
    put(sd, "year", season.get("year"), always=True)
    put(sd, "season_number", season.get("number"))
    for key in ("intro_html", "description", "metadata", "hosts", "host", "editors", "jury",
                "extra_sections", "late_joined_teams"):
        put(sd, key, season.get(key))
    sd["all_teams"] = [_legacy_team_ref(t) for t in season.get("teams") or []]
    sd["winners"] = [_legacy_team_ref(t) for t in season.get("winners") or []]

    stages = []
    for stage in season.get("stages") or []:
        games = []
        for game in stage.get("games") or []:
            teams = []
            for r in game.get("results") or []:
                entry = {
                    "team_slug": r.get("slug") or "",
                    "team_name": r.get("name") or "",
                    "place": r.get("place"),
                    "total": r.get("total"),
                    "scores": copy.deepcopy(r.get("scores") or {}),
                    "passed": bool(r.get("passed")),
                    "is_winner": bool(r.get("is_winner")),
                    "is_additional": bool(r.get("is_additional")),
                    "city": r.get("city") or "",
                }
                if r.get("legacy_team_id") is not None:
                    entry["team_id"] = r["legacy_team_id"]
                entry.update(r.get("extra") or {})
                teams.append(entry)
            legacy_game = {
                "name": game.get("name") or "",
                "order": game.get("order"),
                "date": game.get("date") or "",
                "contests": list(game.get("contests") or []),
                "jury": list(game.get("jury") or []),
                "host": game.get("host") or "",
                "notes": game.get("notes") or "",
                "teams": teams,
            }
            if game.get("had_legacy_id", True):  # старые игры — исходный id, новые — внутренний
                legacy_game["id"] = game["legacy_id"] if game.get("legacy_id") is not None else game.get("id")
            if game.get("date_raw") is not None:
                legacy_game["date_raw"] = game["date_raw"]
            if game.get("is_cancelled") is not None:
                legacy_game["is_cancelled"] = game["is_cancelled"]
            legacy_game.update(game.get("extra") or {})
            games.append(legacy_game)
        legacy_stage = {
            "name": stage.get("name") or "",
            "order": stage.get("order"),
            "notes": stage.get("notes") or "",
            "additional_teams": list(stage.get("additional_teams") or []),
            "additional_notes": stage.get("additional_notes") or "",
            "games": games,
        }
        if stage.get("comment"):
            legacy_stage["comment"] = stage["comment"]
        legacy_stage.update(stage.get("extra") or {})
        stages.append(legacy_stage)
    sd["stages"] = stages
    sd.update(season.get("extra") or {})
    return sd


# ─── Правка сезона через API ───────────────────────────────────────────────────

_SIMPLE_UPDATE_FIELDS = (
    "year", "number", "league_name", "intro_html", "description", "metadata", "host",
    "hosts", "editors", "jury", "extra_sections", "late_joined_teams",
)


def _resolve_ref(ref: dict, lookup: TeamLookup, participant_type: str) -> dict:
    if participant_type == PARTICIPANT_TEAM:
        ref["team_id"] = lookup.resolve(slug=ref.get("slug") or "", team_id=ref.get("team_id") or "")
        if ref["team_id"] and not ref.get("slug"):
            ref["slug"] = lookup.slug_for(ref["team_id"]) or ""
    return ref


def apply_season_update(season: dict, update: dict, lookup: TeamLookup) -> dict:
    """
    Применить правку (dict из SeasonUpdate с exclude_unset) к документу сезона.
    Ссылки на команды проверяются по коллекции teams: неизвестный team_id сбрасывается, slug дополняется.
    """
    season = copy.deepcopy(season)
    participant_type = season.get("participant_type", PARTICIPANT_TEAM)

    for field in _SIMPLE_UPDATE_FIELDS:
        if field in update:
            season[field] = update[field]
            if field != "year" and field != "number":
                legacy_keys = set(season.get("legacy_keys") or [])
                legacy_keys.add({"number": "season_number"}.get(field, field))
                season["legacy_keys"] = sorted(legacy_keys)

    for field in ("teams", "winners"):
        if field in update:
            season[field] = [_resolve_ref(dict(ref), lookup, participant_type) for ref in update[field] or []]

    if "stages" in update:
        stages = []
        used_game_ids: set = set()
        for stage_index, raw_stage in enumerate(update["stages"] or []):
            stage = dict(raw_stage)
            stage["id"] = stage.get("id") or str(uuid.uuid4())
            stage["code"] = stage_code(stage.get("name") or "")
            if stage.get("order") is None:
                stage["order"] = stage_index + 1
            games = []
            for game_index, raw_game in enumerate(stage.get("games") or []):
                game = dict(raw_game)
                if not game.get("id") or game["id"] in used_game_ids:
                    game["id"] = str(uuid.uuid4())
                    game.setdefault("had_legacy_id", True)
                used_game_ids.add(game["id"])
                if game.get("order") is None:
                    game["order"] = game_index + 1
                game["results"] = [
                    _resolve_ref(dict(result), lookup, participant_type) for result in game.get("results") or []
                ]
                games.append(game)
            stage["games"] = games
            stages.append(stage)
        season["stages"] = stages

    return season


def unresolved_participants(season: dict) -> list[dict]:
    """Участники без ссылки на сущность (для ручной привязки)."""
    out = []
    for ref in season.get("teams") or []:
        if not ref.get("team_id") and not ref.get("person_id"):
            out.append({"where": "teams", "slug": ref.get("slug"), "name": ref.get("name")})
    for ref in season.get("winners") or []:
        if not ref.get("team_id") and not ref.get("person_id"):
            out.append({"where": "winners", "slug": ref.get("slug"), "name": ref.get("name")})
    for stage in season.get("stages") or []:
        for game in stage.get("games") or []:
            for result in game.get("results") or []:
                if not result.get("team_id") and not result.get("person_id"):
                    out.append({
                        "where": "results", "stage": stage.get("name"), "game": game.get("name"),
                        "slug": result.get("slug"), "name": result.get("name"),
                    })
    return out


# ─── Перекрёстные ссылки ───────────────────────────────────────────────────────

def _participant_key(ref: dict) -> Optional[str]:
    if ref.get("team_id"):
        return f"team:{ref['team_id']}"
    if ref.get("person_id"):
        return f"person:{ref['person_id']}"
    if ref.get("slug"):
        return f"slug:{ref['slug']}"
    if ref.get("name"):
        return f"name:{ref['name'].strip().lower()}"
    return None


def build_participations(season: dict, people: Optional["PersonLookup"] = None) -> list[dict]:
    """
    Строки participations для сезона: по одной на результат в игре (kind=game),
    одна итоговая на участника сезона (kind=season) и по одной на человека в роли жюри/ведущего/редактора (kind=role).
    """
    base = {
        "tournament_id": season["tournament_id"],
        "tournament_slug": season.get("tournament_slug"),
        "show": season.get("show"),
        "season_id": season["_id"],
        "season_year": season.get("year"),
        "season_title": season.get("title"),
        "season_path": season.get("page_path"),
        "season_status": season.get("status"),
    }
    rows: list[dict] = []
    summary: dict[str, dict] = {}

    def summary_for(ref: dict) -> Optional[dict]:
        key = _participant_key(ref)
        if not key:
            return None
        if key not in summary:
            summary[key] = {
                **base,
                "_id": stable_id(season["_id"], "season", key),
                "kind": "season",
                "participant_key": key,
                "team_id": ref.get("team_id"),
                "person_id": ref.get("person_id"),
                "slug": ref.get("slug") or "",
                "name": ref.get("name") or "",
                "city": ref.get("city") or "",
                "in_season_list": False,
                "is_champion": False,
                "games_played": 0,
                "wins": 0,
                "best_stage_order": None,
                "best_stage_name": None,
                "best_stage_code": None,
                "last_stage_passed": False,
            }
        row = summary[key]
        for field in ("team_id", "person_id", "slug", "name", "city"):
            if not row.get(field) and ref.get(field):
                row[field] = ref[field]
        return row

    for ref in season.get("teams") or []:
        row = summary_for(ref)
        if row:
            row["in_season_list"] = True
    for ref in season.get("winners") or []:
        row = summary_for(ref)
        if row:
            row["is_champion"] = True

    for stage in season.get("stages") or []:
        for game in stage.get("games") or []:
            for index, result in enumerate(game.get("results") or []):
                key = _participant_key(result)
                if not key:
                    continue
                rows.append({
                    **base,
                    "_id": stable_id(season["_id"], "game", game["id"], index),
                    "kind": "game",
                    "participant_key": key,
                    "team_id": result.get("team_id"),
                    "person_id": result.get("person_id"),
                    "slug": result.get("slug") or "",
                    "name": result.get("name") or "",
                    "city": result.get("city") or "",
                    "stage_id": stage.get("id"),
                    "stage_order": stage.get("order"),
                    "stage_name": stage.get("name"),
                    "stage_code": stage.get("code"),
                    "game_id": game.get("id"),
                    "game_order": game.get("order"),
                    "game_name": game.get("name"),
                    "date": game.get("date") or "",
                    "place": result.get("place"),
                    "total": result.get("total"),
                    "scores": result.get("scores") or {},
                    "passed": result.get("passed", False),
                    "is_winner": result.get("is_winner", False),
                    "is_additional": result.get("is_additional", False),
                    "participants_count": len(game.get("results") or []),
                })
                row = summary_for(result)
                row["games_played"] += 1
                if result.get("place") == 1:
                    row["wins"] += 1
                stage_order = stage.get("order") or 0
                if row["best_stage_order"] is None or stage_order > row["best_stage_order"]:
                    row["best_stage_order"] = stage_order
                    row["best_stage_name"] = stage.get("name")
                    row["best_stage_code"] = stage.get("code")
                    row["last_stage_passed"] = bool(result.get("passed"))
                elif stage_order == row["best_stage_order"] and result.get("passed"):
                    row["last_stage_passed"] = True

    rows.extend(_role_rows(season, base, people))
    return list(summary.values()) + rows


ROLE_JURY = "jury"
ROLE_HOST = "host"
ROLE_EDITOR = "editor"


def _clean_person_name(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip(" ,;.")


def _role_rows(season: dict, base: dict, people: Optional["PersonLookup"]) -> list[dict]:
    """Строки kind=role: жюри, ведущие, редакторы сезона (по одной на человека и роль, со счётчиком игр)."""
    found: dict[tuple[str, str], dict] = {}

    def add(role: str, raw_name: Any, game: Optional[dict] = None):
        name = _clean_person_name(raw_name)
        key = name_key(name)
        if not key or len(name) > 60:
            return
        row = found.get((role, key))
        if row is None:
            person_id, matched_by = people.resolve(None, name) if people else (None, None)
            row = found[(role, key)] = {
                **base,
                "_id": stable_id(season["_id"], "role", role, key),
                "kind": "role",
                "role": role,
                "participant_key": f"person:{person_id}" if person_id else f"name:{key}",
                "person_id": person_id,
                "matched_by": matched_by,
                "team_id": None,
                "name": name,
                "name_key": key,
                "games_count": 0,
                "game_ids": [],
            }
        if game is not None and game.get("id") not in row["game_ids"]:
            row["game_ids"].append(game.get("id"))
            row["games_count"] += 1

    for name in season.get("jury") or []:
        add(ROLE_JURY, name)
    for name in season.get("hosts") or []:
        add(ROLE_HOST, name)
    if season.get("host"):
        add(ROLE_HOST, season["host"])
    for name in season.get("editors") or []:
        add(ROLE_EDITOR, name)
    for stage in season.get("stages") or []:
        for game in stage.get("games") or []:
            for name in game.get("jury") or []:
                add(ROLE_JURY, name, game)
            if game.get("host"):
                add(ROLE_HOST, game["host"], game)
    return list(found.values())


# ─── Работа с БД ───────────────────────────────────────────────────────────────

def page_filter(page_id: str) -> dict:
    """Фильтр страницы по строковому id (у части старых документов _id — ObjectId)."""
    candidates: list[Any] = [page_id]
    if ObjectId.is_valid(page_id):
        candidates.append(ObjectId(page_id))
    return {"_id": {"$in": candidates}}


async def load_team_lookup(db) -> TeamLookup:
    teams = await db.teams.find(KVN_ONLY, {"_id": 1, "slug": 1}).to_list(None)  # сезоны КВН ссылаются на команды КВН
    return TeamLookup(teams)


def _league_slug_from_path(full_path: str) -> Optional[str]:
    parts = (full_path or "").strip("/").split("/")
    return parts[1] if len(parts) >= 3 and parts[0] == SHOW_KVN else None


async def ensure_kvn_tournament(db, league_slug: str) -> Optional[dict]:
    """Турнир для лиги КВН (страница kvn/<league_slug>). Создаётся при первом обращении."""
    existing = await db.tournaments.find_one({"show": SHOW_KVN, "slug": league_slug})
    if existing:
        return existing
    league_page = await db.kvn.find_one({"full_path": {"$in": [f"kvn/{league_slug}", f"/kvn/{league_slug}"]}})
    if not league_page:
        return None
    now = now_iso()
    doc = {
        "_id": stable_id("tournament", SHOW_KVN, league_slug),
        "show": SHOW_KVN,
        "slug": league_slug,
        "title": league_page.get("name") or league_page.get("title") or league_slug,
        "short_title": league_page.get("title") or league_slug,
        "participant_type": PARTICIPANT_TEAM,
        "team_type": SHOW_KVN,
        "page_collection": "kvn",
        "page_id": str(league_page["_id"]),
        "page_path": (league_page.get("full_path") or "").lstrip("/"),
        "order": KVN_LEAGUE_ORDER.get(league_slug, 100),
        "status": league_page.get("status") or "published",
        "created_at": now,
        "updated_at": now,
    }
    await db.tournaments.update_one({"_id": doc["_id"]}, {"$setOnInsert": doc}, upsert=True)
    return await db.tournaments.find_one({"_id": doc["_id"]})


async def save_season(db, season: dict, *, write_page: bool, people: Optional[PersonLookup] = None) -> dict:
    """Сохранить сезон, пересобрать participations; при write_page — записать season_data в страницу."""
    now = now_iso()
    existing = await db.seasons.find_one({"_id": season["_id"]}, {"created_at": 1})
    season["created_at"] = (existing or {}).get("created_at") or now
    season["updated_at"] = now
    await db.seasons.replace_one({"_id": season["_id"]}, season, upsert=True)

    rows = build_participations(season, people or await load_person_lookup(db))
    await db.participations.delete_many({"season_id": season["_id"]})
    if rows:
        await db.participations.insert_many(rows, ordered=False)

    if write_page and season.get("page_collection") == "kvn" and season.get("page_id"):
        page = await db.kvn.find_one(page_filter(season["page_id"]), {"season_data": 1})
        if page is not None:
            legacy = season_to_legacy(season)
            old = page.get("season_data") or {}
            for key in _LEGACY_COMPUTED_KEYS:
                if key in old:
                    legacy[key] = old[key]
            await db.kvn.update_one(
                {"_id": page["_id"]},
                {"$set": {"season_data": legacy, "updated_at": now}},
            )
    return season


async def sync_from_kvn_page(
    db, page: dict, lookup: Optional[TeamLookup] = None, people: Optional[PersonLookup] = None
) -> Optional[dict]:
    """Синхронизировать сезон из страницы КВН. Страницы без season_data или вне лиги — удаляют сезон."""
    page_id = str(page["_id"])
    league_slug = _league_slug_from_path(page.get("full_path", ""))
    if not page.get("season_data") or not league_slug:
        await delete_season_for_page(db, page_id)
        return None
    tournament = await ensure_kvn_tournament(db, league_slug)
    if not tournament:
        logger.warning(f"Нет страницы лиги kvn/{league_slug} для сезона {page.get('full_path')}")
        return None
    lookup = lookup or await load_team_lookup(db)
    season = legacy_to_season(page, tournament, lookup)
    return await save_season(db, season, write_page=False, people=people)


async def sync_kvn_pages(db, query: Optional[dict] = None) -> dict:
    """Синхронизировать все (или отобранные) страницы КВН с season_data."""
    lookup = await load_team_lookup(db)
    people = await load_person_lookup(db)
    stats = {"pages": 0, "seasons": 0, "skipped": 0, "errors": []}
    base_query = {"season_data": {"$exists": True}}
    if query:
        base_query = {"$and": [base_query, query]}
    async for page in db.kvn.find(base_query):
        stats["pages"] += 1
        try:
            season = await sync_from_kvn_page(db, page, lookup, people)
        except Exception as e:  # одна битая страница не должна останавливать остальные
            stats["errors"].append(f"{page.get('full_path')}: {e}")
            logger.error(f"Competitions: ошибка синхронизации {page.get('full_path')}: {e}", exc_info=True)
            continue
        stats["seasons" if season else "skipped"] += 1
    return stats


async def delete_season_for_page(db, page_id: str) -> None:
    season_id = stable_id("kvn-page", page_id)
    await db.seasons.delete_one({"_id": season_id})
    await db.participations.delete_many({"season_id": season_id})


async def ensure_competitions_synced(db) -> None:
    """При старте: если сезонов ещё нет, а данные в страницах КВН есть — выполнить первичную миграцию."""
    try:
        if await db.seasons.estimated_document_count() > 0:
            return
        if not await db.kvn.find_one({"season_data": {"$exists": True}}, {"_id": 1}):
            return
        stats = await sync_kvn_pages(db)
        logger.info(f"Competitions: первичная синхронизация из страниц КВН: {stats}")
    except Exception as e:
        logger.error(f"Competitions: первичная синхронизация не удалась: {e}", exc_info=True)


async def create_competition_indexes(ensure_index, db) -> None:
    await ensure_index(db.tournaments, [("show", 1), ("slug", 1)], unique=True)
    await ensure_index(db.seasons, [("tournament_id", 1), ("year", 1)])
    await ensure_index(db.seasons, "page_id")
    await ensure_index(db.participations, "season_id")
    await ensure_index(db.participations, [("team_id", 1), ("kind", 1), ("season_year", -1)])
    await ensure_index(db.participations, [("person_id", 1), ("kind", 1), ("season_year", -1)])
    await ensure_index(db.participations, [("slug", 1), ("kind", 1)])
    await ensure_index(db.participations, [("name_key", 1), ("kind", 1)], sparse=True)
