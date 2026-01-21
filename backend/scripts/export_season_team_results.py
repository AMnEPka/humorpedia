#!/usr/bin/env python3
"""
Export per-team results for a given KVN season (from kvn.season_data) into a JSON file.

Usage (inside backend container):
  python scripts/export_season_team_results.py --path kvn/vl-kvn/vl-2025 --out /app/migration/kvn/vl-2025-team-results.json
"""

import argparse
import asyncio
import os
import re
import sys
from datetime import datetime

# Add backend root (/app) to import path when running inside container,
# and repo backend folder when running locally.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_db  # noqa: E402


def _league_code_from_slug(league_slug: str) -> str:
    # For now we only train on VL; later can extend mapping.
    if league_slug == "vl-kvn":
        return "ВЛ"
    return league_slug or ""


def _stage_code(stage_name: str) -> str:
    """
    Convert stage name like '1/8 финала' -> '1/8', '1/4 финала' -> '1/4', '1/2 финала' -> '1/2', 'финал' -> 'Финал'.
    """
    if not stage_name:
        return ""
    s = stage_name.strip().lower()
    m = re.search(r"(\d+)\s*/\s*(\d+)", s)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    if "финал" in s:
        if "полу" in s:
            return "1/2"
        return "Финал"
    return stage_name.strip()


def _safe_date_key(date_str: str) -> str:
    # Expect YYYY-MM-DD, but keep best-effort.
    if not date_str:
        return "9999-99-99"
    return date_str


async def export_season(path: str, out_path: str) -> dict:
    db = await get_db()
    doc = await db.kvn.find_one({"full_path": path.lstrip("/")})
    if not doc:
        doc = await db.kvn.find_one({"full_path": f"/{path.lstrip('/')}"})
    if not doc:
        doc = await db.kvn.find_one({"slug": path.lstrip("/")})
    if not doc:
        raise SystemExit(f"Season not found by path/slug: {path}")

    season_data = doc.get("season_data") or {}
    league_slug = season_data.get("league_slug") or ""
    league = _league_code_from_slug(league_slug)
    year = season_data.get("year")
    if not year:
        # fallback: try extract from slug/full_path
        m = re.search(r"(19|20)\d{2}", doc.get("slug", "") + " " + doc.get("full_path", ""))
        year = int(m.group(0)) if m else None

    results_by_team: dict[str, dict] = {}

    stages = season_data.get("stages") or []
    for stage in stages:
        stage_name = stage.get("name") or ""
        stage_code = _stage_code(stage_name)
        games = stage.get("games") or []
        for game in games:
            game_date = game.get("date") or ""
            teams = game.get("teams") or []
            n = len([t for t in teams if isinstance(t, dict) and t.get("team_slug")])
            if n <= 0:
                continue
            for t in teams:
                if not isinstance(t, dict):
                    continue
                team_slug = t.get("team_slug")
                if not team_slug:
                    continue
                place = t.get("place")
                # Skip if no place
                if place is None:
                    continue
                row = {
                    "year": year,
                    "league": league,
                    "stage": stage_code,
                    "stage_name": stage_name,
                    "result": f"{place} из {n}",
                    "place": place,
                    "out_of": n,
                    "date": game_date,
                    "game_name": game.get("name") or "",
                }
                entry = results_by_team.setdefault(
                    team_slug,
                    {"team_slug": team_slug, "rows": []},
                )
                entry["rows"].append(row)

    # Sort rows for each team by date then stage order-ish
    for entry in results_by_team.values():
        entry["rows"].sort(key=lambda r: (_safe_date_key(r.get("date", "")), r.get("stage", "")))

    payload = {
        "season_path": path.lstrip("/"),
        "league_slug": league_slug,
        "league": league,
        "year": year,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "teams": sorted(results_by_team.values(), key=lambda x: x["team_slug"]),
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    import json

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="KVN season full_path, e.g. kvn/vl-kvn/vl-2025")
    ap.add_argument("--out", required=True, help="Output JSON path")
    args = ap.parse_args()

    payload = asyncio.run(export_season(args.path, args.out))
    print(f"✅ Exported {len(payload.get('teams', []))} teams to {args.out}")


if __name__ == "__main__":
    main()

