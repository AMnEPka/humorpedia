#!/usr/bin/env python3
"""Быстрый импорт people напрямую из humorbd.sql -> MongoDB.

Задачи:
- Перестать проверять тысячи страниц вручную: импортировать пачками и сразу получать корректные modules.
- Гарантировать, что у людей будет биография + таймлайн (если он есть в источнике).
- Не делать grep на каждую запись: сканируем SQL один раз на выбранную пачку id.

Использование:
  # dry-run на 2 конкретных ID
  python3 import_people_from_sql.py --ids 115 123 --dry-run

  # импорт пачки из people_list.json (берёт первые pending)
  python3 import_people_from_sql.py --from-list --limit 10 --apply

По умолчанию: dry-run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import pymongo

from utils import DB_NAME, MONGO_URL, create_person_document, normalize_rich_text

SQL_FILE = "/app/humorbd.sql"
PEOPLE_LIST_FILE = "/app/migration/people_list.json"
TV_MAP_FILE = "/app/migration/tv_map.json"
IMAGE_MAP_FILE = "/app/migration/image_mapping.json"


# --------- parsing helpers ---------

def _split_rows(values_str: str) -> list[str]:
    """Разбивает VALUES (...) , (...) на список строк-рядов без внешних скобок.

    Работает устойчивее чем regex split, потому что учитывает кавычки и экранирование.
    """
    rows: list[str] = []
    current = ""
    in_quotes = False
    escape_next = False
    paren_depth = 0

    for ch in values_str:
        if escape_next:
            current += ch
            escape_next = False
            continue

        if ch == "\\":
            current += ch
            escape_next = True
            continue

        if ch == "'":
            in_quotes = not in_quotes
            current += ch
            continue

        if not in_quotes:
            if ch == "(":
                paren_depth += 1
            elif ch == ")":
                paren_depth -= 1

                # конец ряда: парсинг INSERT обычно "(...),(...)" (без вложенных скобок)
                if paren_depth == -1:
                    rows.append(current)
                    current = ""
                    paren_depth = 0
                    continue

            # разделитель между рядами
            if ch == "," and paren_depth == 0 and current:
                rows.append(current)
                current = ""
                continue

        current += ch

    if current.strip():
        rows.append(current)

    # чистим возможные внешние скобки
    cleaned = []
    for r in rows:
        rr = r.strip()
        if rr.startswith("("):
            rr = rr[1:]
        if rr.endswith(")"):
            rr = rr[:-1]
        cleaned.append(rr)

    return cleaned


def _split_fields(row_str: str) -> list[str | None]:
    """Разделение SQL tuple на поля (учитывая кавычки и backslash)."""
    fields: list[str | None] = []
    cur = ""
    in_quotes = False
    escape_next = False

    i = 0
    while i < len(row_str):
        ch = row_str[i]

        if escape_next:
            cur += ch
            escape_next = False
            i += 1
            continue

        if ch == "\\":
            cur += ch
            escape_next = True
            i += 1
            continue

        if ch == "'":
            in_quotes = not in_quotes
            i += 1
            continue

        if ch == "," and not in_quotes:
            v = cur.strip()
            if v.upper() == "NULL":
                fields.append(None)
            else:
                fields.append(v)
            cur = ""
            i += 1
            while i < len(row_str) and row_str[i] == " ":
                i += 1
            continue

        cur += ch
        i += 1

    v = cur.strip()
    if v.upper() == "NULL":
        fields.append(None)
    else:
        fields.append(v)

    return fields


def _unescape_sql_string(value: str) -> str:
    # базовое "MySQL dump" экранирование
    # важно: сначала двойные \\\\ -> \\, затем \\' -> '
    return value.replace("\\\\", "\\").replace("\\'", "'")


# --------- data extraction ---------

@dataclass
class SiteContentRow:
    id: int
    pagetitle: str
    longtitle: str
    description: str
    alias: str
    keywords: str
    rating: float
    votes: int


def _load_tv_map() -> dict[str, str]:
    if os.path.exists(TV_MAP_FILE):
        with open(TV_MAP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    # строим карту из единственного INSERT `modx_site_tmplvars`
    tv_map: dict[str, str] = {}
    insert_started = False
    buf: list[str] = []

    with open(SQL_FILE, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not insert_started:
                if "INSERT INTO `modx_site_tmplvars`" in line:
                    insert_started = True
                    buf.append(line)
                continue

            buf.append(line)
            if line.strip().endswith(";"):
                break

    blob = "".join(buf)
    m = re.search(r"VALUES\s*(.*);\s*$", blob, flags=re.DOTALL)
    if not m:
        raise RuntimeError("Не удалось найти VALUES в modx_site_tmplvars")

    values_str = m.group(1)
    rows = _split_rows(values_str)

    # поля tmplvars: (id, source, property_preprocess, type, name, caption, ...)
    for r in rows:
        parts = _split_fields(r)
        if len(parts) >= 5 and parts[0] and parts[4]:
            tv_id = str(parts[0]).strip()
            tv_name = _unescape_sql_string(str(parts[4]))
            tv_map[tv_id] = tv_name

    with open(TV_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(tv_map, f, ensure_ascii=False, indent=2)

    return tv_map


def _load_image_map() -> dict[str, str]:
    if not os.path.exists(IMAGE_MAP_FILE):
        return {}
    with open(IMAGE_MAP_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_for_ids(target_ids: set[int]):
    """Сканирует humorbd.sql и собирает site_content + tv_values только для target_ids."""

    site_content: dict[int, SiteContentRow] = {}
    tv_values: dict[int, dict[str, str]] = {i: {} for i in target_ids}

    in_sc = False
    in_tv = False
    buf: list[str] = []

    def flush_site_content(insert_blob: str):
        m = re.search(r"VALUES\s*(.*);\s*$", insert_blob, flags=re.DOTALL)
        if not m:
            return
        rows = _split_rows(m.group(1))

        # В humorbd.sql в конце у site_content есть extra поля: old_id, keywords, popular, rating, votes
        # Нам нужны: id(0), pagetitle(3), longtitle(4), description(5), alias(6), keywords(45), rating(48), votes(49)
        for r in rows:
            parts = _split_fields(r)
            if not parts or parts[0] is None:
                continue
            try:
                rid = int(str(parts[0]).strip())
            except Exception:
                continue
            if rid not in target_ids:
                continue

            def s(idx: int) -> str:
                v = parts[idx] if idx < len(parts) else ""
                return _unescape_sql_string(v) if isinstance(v, str) else ""

            keywords = s(45)
            try:
                rating = float(str(parts[48]).strip()) if parts[48] is not None else 0.0
            except Exception:
                rating = 0.0
            try:
                votes = int(str(parts[49]).strip()) if parts[49] is not None else 0
            except Exception:
                votes = 0

            site_content[rid] = SiteContentRow(
                id=rid,
                pagetitle=s(3),
                longtitle=s(4),
                description=s(5),
                alias=s(6),
                keywords=keywords,
                rating=rating,
                votes=votes,
            )

    def flush_tv(insert_blob: str):
        m = re.search(r"VALUES\s*(.*);\s*$", insert_blob, flags=re.DOTALL)
        if not m:
            return
        rows = _split_rows(m.group(1))

        # (id, tmplvarid, contentid, value)
        for r in rows:
            parts = _split_fields(r)
            if len(parts) < 4:
                continue
            if parts[2] is None:
                continue
            try:
                contentid = int(str(parts[2]).strip())
            except Exception:
                continue
            if contentid not in target_ids:
                continue

            tmplvarid = str(parts[1]).strip() if parts[1] is not None else ""
            raw_val = parts[3] if isinstance(parts[3], str) else ""
            tv_values[contentid][tmplvarid] = _unescape_sql_string(raw_val)

    with open(SQL_FILE, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not in_sc and not in_tv:
                if line.startswith("INSERT INTO `modx_site_content`"):
                    in_sc = True
                    buf = [line]
                    if line.strip().endswith(";"):
                        flush_site_content(line)
                        in_sc = False
                        buf = []
                    continue

                if line.startswith("INSERT INTO `modx_site_tmplvar_contentvalues`"):
                    in_tv = True
                    buf = [line]
                    if line.strip().endswith(";"):
                        flush_tv(line)
                        in_tv = False
                        buf = []
                    continue

            if in_sc:
                buf.append(line)
                if line.strip().endswith(";"):
                    flush_site_content("".join(buf))
                    in_sc = False
                    buf = []
                continue

            if in_tv:
                buf.append(line)
                if line.strip().endswith(";"):
                    flush_tv("".join(buf))
                    in_tv = False
                    buf = []
                continue

    return site_content, tv_values


# --------- MIGX / timeline parsing ---------

def _parse_ru_date(date_str: str) -> str | None:
    if not date_str:
        return None
    date_str = normalize_rich_text(date_str)

    months = {
        "января": 1,
        "февраля": 2,
        "марта": 3,
        "апреля": 4,
        "мая": 5,
        "июня": 6,
        "июля": 7,
        "августа": 8,
        "сентября": 9,
        "октября": 10,
        "ноября": 11,
        "декабря": 12,
    }

    m = re.search(r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})", date_str, flags=re.IGNORECASE)
    if not m:
        return None
    day = int(m.group(1))
    month = months.get(m.group(2).lower())
    year = int(m.group(3))
    if not month:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _parse_table_birth(html: str) -> tuple[str | None, str | None]:
    """Достаём дату/место рождения из HTML-таблицы, если есть."""
    if not html:
        return None, None
    h = normalize_rich_text(html)

    def find_cell(label: str) -> str | None:
        # <td>Дата рождения</td><td>...</td>
        m = re.search(
            rf"<td>\s*{re.escape(label)}\s*</td>\s*<td>(.*?)</td>",
            h,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return None
        v = re.sub(r"<[^>]+>", "", m.group(1))
        v = normalize_rich_text(v)
        return v

    bd = find_cell("Дата рождения")
    bp = find_cell("Место рождения")

    return _parse_ru_date(bd) if bd else None, bp


def _parse_migx(value: str) -> list[dict]:
    """MIGX хранится как JSON-список секций, часто с двойным экранированием."""
    if not value:
        return []
    raw = value

    # нормализуем самые частые артефакты
    raw = raw.replace("\\r\\n", "\n").replace("\\r", "\n")

    # иногда строка уже JSON; иногда закодирована как строка JSON внутри SQL
    # попробуем несколько раз раскодировать.
    for _ in range(3):
        try:
            data = json.loads(raw)
            # если вдруг это строка, а не массив — продолжаем
            if isinstance(data, str):
                raw = data
                continue
            if isinstance(data, list):
                return data
            return []
        except Exception:
            pass

        # попытка «разэкранировать»
        raw = raw.replace("\\\"", '"').replace("\\/", "/")

    return []


def _timeline_from_tv_named(tv_named: dict[str, str]) -> list[dict]:
    events = []
    for i in range(1, 15):
        suf = "" if i == 1 else str(i)
        d = tv_named.get(f"timeline-block-date{suf}")
        n = tv_named.get(f"timeline-block-name{suf}")
        v = tv_named.get(f"timeline-block-value{suf}")
        if d and n and v:
            events.append(
                {
                    "year": normalize_rich_text(d),
                    "title": normalize_rich_text(n),
                    "description": normalize_rich_text(v),
                }
            )
    return events


def _timeline_from_migx_sections(sections: list[dict]) -> list[dict]:
    for sec in sections:
        if sec.get("MIGX_formname") != "timeline":
            continue
        list_triple = sec.get("list_triple")
        if not list_triple:
            continue

        # list_triple сам является JSON-строкой
        raw = normalize_rich_text(list_triple)
        raw = raw.replace("\\\"", '"').replace("\\/", "/")
        try:
            arr = json.loads(raw)
        except Exception:
            return []

        events = []
        for item in arr:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or ""
            subtitle = item.get("subtitle") or ""
            content = item.get("content") or ""
            events.append(
                {
                    "year": normalize_rich_text(subtitle) or None,
                    "title": normalize_rich_text(title) or None,
                    "description": normalize_rich_text(content) or None,
                }
            )
        return [e for e in events if e.get("title") or e.get("description")]

    return []


def _social_from_migx_sections(sections: list[dict]) -> dict[str, str]:
    for sec in sections:
        if sec.get("MIGX_formname") != "info":
            continue
        raw = sec.get("list_social")
        if not raw:
            return {}
        s = normalize_rich_text(raw)
        s = s.replace("\\\"", '"').replace("\\/", "/")
        try:
            arr = json.loads(s)
        except Exception:
            return {}
        links = {}
        for item in arr:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            link = item.get("link")
            if name and link:
                links[str(name)] = normalize_rich_text(str(link))
        return links
    return {}


def _bio_from_migx_sections(sections: list[dict]) -> tuple[str, str | None, str | None, dict[str, str]]:
    """Возвращает: (bio_html, birth_date_iso, birth_place, social_links)."""
    for sec in sections:
        if sec.get("MIGX_formname") != "info":
            continue
        bio_html = sec.get("content") or ""
        table_html = sec.get("table") or ""
        birth_date, birth_place = _parse_table_birth(table_html)
        return normalize_rich_text(bio_html), birth_date, birth_place, _social_from_migx_sections(sections)

    return "", None, None, {}


def _tags_from_keywords(keywords: str) -> list[str]:
    if not keywords:
        return []
    parts = [normalize_rich_text(p.strip()) for p in keywords.split(",")]
    return [p for p in parts if p]


def build_person_doc(
    sc: SiteContentRow,
    tv_by_id: dict[str, str],
    tv_map: dict[str, str],
    image_map: dict[str, str],
    image_hint: str | None,
):
    tv_named = {}
    for tv_id, val in tv_by_id.items():
        tv_name = tv_map.get(tv_id)
        if tv_name:
            tv_named[tv_name] = val

    sections = []
    if "migx" in tv_named:
        sections = _parse_migx(tv_named.get("migx", ""))

    # биография
    bio_html, bd, bp, social = _bio_from_migx_sections(sections)
    if not bio_html:
        # fallback: description
        if sc.description:
            bio_html = f"<p>{normalize_rich_text(sc.description)}</p>"

    # birth_date/birth_place fallback: иногда прямыми TV
    if not bd:
        bd = _parse_ru_date(tv_named.get("table-value2", ""))
    if not bp:
        bp = normalize_rich_text(tv_named.get("table-value3", "")) if tv_named.get("table-value3") else None

    # social fallback: иногда отдельными TV (vk/telegram/...)
    if not social:
        for k in ["table-vk", "table-ig", "table-youtube", "table-tg", "table-telegram"]:
            if tv_named.get(k):
                social[k.replace("table-", "")] = normalize_rich_text(tv_named[k])

    # timeline
    timeline_events = _timeline_from_tv_named(tv_named)
    if not timeline_events:
        timeline_events = _timeline_from_migx_sections(sections)

    # tags
    tags = _tags_from_keywords(sc.keywords)

    # rating
    rating = {"average": float(sc.rating or 0.0), "count": int(sc.votes or 0)}

    # image
    image_url = None
    if image_hint:
        image_url = image_map.get(image_hint) or image_hint
    # если image_hint — старый относительный путь, а в mapping нет, пробуем оставить как есть
    if image_url and not image_url.startswith("/"):
        image_url = image_map.get(image_url)

    doc = create_person_document(
        title=sc.pagetitle,
        slug=sc.alias,
        full_name=sc.longtitle or sc.pagetitle,
        bio_content=bio_html,
        birth_date=bd,
        birth_place=bp,
        tags=tags,
        social_links=social,
        timeline_events=timeline_events,
        rating=rating,
        image_url=image_url,
    )

    # create_person_document кладёт birth_date/birth_place внутрь bio; для совместимости
    # дублируем поля наверх, как в текущих данных
    if bd:
        doc["birth_date"] = bd
    if bp:
        doc["birth_place"] = bp

    return doc


# --------- import runner ---------

def _pick_from_people_list(limit: int) -> list[dict]:
    with open(PEOPLE_LIST_FILE, "r", encoding="utf-8") as f:
        people = json.load(f)

    pending = [p for p in people if p.get("status") == "pending"]
    return pending[:limit]


def main():
    parser = argparse.ArgumentParser(description="Import people from humorbd.sql")
    parser.add_argument("--ids", nargs="*", type=int, help="MODX content IDs")
    parser.add_argument("--from-list", action="store_true", help="Взять IDs из people_list.json")
    parser.add_argument("--limit", type=int, default=10, help="Сколько взять из списка")
    parser.add_argument("--apply", action="store_true", help="Записать в MongoDB")
    parser.add_argument("--dry-run", action="store_true", help="Только собрать и показать краткий отчёт (по умолчанию)")
    parser.add_argument("--update", action="store_true", help="Обновлять существующие записи")

    args = parser.parse_args()

    if not args.ids and not args.from_list:
        raise SystemExit("Нужно указать --ids ... или --from-list")

    # target set
    selected = []
    if args.from_list:
        selected = _pick_from_people_list(args.limit)
        target_ids = {int(p["id"]) for p in selected}
    else:
        target_ids = {int(i) for i in args.ids}

    print(f"Пачка: {len(target_ids)} ids")

    tv_map = _load_tv_map()
    image_map = _load_image_map()

    sc_rows, tv_vals = _extract_for_ids(target_ids)

    # prepare docs
    docs = []
    for cid in sorted(target_ids):
        sc = sc_rows.get(cid)
        if not sc:
            print(f"[WARN] site_content не найден для id={cid}")
            continue

        image_hint = None
        if args.from_list:
            for p in selected:
                if int(p["id"]) == cid:
                    image_hint = p.get("image")
                    break

        doc = build_person_doc(sc, tv_vals.get(cid, {}), tv_map, image_map, image_hint)
        docs.append((cid, doc))

    print(f"Собрано документов: {len(docs)}")

    if not args.apply:
        # короткий отчёт
        for cid, doc in docs[:10]:
            tl = [m for m in doc.get("modules", []) if m.get("type") == "timeline"]
            tl_count = len((tl[0].get("data", {}) or {}).get("events", [])) if tl else 0
            print(f"- id={cid} slug={doc.get('slug')} bio={'text_block' in [m.get('type') for m in doc.get('modules', [])]} timeline_events={tl_count}")
        print("DRY RUN (ничего не записано)")
        return

    # write to Mongo
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]

    imported = 0
    updated = 0

    for cid, doc in docs:
        existing = db.people.find_one({"slug": doc.get("slug")})
        if existing:
            if not args.update:
                continue
            doc["_id"] = existing["_id"]
            db.people.replace_one({"slug": doc.get("slug")}, doc)
            updated += 1
        else:
            db.people.insert_one(doc)
            imported += 1

    client.close()

    print(f"Готово. inserted={imported}, updated={updated}")


if __name__ == "__main__":
    main()
