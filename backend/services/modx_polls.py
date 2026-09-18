"""Read legacy MODX poll definitions and anonymous aggregate results."""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from services.modx_articles_news import CONTENT_CONFIG
from services.modx_dump import ModxSite, iter_table_rows, json_list


def read_legacy_votes(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8", errors="replace") as source:
        return [row for table, row in iter_table_rows(source, ["modx_uservotes"])]


def _option_text(raw: dict) -> str:
    for key in ("answer", "title", "name", "text", "value", "option"):
        value = str(raw.get(key) or "").strip()
        if value:
            return value
    return ""


def poll_definitions(site: ModxSite, votes: Iterable[dict]) -> tuple[list[dict], list[str]]:
    definitions = []
    warnings: list[str] = []
    for old_id, resource in sorted(site.resources.items()):
        raw_options = [item for item in json_list(site.tv(old_id, "vote_answers")) if isinstance(item, dict)]
        if not raw_options:
            continue
        options = []
        seen: set[int] = set()
        for index, raw in enumerate(raw_options, start=1):
            raw_id = raw.get("MIGX_id") or raw.get("answer_id") or raw.get("id") or index
            try:
                answer_id = int(raw_id)
            except (TypeError, ValueError):
                answer_id = index
            text = _option_text(raw)
            if not text:
                warnings.append(f"опрос {old_id}: вариант {answer_id} без текста пропущен")
                continue
            if answer_id in seen:
                warnings.append(f"опрос {old_id}: повтор идентификатора ответа {answer_id}")
                continue
            seen.add(answer_id)
            try:
                historical_votes = int(raw.get("votes") or 0)
            except (TypeError, ValueError):
                historical_votes = 0
                warnings.append(f"опрос {old_id}: некорректный агрегат голосов ответа {answer_id}")
            options.append({
                "id": f"legacy-{old_id}-{answer_id}",
                "text": text,
                "historical_votes": historical_votes,
                "old_answer_id": answer_id,
            })
        if len(options) < 2:
            warnings.append(f"опрос {old_id}: меньше двух пригодных вариантов")
            continue
        definitions.append({
            "_id": f"legacy-poll-{old_id}",
            "old_id": old_id,
            "question": str(resource.get("pagetitle") or resource.get("longtitle") or f"Опрос {old_id}").strip(),
            "options": options,
            "status": "published" if resource.get("published") and not resource.get("deleted") else "draft",
            "show_results_before_vote": False,
        })
    return definitions, warnings


def poll_placements(site: ModxSite) -> list[dict]:
    placements = []
    for kind, config in CONTENT_CONFIG.items():
        for resource_id, resource in site.resources.items():
            if resource.get("parent") != config["parent_id"] or resource.get("template") != config["template"]:
                continue
            if resource.get("deleted") or not resource.get("published"):
                continue
            for order, section in enumerate(site.migx_sections(resource_id), start=1):
                if section.get("hide_section") in (1, "1", True) or section.get("MIGX_formname") != "voting":
                    continue
                value = str(section.get("vote") or "").strip()
                placements.append({
                    "kind": kind,
                    "resource_id": resource_id,
                    "resource_title": resource.get("pagetitle") or "",
                    "order": order,
                    "old_poll_id": int(value) if value.isdigit() else None,
                })
    return placements


def audit_polls(site: ModxSite, votes: list[dict]) -> dict:
    definitions, warnings = poll_definitions(site, votes)
    placements = poll_placements(site)
    definition_ids = {item["old_id"] for item in definitions}
    option_ids = {
        (item["old_id"], option["old_answer_id"])
        for item in definitions for option in item["options"]
    }
    placement_ids = {item["old_poll_id"] for item in placements if item["old_poll_id"] is not None}
    row_counts = Counter((int(row["rid"]), int(row["answer_id"])) for row in votes)
    aggregate_counts = {
        (item["old_id"], option["old_answer_id"]): int(option["historical_votes"])
        for item in definitions for option in item["options"]
    }
    missing_definitions = sorted({
        item["old_poll_id"] for item in placements
        if item["old_poll_id"] is not None and item["old_poll_id"] not in definition_ids
    })
    orphan_vote_polls = sorted({int(row["rid"]) for row in votes if int(row["rid"]) not in definition_ids})
    invalid_answers = sorted({
        (int(row["rid"]), int(row["answer_id"])) for row in votes
        if (int(row["rid"]), int(row["answer_id"])) not in option_ids
    })
    aggregate_mismatches = [
        {"old_poll_id": key[0], "old_answer_id": key[1], "aggregate": aggregate, "vote_rows": row_counts.get(key, 0)}
        for key, aggregate in sorted(aggregate_counts.items())
        if aggregate != row_counts.get(key, 0)
    ]
    return {
        "definitions": definitions,
        "placements": placements,
        "votes_count": len(votes),
        "legacy_users_count": len({int(row["user_id"]) for row in votes}),
        "missing_definitions": missing_definitions,
        "orphan_vote_polls": orphan_vote_polls,
        "invalid_answers": invalid_answers,
        "unplaced_definitions": sorted(definition_ids - placement_ids),
        "aggregate_mismatches": aggregate_mismatches,
        "warnings": warnings,
    }
