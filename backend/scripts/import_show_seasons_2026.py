"""Добавить два сезона из редакционных таблиц. По умолчанию только dry-run.

Запуск внутри backend: python scripts/import_show_seasons_2026.py /tmp/seasons.json
Для записи: --apply --backup-dir /app/backups/show-seasons-2026
"""

import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import sys
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.cache import cache_service  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402


TARGETS = {
    "standup": ("8f8f1bb5-b56c-49ee-8162-6e20b8f6200d", 13, "count_second"),
    "standupwomen": ("8ac49241-58ab-4e86-95fd-f1afb161bbef", 7, "count_last"),
}
MARKS = {"", "+", "В", "+В"}


def validate(payload):
    if payload.get("schema_version") != 1:
        raise ValueError("Неизвестная версия пакета")
    seasons = payload["seasons"]
    if len(seasons) != 2 or {s["slug"] for s in seasons} != set(TARGETS):
        raise ValueError("Пакет должен содержать ровно два целевых сезона")
    for season in seasons:
        if (season["id"], season["season"], season["layout"]) != TARGETS[season["slug"]]:
            raise ValueError("Неверная целевая страница, сезон или формат")
        numbers = season["episode_numbers"]
        if not numbers or numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("Номера выпусков должны идти подряд от 1")
        if not season["source"]["url"].startswith("https://docs.google.com/spreadsheets/d/"):
            raise ValueError("Не указан источник Google Sheets")
        names = set()
        for row in season["rows"]:
            name = row["name"].strip()
            if not name or name in names:
                raise ValueError(f"Пустое имя или дубль: {name}")
            names.add(name)
            marks = row["marks"]
            if len(marks) != len(numbers) or any(m not in MARKS for m in marks):
                raise ValueError(f"Неверные отметки выпусков: {name}")
            if row["performances"] != sum("+" in m for m in marks):
                raise ValueError(f"Итог выступлений не сходится: {name}")
        if any(not any("+" in r["marks"][i] for r in season["rows"]) for i in range(len(numbers))):
            raise ValueError("Есть выпуск без состава выступающих")
    return seasons


def render_table(season):
    numbers = season["episode_numbers"]
    if season["layout"] == "count_second":
        header = ('<tr><th rowspan="2">Комик</th><th rowspan="2">Количество выступлений</th>'
                  f'<th colspan="{len(numbers)}">Номера выпусков</th></tr>\n<tr>'
                  + "".join(f"<th>{n}</th>" for n in numbers) + "</tr>")
    else:
        header = "<tr><th>Комик</th>" + "".join(f"<th>{n}</th>" for n in numbers) + "<th>Выступлений</th></tr>"
    rows = []
    for row in season["rows"]:
        cells = [escape(row["name"])]
        if season["layout"] == "count_second":
            cells.append(str(row["performances"]))
        cells.extend(escape(m) for m in row["marks"])
        if season["layout"] == "count_last":
            cells.append(str(row["performances"]))
        rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    source = escape(season["source"]["url"], quote=True)
    return ("<table><tbody>\n" + header + "\n" + "\n".join(rows) + "\n</tbody></table>\n"
            '<p>«+» — выступление; «В» — ведение без выступления; «+В» — выступление и ведение. '
            'Количество выступлений учитывает только «+» и «+В».</p>\n'
            f'<p>Источник: <a href="{source}" target="_blank" rel="noopener noreferrer">таблица сезона</a>'
            ' (данные на июнь 2026 года).</p>')


def new_modules(season):
    def module(kind, content, title=""):
        return {"id": str(uuid5(NAMESPACE_URL, f'humorpedia:{season["id"]}:season:{season["season"]}:{kind}')),
                "type": "text_block", "title": title, "visible": True,
                "data": {"title": title, "content": content, "collapsed": kind == "episodes"}}
    return [module("heading", f'<h2>{escape(season["heading"])}</h2>'),
            module("episodes", render_table(season), "Выпуски")]


def prepare_modules(show, season):
    if show["_id"] != season["id"] or (show.get("full_path") or show["slug"]) != season["slug"]:
        raise ValueError("Документ не соответствует целевой странице")
    old = show.get("modules") or []
    additions = new_modules(season)
    existing = [m for m in old if m["id"] in {a["id"] for a in additions}]
    if existing:
        expected = {a["id"]: a for a in additions}
        if len(existing) != 2 or any({k: v for k, v in m.items() if k != "order"} != expected[m["id"]] for m in existing):
            raise ValueError("Импортированный сезон изменён редактором; автоматическая перезапись запрещена")
        return deepcopy(old), False
    # Защита от повторного сезона, добавленного вручную с другими ID.
    pattern = rf'(?:сезон\s*{season["season"]}\b|{re.escape(season["heading"].split(" (")[0])})'
    if any(re.search(pattern, (m.get("title") or "") + " " + (m.get("data") or {}).get("content", ""), re.I)
           for m in old if m.get("title") != "Выпуски"):
        raise ValueError("Такой сезон уже существует с другими ID")
    anchor = next((i for i, m in enumerate(old) if m["id"] == season["after_module_id"]), None)
    if anchor is None or old[anchor].get("title") != "Выпуски":
        raise ValueError("Не найден блок предыдущего сезона")
    if any(m.get("title") == "Выпуски" for m in old[anchor + 1:]):
        raise ValueError("После выбранного сезона уже есть другая таблица выпусков")
    result = deepcopy(old)
    order = old[anchor]["order"]
    for i, module in enumerate(additions, 1):
        module["order"] = order + i
    for module in result[anchor + 1:]:
        module["order"] += len(additions)
    result[anchor + 1:anchor + 1] = additions
    return result, True


async def run(args):
    seasons = validate(json.loads(Path(args.input).read_text(encoding="utf-8")))
    db = await get_db()
    # Проверяем обе страницы до первой записи.
    plans = []
    for season in seasons:
        show = await db.shows.find_one({"_id": season["id"]})
        if not show:
            raise ValueError(f'Не найдена страница {season["slug"]}')
        modules, changed = prepare_modules(show, season)
        plans.append((season, show, modules, changed))
    report = []
    written = False
    try:
        for season, show, modules, changed in plans:
            row = {"slug": season["slug"], "season": season["season"],
                   "episodes": len(season["episode_numbers"]), "people": len(season["rows"]),
                   "performances": sum(r["performances"] for r in season["rows"]),
                   "action": "добавить" if changed else "без изменений"}
            if args.apply and changed:
                backup_dir = Path(args.backup_dir)
                backup_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                backup = backup_dir / f'{season["slug"]}-{stamp}.json'
                with backup.open("x", encoding="utf-8") as f:
                    json.dump(show, f, ensure_ascii=False, indent=2, default=str)
                query = {"_id": show["_id"], "modules": show["modules"],
                         "updated_at": show.get("updated_at", {"$exists": False})}
                result = await db.shows.update_one(query, {"$set": {
                    "modules": modules, "updated_at": datetime.now(timezone.utc).isoformat()}})
                if result.modified_count != 1:
                    raise RuntimeError(f'Страница {season["slug"]} изменилась параллельно; повторите dry-run')
                written = True
                row.update(action="добавлено", backup=str(backup))
            report.append(row)
    finally:
        if written:
            await cache_service.invalidate_everywhere(db)
    return {"apply": args.apply, "results": report}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir")
    args = parser.parse_args()
    if args.apply and not args.backup_dir:
        parser.error("Для --apply обязательно указать --backup-dir")
    try:
        print(json.dumps(await run(args), ensure_ascii=False, indent=2))
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
