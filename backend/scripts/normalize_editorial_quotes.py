"""Разовая редакционная нормализация кавычек. По умолчанию только отчёт.

python scripts/normalize_editorial_quotes.py --report-dir /app/backups/quotes
python scripts/normalize_editorial_quotes.py --apply /app/backups/quotes/plan.json

Меняет только согласованные текстовые поля. Сохраняет исходную разметку,
отчёт и значения полей до записи. Повреждённые пары пропускает по абзацам/
ячейкам. Запись защищена сравнением старых значений изменяемых полей.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

COLLECTIONS = (
    "people", "teams", "shows", "kvn", "articles", "news", "quizzes", "wiki",
    "cities", "sections", "polls", "tournaments", "seasons", "participations",
)
TEXT_KEYS = {
    "title", "name", "full_name", "menu_title", "short_title", "description",
    "content", "excerpt", "text", "author", "source", "label", "value",
    "alt", "caption", "copyright", "meta_title", "meta_description",
    "question", "explanation", "success_explanation", "error_explanation",
    "comment", "notes", "additional_notes", "intro_html", "team_name",
    "person_name", "role", "host", "jury", "editor", "venue",
}
TEXT_LISTS = {"headers", "rows", "contests", "keywords", "jury", "editors"}
SKIP_KEYS = {
    "tags", "primary_tag", "aliases", "social_links", "old_urls", "editorial_notes",
    "import_source", "sources", "source_url", "url", "href", "src", "slug",
    "full_path", "type", "id", "_id", "created_by", "updated_by",
}
BLOCKS = {
    "p", "div", "li", "ul", "ol", "td", "th", "tr", "table", "thead", "tbody",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "hr", "section",
}
PROTECTED = {"script", "style", "code", "pre", "textarea"}
# Эти две смешанные пары отдельно согласованы владельцем 2026-10-03.
MIXED_REPAIRS = {
    ("shows", "ubojnaya-liga", "modules.9.data.content"),
    ("quizzes", "humorquiz-2", "modules.0.data.questions.0.question"),
}
# Адресные восстановления из второго редакторского согласования; никаких догадок
# в остальных документах. Последнее число — количество восстановленных пар.
APPROVED_REPAIRS = {
    ("shows", "fdf9cf6c-fd3b-41e5-ad96-9f474c7047f3", "modules.16.data.content"): [
        ('Итальянское "Поле чудес</td>', 'Итальянское «Поле чудес»</td>', 1),
    ],
    ("shows", "e3f66a7b-f77f-4102-b2f1-5d53b26d494d", "modules.13.data.content"): [
        ('Дуэт "Клан Ниндзя</td>', 'Дуэт «Клан Ниндзя»</td>', 1),
    ],
    ("shows", "0228436e-56ca-4ea1-90a8-600c7bb0393e", "modules.6.data.content"): [
        ('Дуэт "ИП "Успех"', 'Дуэт «ИП „Успех“»', 2),
    ],
    ("kvn", "8f62260f-13b8-482c-9e54-0b0fd9315082", "modules.6.data.content"): [
        ('Сборная Амурской области" (Благовещенск)', '«Сборная Амурской области» (Благовещенск)', 1),
    ],
    ("shows", "af0d6bda-61cf-43d1-ab4d-c0a280c54742", "modules.8.data.content"): [
        ('Саратов"', 'Саратов', 0),
    ],
    ("news", "939c7089-1b54-42f6-a068-9fbefac401e1", "excerpt"): [
        ('"дес…', '«десятых»…', 1),
    ],
    ("news", "939c7089-1b54-42f6-a068-9fbefac401e1", "seo.meta_description"): [
        ('"дес…', '«десятых»…', 1),
    ],
}


class SourceText(HTMLParser):
    """Текст с исходными смещениями: теги/атрибуты никогда не сериализуем."""

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.lines = [0] + [m.end() for m in re.finditer("\n", source)]
        self.segments = [[]]
        self.protected = []

    def source_offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def boundary(self):
        if self.segments[-1]:
            self.segments.append([])

    def handle_starttag(self, tag, attrs):
        if tag == "br" and not self.protected:
            offset = self.source_offset()
            self.segments[-1].append(("\n", offset, offset))
        if tag in BLOCKS or tag in PROTECTED:
            self.boundary()
        if tag in PROTECTED:
            self.protected.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and not self.protected:
            offset = self.source_offset()
            self.segments[-1].append(("\n", offset, offset))
        if tag in BLOCKS:
            self.boundary()

    def handle_endtag(self, tag):
        if self.protected and tag == self.protected[-1]:
            self.protected.pop()
        if tag in BLOCKS or tag in PROTECTED:
            self.boundary()

    def handle_data(self, data):
        if self.protected:
            return
        offset = self.source_offset()
        self.segments[-1].extend((c, offset + i, offset + i + 1) for i, c in enumerate(data))

    def entity(self, raw):
        if self.protected:
            return
        start = self.source_offset()
        end = start + len(raw)
        if self.source[end:end + 1] == ";":
            end += 1
        decoded = html.unescape(self.source[start:end])
        self.segments[-1].extend((c, start, end) for c in decoded)

    def handle_entityref(self, name):
        self.entity("&" + name)

    def handle_charref(self, name):
        self.entity("&#" + name)


def normalize_text(value, repair_mixed=False):
    parser = SourceText(value)
    parser.feed(value)
    parser.close()
    replacements = []
    pairs = 0
    issues = []
    for segment in parser.segments:
        text = "".join(c for c, _, _ in segment)
        if '"' not in text:
            continue
        stack = []
        edits = []
        count = 0
        problems = []
        for i, (char, start, end) in enumerate(segment):
            if char not in '«»„“"':
                continue
            if char in "«„":
                stack.append((char, i, start, end, len(stack)))
            elif char in "»“":
                expected = "«" if char == "»" else "„"
                if stack and stack[-1][0] == expected:
                    stack.pop()
                else:
                    problems.append((i, "несогласованная существующая пара"))
            else:
                before = text[i - 1] if i else ""
                after = text[i + 1] if i + 1 < len(text) else ""
                opens = bool(after and not after.isspace()) and (
                    not before or before.isspace() or before in "([{«„:—–-"
                )
                closes = bool(before and not before.isspace()) and (
                    not after or after.isspace() or after in ")]},.;:!?»“…—–-"
                )
                if closes and stack and stack[-1][0] == '"':
                    _, _, left_start, left_end, depth = stack.pop()
                    edits.extend(((left_start, left_end, "„" if depth else "«"),
                                  (start, end, "“" if depth else "»")))
                    count += 1
                elif closes and repair_mixed and stack and stack[-1][0] in "«„":
                    opener = stack.pop()[0]
                    edits.append((start, end, "»" if opener == "«" else "“"))
                    count += 1
                elif opens:
                    stack.append(('"', i, start, end, len(stack)))
                else:
                    problems.append((i, "неясная роль кавычки"))
        if stack:
            problems.extend((item[1], "непарная кавычка") for item in stack)
        if problems:
            # При повреждении одного абзаца/ячейки не угадываем пары в нём.
            seen = set()
            for i, reason in problems:
                context = text[max(0, i - 65):i + 100]
                if (reason, context) not in seen:
                    issues.append({"reason": reason, "context": context})
                    seen.add((reason, context))
        else:
            replacements.extend(edits)
            pairs += count
    result = value
    for start, end, replacement in sorted(replacements, reverse=True):
        result = result[:start] + replacement + result[end:]
    return {"value": result, "pairs": pairs, "issues": issues}


def text_slots(value, path=(), inherited=None):
    """Белый список текстовых значений; URL, таксономию и служебные поля исключаем."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in SKIP_KEYS or key.endswith("_id") or key.endswith("_ids"):
                continue
            if isinstance(item, str):
                if key in TEXT_KEYS or inherited == "facts":
                    yield value, key, path + (key,)
            elif isinstance(item, (list, dict)):
                yield from text_slots(item, path + (key,), key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, str) and inherited in TEXT_LISTS:
                yield value, index, path + (index,)
            elif isinstance(item, (list, dict)):
                yield from text_slots(item, path + (index,), inherited)


