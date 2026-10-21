"""Read-only сверка канонических сезонов и legacy-проекций КВН."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any, Iterable

from services.competitions import TeamLookup, _league_slug_from_path, legacy_to_season, season_to_legacy


_STATUSES = ("equal_projection", "projection_conflict", "missing_canonical", "missing_legacy", "ambiguous", "invalid")
_ROUNDTRIP_EXCLUDED = {"created_at", "updated_at", "legacy_keys", "_projection", "_write_claim"}
_DIFF_GROUPS = ("projection_differences", "metadata_differences", "canonical_roundtrip_differences")


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _compact(value: Any) -> dict[str, Any]:
    normalized = _json_value(value)
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded) <= 200:
        return {"present": True, "value": normalized}
    return {
        "present": True,
        "value": encoded[:177] + "…",
        "digest": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
    }


def _pointer(parent: str, key: Any) -> str:
    escaped = str(key).replace("~", "~0").replace("/", "~1")
    return f"{parent}/{escaped}"


def _diff(left: Any, right: Any, path: str = "") -> list[dict[str, Any]]:
    if isinstance(left, dict) and isinstance(right, dict):
        result = []
        for key in sorted(set(left) | set(right), key=str):
            child = _pointer(path, key)
            if key not in left:
                result.append({"path": child, "left": {"present": False}, "right": _compact(right[key])})
            elif key not in right:
                result.append({"path": child, "left": _compact(left[key]), "right": {"present": False}})
            else:
                result.extend(_diff(left[key], right[key], child))
        return result
    if isinstance(left, list) and isinstance(right, list):
        result = []
        for index in range(max(len(left), len(right))):
            child = _pointer(path, index)
            if index >= len(left):
                result.append({"path": child, "left": {"present": False}, "right": _compact(right[index])})
            elif index >= len(right):
                result.append({"path": child, "left": _compact(left[index]), "right": {"present": False}})
            else:
                result.extend(_diff(left[index], right[index], child))
        return result
    if isinstance(left, bool) != isinstance(right, bool):
        different = True
    elif isinstance(left, (int, float)) and not isinstance(left, bool) and isinstance(right, (int, float)) and not isinstance(right, bool):
        different = left != right
    else:
        different = type(left) is not type(right) and _json_value(left) == _json_value(right) or _json_value(left) != _json_value(right)
    if different:
        return [{"path": path or "/", "left": _compact(left), "right": _compact(right)}]
    return []


def _season_projection(season: dict) -> dict:
    return _json_value(season_to_legacy(season))


def _canonical_roundtrip(season: dict, lookup: TeamLookup) -> tuple[dict, dict]:
    legacy = season_to_legacy(season, season.get("tournament_slug"))
    page = {
        "_id": str(season["page_id"]),
        "slug": season.get("slug") or "",
        "full_path": season.get("page_path") or "",
        "title": season.get("title") or "",
        "status": season.get("status") or "draft",
        "season_data": legacy,
    }
    tournament = {
        "_id": season.get("tournament_id"),
        "slug": season.get("tournament_slug") or "",
        "show": season.get("show") or "kvn",
        "participant_type": season.get("participant_type") or "team",
    }
    return legacy_to_season(page, tournament, lookup), page


def _without_roundtrip_exclusions(season: dict) -> dict:
    """Исключить служебные поля только корневого документа сезона."""
    return {key: value for key, value in season.items() if key not in _ROUNDTRIP_EXCLUDED}


def _metadata_projection(page: dict, tournament_slug: str, tournament_id: Any) -> dict:
    path = (page.get("full_path") or "").strip("/")
    result = {"path": path} if "full_path" in page else {}
    if "title" in page:
        result["title"] = page["title"]
    elif "name" in page:
        result["title"] = page["name"]
    if "slug" in page:
        result["slug"] = page["slug"]
    if "status" in page:
        result["status"] = page["status"]
    result["tournament"] = {"slug": tournament_slug, "id": _json_value(tournament_id)}
    return result


def _stored_metadata(season: dict) -> dict:
    result = {}
    for page_field, season_field in (("title", "title"), ("slug", "slug"), ("status", "status")):
        if season_field in season:
            result[page_field] = season[season_field]
    if "page_path" in season:
        result["path"] = (season.get("page_path") or "").strip("/")
    tournament = {}
    if "tournament_slug" in season:
        tournament["slug"] = season["tournament_slug"]
    if "tournament_id" in season:
        tournament["id"] = _json_value(season["tournament_id"])
    result["tournament"] = tournament
    return result


def reconcile_seasons(
    pages: Iterable[dict],
    seasons: Iterable[dict],
    tournaments: Iterable[dict],
    teams: Iterable[dict],
    *,
    max_differences: int = 50,
) -> dict[str, Any]:
    """Сверить записи по точной связи `page_collection=kvn` и `page_id`, ничего не меняя."""
    if max_differences < 1:
        raise ValueError("max_differences должен быть не меньше 1")

    lookup = TeamLookup(team for team in teams if team.get("show_id") is None)
    tournaments_by_slug: dict[str, list[dict]] = defaultdict(list)
    for tournament in tournaments:
        if tournament.get("show", "kvn") == "kvn" and tournament.get("slug"):
            tournaments_by_slug[str(tournament["slug"])].append(tournament)

    page_groups: dict[str, list[dict]] = defaultdict(list)
    season_groups: dict[str, list[dict]] = defaultdict(list)
    items: list[dict[str, Any]] = []

    for page in pages:
        try:
            if not isinstance(page, dict):
                raise ValueError("страница должна быть объектом")
            if "season_data" not in page or page.get("season_data") is None:
                continue
            raw_page_id = page["_id"]
            if raw_page_id is None:
                raise ValueError("пустой идентификатор страницы")
            page_id = str(raw_page_id)
            if not page_id or not isinstance(page.get("season_data"), dict):
                raise ValueError("страница не содержит объект season_data")
            page_groups[page_id].append(page)
        except Exception as exc:
            items.append({"status": "invalid", "page_id": str(page.get("_id")) if isinstance(page, dict) and page.get("_id") is not None else None,
                          "error": f"Некорректная страница: {type(exc).__name__}"})

    for season in seasons:
        if not isinstance(season, dict):
            items.append({"status": "invalid", "page_id": None, "error": "Некорректная запись сезона"})
            continue
        if season.get("page_collection") != "kvn":
            continue
        try:
            raw_page_id = season["page_id"]
            if raw_page_id is None:
                raise ValueError("пустой page_id")
            page_id = str(raw_page_id)
            if not page_id:
                raise ValueError("пустой page_id")
            season_groups[page_id].append(season)
        except Exception:
            items.append({"status": "invalid", "page_id": None, "season_id": _json_value(season.get("_id")),
                          "error": "Некорректная связь сезона со страницей"})

    for page_id, page_rows in page_groups.items():
        linked = season_groups.get(page_id, [])
        if len(page_rows) > 1 or len(linked) > 1:
            for page in page_rows:
                items.append({"status": "ambiguous", "page_id": page_id,
                              "season_ids": [_json_value(row.get("_id")) for row in linked],
                              "error": "Для страницы найдено несколько записей по точному page_id"})
            continue
        page = page_rows[0]
        if not linked:
            items.append({"status": "missing_canonical", "page_id": page_id, "season_id": None,
                          "projection_differences": [], "metadata_differences": [], "canonical_roundtrip_differences": []})
            continue
        season = linked[0]
        try:
            league_slug = _league_slug_from_path(page.get("full_path") or "")
            tournament_matches = tournaments_by_slug.get(league_slug or "", [])
            if not league_slug or len(tournament_matches) != 1:
                items.append({"status": "invalid", "page_id": page_id, "season_id": _json_value(season.get("_id")),
                              "error": "Не удалось однозначно определить турнир по пути страницы"})
                continue
            tournament = tournament_matches[0]
            projected = legacy_to_season(page, tournament, lookup)
            projection_differences = _diff(_season_projection(season), _season_projection(projected))
            metadata_differences = _diff(_stored_metadata(season), _metadata_projection(page, league_slug, tournament.get("_id")))
            roundtripped, _ = _canonical_roundtrip(season, lookup)
            roundtrip_differences = _diff(
                _json_value(_without_roundtrip_exclusions(season)),
                _json_value(_without_roundtrip_exclusions(roundtripped)),
            )
            items.append({
                "status": "projection_conflict" if projection_differences else "equal_projection",
                "page_id": page_id,
                "season_id": _json_value(season.get("_id")),
                "projection_differences": projection_differences,
                "metadata_differences": metadata_differences,
                "canonical_roundtrip_differences": roundtrip_differences,
            })
        except Exception as exc:
            items.append({"status": "invalid", "page_id": page_id, "season_id": _json_value(season.get("_id")),
                          "error": f"Ошибка преобразования записи: {type(exc).__name__}"})

    for page_id, season_rows in season_groups.items():
        if page_id in page_groups:
            continue
        if len(season_rows) > 1:
            for season in season_rows:
                items.append({"status": "ambiguous", "page_id": page_id, "season_id": _json_value(season.get("_id")),
                              "error": "Несколько сезонов ссылаются на отсутствующую страницу"})
        else:
            items.append({"status": "missing_legacy", "page_id": page_id,
                          "season_id": _json_value(season_rows[0].get("_id")),
                          "projection_differences": [], "metadata_differences": [], "canonical_roundtrip_differences": []})

    total_differences = 0
    returned_differences = 0
    truncated = False
    summary_difference_counts = {group: 0 for group in _DIFF_GROUPS}
    for item in items:
        item_difference_counts = {group: len(item.get(group, [])) for group in _DIFF_GROUPS}
        for group, count in item_difference_counts.items():
            summary_difference_counts[group] += count
        row_total = sum(item_difference_counts.values())
        item["total_differences"] = row_total
        item["difference_counts"] = item_difference_counts
        item["truncated"] = False
        total_differences += row_total
        for group in _DIFF_GROUPS:
            differences = item.get(group)
            if not differences:
                continue
            remaining = max_differences - returned_differences
            if remaining <= 0:
                item[group] = []
                item["truncated"] = True
                truncated = True
            elif len(differences) > remaining:
                item[group] = differences[:remaining]
                returned_differences += remaining
                item["truncated"] = True
                truncated = True
            else:
                returned_differences += len(differences)

    status_counts = Counter(item["status"] for item in items)
    return {
        "summary": {
            **{status: status_counts.get(status, 0) for status in _STATUSES},
            "items": len(items),
            "total_differences": total_differences,
            "returned_differences": returned_differences,
            "truncated": truncated,
            "difference_counts": summary_difference_counts,
        },
        "items": items,
    }
