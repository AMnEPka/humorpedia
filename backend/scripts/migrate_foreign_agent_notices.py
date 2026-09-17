"""Move legacy foreign-agent stars/footnotes into structured person flags.

Dry-run by default. Pass --apply to update MongoDB.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.database import close_db, get_db


PEOPLE = {
    "ruslan-belyi": r"(?:Руслан(?:а|ом|у)?\s+(?:Викторович\s+)?Бел(?:ый|ого|ым|ому)|Бел(?:ый|ого|ым|ому)|Руслан(?:а|ом|у)?)",
    "danila-poperechniy": r"(?:Данил(?:а|ы|е)?(?:\s+Алексеевич)?(?:\s+Поперечн(?:ый|ого|ому|ым))?|Поперечн(?:ый|ого|ому|ым))",
    "mikhail-shats": r"(?:Михаил(?:а|ом|у)?(?:\s+Григорьевич)?(?:\s+Шац(?:а)?)?|Шац(?:а)?)",
    "evgeniy-trikoz": r"(?:Евгени(?:й|я|ю|ем)(?:\s+Сергеевич)?(?:\s+Трикоз(?:а)?)?|Трикоз(?:а)?)",
}

NAME_PATTERNS = [
    (slug, re.compile(rf"(?<![А-ЯЁа-яё])({pattern})", re.I))
    for slug, pattern in PEOPLE.items()
]
MENTION_PATTERNS = [
    (slug, re.compile(rf"{pattern.pattern}\s*(\*+)", re.I))
    for slug, pattern in NAME_PATTERNS
]
GENERIC_NOTE_PARAGRAPH_RE = re.compile(
    r"<p[^>]*>\s*(\*+)\s*[-–—]\s*признан(?:а)?\s+в\s+РФ\s+иностранным\s+агентом\.?\s*</p>",
    re.I,
)
SPECIAL_TATYANA_NOTE_RE = re.compile(
    r"(<p[^>]*>)\s*\*\s*([-–—]\s*признана\s+в\s+РФ\s+иностранным\s+агентом,\s*экстремистом\s+и\s+террористом\.?)\s*(</p>)",
    re.I,
)
SPECIAL_TATYANA_MENTION_RE = re.compile(
    r"(Татья(?:на|ной|ны)\s+Лазарев(?:а|ой|у)|Лазарев(?:а|ой|у))\*(?!\*)",
    re.I,
)
UNLINKED_FOREIGN_AGENT_PATTERNS = (
    (
        re.compile(r"(Максим(?:а|ом|у)?\s+Покровск(?:ий|ого|ому|им))\*(?!\*)", re.I),
        "*",
        "признан в РФ иностранным агентом",
    ),
)
ANCHOR_RE = re.compile(r"(<a\b[^>]*\bhref\s*=\s*([\"'])(.*?)\2[^>]*>)(.*?)(</a\s*>)(\s*\*+)?", re.I | re.S)
TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")


def link_known_mentions(value: str) -> tuple[str, int]:
    """Replace legacy stars with semantic annotations, without creating person links."""
    changed = 0

    def normalize_anchor(match: re.Match[str]) -> str:
        nonlocal changed
        href = match.group(3).split("?", 1)[0].split("#", 1)[0].rstrip("/")
        slug = href.rsplit("/", 1)[-1]
        body_without_star = re.sub(r"\s*\*+\s*$", "", match.group(4))
        detected_slug = slug if slug in PEOPLE else None
        detected_pattern = None
        for candidate_slug, pattern in NAME_PATTERNS:
            if pattern.search(match.group(4)):
                if not detected_slug:
                    detected_slug = candidate_slug
                detected_pattern = pattern
                break
        if not detected_slug:
            return match.group(0)
        body = body_without_star
        if slug in PEOPLE and detected_pattern:
            replacement = f'<span data-foreign-agent-person="{detected_slug}">{body}</span>'
            if replacement != match.group(0):
                changed += 1
            return replacement
        if body == match.group(4) and not match.group(6):
            return match.group(0)
        changed += 1
        opening = match.group(1)
        if slug not in PEOPLE and "data-foreign-agent-person" not in opening:
            opening = opening[:-1] + f' data-foreign-agent-person="{detected_slug}">'
        return f"{opening}{body}{match.group(5)}"

    value = ANCHOR_RE.sub(normalize_anchor, value)
    parts = TAG_SPLIT_RE.split(value)
    anchor_depth = 0
    output = []
    for part in parts:
        if part.lower().startswith("<a "):
            anchor_depth += 1
            output.append(part)
            continue
        if part.lower().startswith("</a"):
            anchor_depth = max(0, anchor_depth - 1)
            output.append(part)
            continue
        if part.startswith("<") or anchor_depth:
            output.append(part)
            continue
        text = part
        for slug, pattern in MENTION_PATTERNS:
            def replace(match: re.Match[str], person_slug: str = slug) -> str:
                nonlocal changed
                changed += 1
                return f'<span data-foreign-agent-person="{person_slug}">{match.group(1)}</span>'
            text = pattern.sub(replace, text)
        output.append(text)
    return "".join(output), changed


def clean_subject_value(value: str, slug: str) -> str:
    pattern = next(pattern for item_slug, pattern in MENTION_PATTERNS if item_slug == slug)
    return pattern.sub(lambda match: match.group(1), value)


def rich_text_slots(document: dict):
    if isinstance(document.get("content"), str):
        yield document, "content"
    for module in document.get("modules") or []:
        data = module.get("data") or {}
        if isinstance(data.get("content"), str):
            yield data, "content"
        for event in data.get("events") or data.get("items") or []:
            if isinstance(event, dict) and isinstance(event.get("description"), str):
                yield event, "description"
        for row in data.get("rows") or []:
            if not isinstance(row, list):
                continue
            for index, cell in enumerate(row):
                if isinstance(cell, str):
                    yield row, index


def remaining_star_counts(document: dict) -> set[int]:
    result: set[int] = set()
    for holder, key in rich_text_slots(document):
        value = holder[key]
        if GENERIC_NOTE_PARAGRAPH_RE.search(value):
            value = GENERIC_NOTE_PARAGRAPH_RE.sub("", value)
        result.update(len(match.group(0)) for match in re.finditer(r"\*+", value))
    return result


def remove_obsolete_notes(document: dict) -> int:
    remaining = remaining_star_counts(document)
    removed = 0
    modules = []
    for module in document.get("modules") or []:
        data = module.get("data") or {}
        content = data.get("content")
        if not isinstance(content, str) or not GENERIC_NOTE_PARAGRAPH_RE.search(content):
            modules.append(module)
            continue

        def replace(match: re.Match[str]) -> str:
            nonlocal removed
            if len(match.group(1)) in remaining:
                return match.group(0)
            removed += 1
            return ""

        data["content"] = GENERIC_NOTE_PARAGRAPH_RE.sub(replace, content).strip()
        if data["content"]:
            modules.append(module)
    document["modules"] = modules
    return removed


def annotate_unlinked_foreign_agents(document: dict) -> int:
    """Structure marked mentions even when the person has no page yet."""
    changed = 0
    for holder, key in rich_text_slots(document):
        value = holder[key]
        updated = value
        for pattern, marker, notice in UNLINKED_FOREIGN_AGENT_PATTERNS:
            updated, count = pattern.subn(
                rf'<span data-foreign-agent-marker="{marker}" '
                rf'data-foreign-agent-notice="{notice}">\1</span>',
                updated,
            )
            changed += count
        if updated != value:
            holder[key] = updated
    return changed


def normalize_special_tatyana_marker(document: dict) -> int:
    """Replace Tatyana Lazareva's legacy star and footnote with structured metadata."""
    has_special_note = any(
        SPECIAL_TATYANA_NOTE_RE.search(holder[key])
        for holder, key in rich_text_slots(document)
    )
    if not has_special_note:
        return 0
    changed = 0
    for holder, key in rich_text_slots(document):
        value = holder[key]
        updated = SPECIAL_TATYANA_MENTION_RE.sub(
            r'<span data-foreign-agent-marker="**" data-foreign-agent-notice="признана в РФ иностранным агентом, экстремистом и террористом">\1</span>',
            value,
        )
        updated = SPECIAL_TATYANA_NOTE_RE.sub("", updated).strip()
        if updated != value:
            holder[key] = updated
            changed += 1
    return changed