def mapping_slots(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in SKIP_KEYS:
                continue
            if key in {"facts", "scores"} and isinstance(item, dict):
                yield value, key, path + (key,)
            if isinstance(item, (dict, list)):
                yield from mapping_slots(item, path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from mapping_slots(item, path + (index,))


def transform_document(collection, document):
    updated = copy.deepcopy(document)
    changes, issues = [], []
    for holder, key, path in text_slots(updated):
        before = holder[key]
        dotted = ".".join(map(str, path))
        repair = (collection, document.get("slug"), dotted) in MIXED_REPAIRS
        prepared = before
        restored_pairs = 0
        for old, new, pair_count in APPROVED_REPAIRS.get((collection, document.get("_id"), dotted), []):
            restored_pairs += prepared.count(old) * pair_count
            prepared = prepared.replace(old, new)
        if (collection == "teams" and key == "description" and "events" in path
                and before.strip() == '"'):
            result = {"value": "", "pairs": 0, "issues": []}
        else:
            result = normalize_text(prepared, repair_mixed=repair)
        result["pairs"] += restored_pairs
        issues.extend({"path": dotted, **issue} for issue in result["issues"])
        if result["value"] != before:
            holder[key] = result["value"]
            changes.append({"path": dotted, "before": before, "after": holder[key],
                            "pairs": result["pairs"], "manual_repair": prepared != before})
    # Ключи facts + facts_order и scores + contests — связанные подписи.
    # Обновляем и источник seasons, и его публичные/производные копии.
    for container, mapping_key, path in list(mapping_slots(updated)):
        facts = container[mapping_key]
        dotted = ".".join(map(str, path))
        for key in list(facts):
            result = normalize_text(key)
            issues.extend({"path": dotted + ".{key}", **issue} for issue in result["issues"])
            new_key = result["value"]
            if new_key == key:
                continue
            if new_key in facts:
                reason = "конфликт названий фактов" if mapping_key == "facts" else "конфликт названий оценок"
                issues.append({"path": dotted + ".{key}", "reason": reason, "context": key})
                continue
            # Сохраняем порядок словаря, используемый страницами без facts_order.
            container[mapping_key] = {new_key if k == key else k: v for k, v in facts.items()}
            facts = container[mapping_key]
            changes.append({"path": dotted + ".{key}", "before": key, "after": new_key, "pairs": result["pairs"]})
            if mapping_key == "facts" and isinstance(container.get("facts_order"), list):
                container["facts_order"] = [new_key if x == key else x for x in container["facts_order"]]
    return updated, changes, issues


def public_url(collection, document):
    path = document.get("page_path") if collection == "seasons" else document.get("full_path")
    if path:
        if collection == "shows":
            return "/shows/" + path.lstrip("/")
        return "/" + path.lstrip("/")
    slug = document.get("slug", "")
    prefix = {"teams": "kvn/teams", "cities": "city"}.get(collection, collection)
    return "/" + prefix + "/" + slug


def save_json(path, value):
    from bson import json_util
    path.write_text(json_util.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


async def make_plan(directory):
    from utils.database import close_db, get_db
    db = await get_db()
    directory.mkdir(parents=True, exist_ok=True)
    plan, changes, issues, counts = [], [], [], {}
    try:
        for collection in COLLECTIONS:
            counts[collection] = {"scanned": 0, "changed": 0, "fields": 0, "pairs": 0}
            async for document in db[collection].find({}):
                counts[collection]["scanned"] += 1
                updated, doc_changes, doc_issues = transform_document(collection, document)
                info = {"collection": collection, "id": document["_id"],
                        "slug": document.get("slug"), "url": public_url(collection, document)}
                issues.extend({**info, **issue} for issue in doc_issues)
                if not doc_changes:
                    continue
                roots = {key for key in document if document[key] != updated[key]}
                plan.append({**info, "before": {key: document[key] for key in sorted(roots)},
                             "after": {key: updated[key] for key in sorted(roots)}})
                changes.extend({**info, **change} for change in doc_changes)
                counts[collection]["changed"] += 1
                counts[collection]["fields"] += len(doc_changes)
                counts[collection]["pairs"] += sum(change["pairs"] for change in doc_changes)
        summary = {"mode": "dry-run", "collections": counts, "documents": len(plan),
                   "fields": len(changes), "pairs": sum(x["pairs"] for x in changes),
                   "issues": len(issues)}
        save_json(directory / "plan.json", plan)
        save_json(directory / "changes.json", changes)
        save_json(directory / "issues.json", issues)
        save_json(directory / "summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        await close_db()


async def apply_plan(path):
    from bson import json_util
    from utils.database import close_db, get_db
    from services.cache import cache_service
    plan = json_util.loads(path.read_text(encoding="utf-8"))
    db = await get_db()
    counts = Counter()
    log = path.with_name("applied.jsonl")
    try:
        # Проверяем весь план до первой записи; конфликт требует нового dry-run.
        for item in plan:
            current = await db[item["collection"]].find_one({"_id": item["id"]})
            if current is None or any(current.get(k) != v for k, v in item["before"].items()):
                raise RuntimeError(f'Контент изменился после dry-run: {item["collection"]}/{item["slug"]}')
        with log.open("a", encoding="utf-8") as stream:
            for item in plan:
                query = {"_id": item["id"], **item["before"]}
                fields = {**item["after"], "updated_at": datetime.now(timezone.utc).isoformat()}
                # Сохраняем запись для восстановления до изменения БД.
                stream.write(json_util.dumps(item, ensure_ascii=False) + "\n")
                stream.flush()
                result = await db[item["collection"]].update_one(query, {"$set": fields})
                if result.matched_count != 1:
                    raise RuntimeError(f'Конкурентное изменение: {item["collection"]}/{item["slug"]}')
                counts[item["collection"]] += 1
        print(json.dumps({"mode": "applied", "documents": sum(counts.values()),
                          "collections": counts}, ensure_ascii=False, indent=2))
    finally:
        # В том числе при частичном применении: действующий backend сверяет поколение кэша.
        if counts:
            await cache_service.invalidate_everywhere(db)
        await close_db()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--apply", type=Path, metavar="PLAN_JSON")
    args = parser.parse_args()
    if bool(args.report_dir) == bool(args.apply):
        parser.error("укажите либо --report-dir, либо --apply")
    asyncio.run(apply_plan(args.apply) if args.apply else make_plan(args.report_dir))


if __name__ == "__main__":
    main()