def remove_empty_text_modules(document: dict) -> int:
    """Drop text cards left empty after legacy footnotes are removed."""
    modules = document.get("modules") or []
    kept = []
    removed = 0
    for module in modules:
        content = (module.get("data") or {}).get("content")
        if module.get("type") == "text_block" and isinstance(content, str) and not content.strip():
            removed += 1
            continue
        kept.append(module)
    document["modules"] = kept
    return removed


def clean_flagged_person(document: dict, slug: str) -> None:
    for key in ("title", "full_name", "primary_tag"):
        if isinstance(document.get(key), str):
            document[key] = clean_subject_value(document[key], slug).strip()
    for container, key in (
        (document.get("seo") or {}, "meta_title"),
        (document.get("seo") or {}, "meta_description"),
        (document.get("photo") or {}, "alt"),
    ):
        if isinstance(container.get(key), str):
            container[key] = clean_subject_value(container[key], slug).strip()
    for key, value in (document.get("facts") or {}).items():
        if isinstance(value, str):
            document["facts"][key] = clean_subject_value(value, slug)


async def migrate(apply: bool) -> dict:
    db = await get_db()
    stats = {
        "people_flagged": 0,
        "mentions_linked": 0,
        "unlinked_markers_fixed": 0,
        "notes_removed": 0,
        "empty_text_modules_removed": 0,
        "special_markers_fixed": 0,
        "documents_changed": 0,
    }

    for slug in PEOPLE:
        person = await db.people.find_one({"slug": slug})
        if not person:
            continue
        updated = copy.deepcopy(person)
        updated["foreign_agent"] = True
        clean_flagged_person(updated, slug)
        if updated != person:
            stats["people_flagged"] += 1
            if apply:
                await db.people.replace_one({"_id": person["_id"]}, updated)

    for collection_name in ("people", "articles", "news", "cities", "shows"):
        collection = db[collection_name]
        async for document in collection.find({}):
            updated = copy.deepcopy(document)
            mentions = 0
            for holder, key in rich_text_slots(updated):
                holder[key], count = link_known_mentions(holder[key])
                mentions += count
            unlinked_markers = annotate_unlinked_foreign_agents(updated)
            notes = remove_obsolete_notes(updated)
            special_markers = normalize_special_tatyana_marker(updated)
            empty_modules = remove_empty_text_modules(updated)
            if updated == document:
                continue
            stats["documents_changed"] += 1
            stats["mentions_linked"] += mentions
            stats["unlinked_markers_fixed"] += unlinked_markers
            stats["notes_removed"] += notes
            stats["empty_text_modules_removed"] += empty_modules
            stats["special_markers_fixed"] += special_markers
            if apply:
                await collection.replace_one({"_id": document["_id"]}, updated)

    await close_db()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write changes to MongoDB")
    args = parser.parse_args()
    stats = asyncio.run(migrate(args.apply))
    print(("APPLIED" if args.apply else "DRY RUN"), stats)


if __name__ == "__main__":
    main()
