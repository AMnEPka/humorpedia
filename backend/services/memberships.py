"""
Составы: связь «человек — команда — роль — годы».

Коллекция memberships:
{ _id, team_id, person_id|null, candidate_person_id|null, person_name, person_slug (slug со старого сайта), name_key,
  roles: ["капитан", ...], from_year, to_year, status: "current"|"former", season_ids: [],
  note, source: "manual"|"roster_text", source_ref (id модуля), link_review_status,
  reviewed_by, reviewed_at, order, created_at, updated_at }

Человек может ещё не иметь страницы (в БД почти нет людей): запись хранит имя и slug, а person_id
проставляется автоматически при появлении человека (link_person / resolve_memberships).

Разбор текстовых блоков «Состав команды» — parse_roster_html (без БД, покрыт тестами).
"""
from __future__ import annotations

import html as html_lib
import logging
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

ROSTER_TITLES = ("Состав команды", "Состав команды КВН", "Состав участников")
SOURCE_ROSTER = "roster_text"
SOURCE_MANUAL = "manual"
STATUS_CURRENT = "current"
STATUS_FORMER = "former"
LINK_CANDIDATE = "candidate"
LINK_CONFIRMED = "confirmed"
LINK_REJECTED = "rejected"

_DASHES = "–—-"
_BLOCK_TAGS = {"li", "p", "div", "h2", "h3", "h4", "h5", "tr"}
_PERSON_LINK = re.compile(r"(?:^|/)people/([a-z0-9_-]+?)(?:\.html)?/?$", re.I)
_SEASON_YEAR = re.compile(r"(?:сезон[еау]?|году?)\s*((?:19|20)\d{2})", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_aliases(text: str) -> str:
    """Линейно удалить прозвища в (), «» и "", сохранив незакрытый фрагмент."""
    closers = {"(": ")", "«": "»", '"': '"'}
    result: list[str] = []
    buffered: list[str] = []
    closing: str | None = None
    for char in text:
        if closing is None:
            if char in closers:
                closing = closers[char]
                buffered = [char]
            else:
                result.append(char)
            continue
        buffered.append(char)
        if char == closing:
            result.append(" ")
            buffered = []
            closing = None
    if buffered:
        result.extend(buffered)
    return "".join(result)


def name_key(name: str) -> str:
    """Ключ имени без учёта порядка слов, регистра и ё: «Шастун Антон» == «Антон Шастун»."""
    text = (name or "").lower().replace("ё", "е")
    text = _strip_aliases(text)
    tokens = re.findall(r"[a-zа-я0-9-]+", text)
    return " ".join(sorted(t for t in tokens if t))


# ─── Разбор HTML ───────────────────────────────────────────────────────────────

class _BlockCollector(HTMLParser):
    """Собирает текстовые блоки (li/p/div/...; <br> делит блок на строки) со ссылками."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict] = []
        self._stack: list[dict] = []
        self._href: Optional[str] = None

    def _current(self) -> Optional[dict]:
        return self._stack[-1] if self._stack else None

    def handle_starttag(self, tag, attrs):
        if tag in _BLOCK_TAGS:
            parent = self._current()
            if parent is not None and parent["parts"] and "".join(p["text"] for p in parent["parts"]).strip():
                self._flush_line(parent)
            self._stack.append({"tag": tag, "parts": [], "lines": []})
        elif tag == "br":
            block = self._current()
            if block is not None:
                self._flush_line(block)
        elif tag == "a":
            self._href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag == "a":
            self._href = None
        elif tag in _BLOCK_TAGS and self._stack:
            block = self._stack.pop()
            self._flush_line(block)
            for line in block["lines"]:
                self.blocks.append({"tag": block["tag"], **line})

    def handle_data(self, data):
        block = self._current()
        if block is None:
            if data.strip():
                self.blocks.append({"tag": "text", "text": data.strip(), "links": []})
            return
        block["parts"].append({"text": data, "href": self._href})

    @staticmethod
    def _flush_line(block: dict):
        text = "".join(p["text"] for p in block["parts"])
        links = [{"text": p["text"].strip(), "href": p["href"]} for p in block["parts"] if p["href"] and p["text"].strip()]
        if text.strip():
            block["lines"].append({"text": re.sub(r"\s+", " ", text).strip(), "links": links})
        block["parts"] = []


_PAREN = re.compile(r"\(([^()]*)\)")
_YEAR = r"((?:19|20)\d{2})"

_ROLE_SYNONYMS = {
    "капитан команды": "капитан",
    "директор команды": "директор",
    "руководитель команды": "руководитель",
    "основатель команды": "основатель",
    "создатель команды": "основатель",
    "создатель": "основатель",
    "учредитель": "основатель",
    "звукач": "звукооператор",
    "звукарь": "звукооператор",
    "звукорежиссер": "звукорежиссёр",
    "админ": "администратор",
    "фрнтмен": "фронтмен",
    "фронтмен команды": "фронтмен",
}


def normalize_role(role: str) -> str:
    role = re.sub(r"\s+", " ", role.strip(" *.,;:")).lower()
    return _ROLE_SYNONYMS.get(role, role)


def parse_years(note: str) -> dict:
    """Годы из пометки: «с 2022» → from; «до 2021» → to, бывший; «2017-2019» → from/to; «2013 и 2017» → min/max."""
    text = note.lower()
    result = {"from_year": None, "to_year": None, "former": False}
    span = re.search(_YEAR + r"\s*[" + _DASHES + r"]\s*" + _YEAR, text)
    since = re.search(r"\bс\s+" + _YEAR, text)
    until = re.search(r"\bдо\s+(?:\D{0,20}?)" + _YEAR, text)
    years = [int(y) for y in re.findall(_YEAR, text)]
    if span:
        result["from_year"], result["to_year"] = int(span.group(1)), int(span.group(2))
    elif since:
        result["from_year"] = int(since.group(1))
    elif until:
        result["to_year"] = int(until.group(1))
    elif years:
        result["from_year"], result["to_year"] = min(years), max(years)
    if result["to_year"] or re.search(r"покинул|бывш", text):
        result["former"] = True
    return result


def _split_name_and_role(text: str) -> tuple[str, str]:
    for sep in (" – ", " — ", " - ", "– ", "— "):
        if sep in text:
            name, role = text.split(sep, 1)
            return name.strip(), role.strip()
    if ", " in text:
        name, role = text.split(", ", 1)
        if len(name.split()) <= 4:
            return name.strip(), role.strip()
    return text.strip(), ""


def _looks_like_name(text: str) -> bool:
    words = text.split()
    return 1 <= len(words) <= 5 and not text.endswith(":") and not re.search(r"\d{3,}", text)


def _header_context(text: str) -> Optional[dict]:
    """Строка-заголовок раздела состава: «Бывшие участники:», «Присоединившиеся … в сезоне 2025:», «Авторы:»."""
    lowered = text.lower().rstrip(":").strip()
    is_header = text.rstrip().endswith(":") or bool(re.search(r"бывш|присоедин|ранее|также|в разные годы", lowered))
    if not is_header:
        return None
    ctx: dict = {"status": STATUS_CURRENT, "role": "", "from_year": None, "header": text}
    if re.search(r"бывш|ранее|в разные годы|покинул", lowered):
        ctx["status"] = STATUS_FORMER
    season = _SEASON_YEAR.search(lowered)
    if season:
        ctx["from_year"] = int(season.group(1))
    for role in ("автор", "музыкант", "администратор", "директор", "редактор", "тренер"):
        if lowered.startswith(role):
            ctx["role"] = role
    return ctx


def parse_roster_html(content: str) -> dict:
    """
    Разобрать HTML текстового блока состава.
    Возвращает {"entries": [...], "complete": bool, "unparsed": [строки, которые не удалось разобрать]}.
    complete=True — весь текст блока превратился в записи и заголовки разделов (блок можно заменить структурой).
    """
    collector = _BlockCollector()
    collector.feed(content or "")
    collector.close()

    entries: list[dict] = []
    unparsed: list[str] = []
    context = {"status": STATUS_CURRENT, "role": "", "from_year": None}

    for block in collector.blocks:
        text = html_lib.unescape(block["text"]).strip()
        if not text:
            continue
        header = _header_context(text) if block["tag"] != "li" else None
        if header:
            context = header
            continue

        # Пометки в скобках с годами/событиями: «(с 2022)», «(2017-2019)», «(до 2021)», «(играла в сезонах 2010-2011)».
        # Скобки без цифр — прозвища («Ольга (Лёля) Климентьева») — остаются частью имени.
        notes = [m.group(1).strip() for m in _PAREN.finditer(text) if re.search(r"\d|покинул|вернул", m.group(1))]
        clean = _PAREN.sub(lambda m: " " if re.search(r"\d|покинул|вернул", m.group(1)) else m.group(0), text)
        clean = re.sub(r"\s+", " ", clean).strip()

        name, role_text = _split_name_and_role(clean)
        name = name.strip(" *.,;:")
        if not _looks_like_name(name):
            unparsed.append(text)
            continue

        from_year, to_year, status = context.get("from_year"), None, context.get("status", STATUS_CURRENT)
        for note in notes:
            years = parse_years(note)
            from_year = years["from_year"] or from_year
            to_year = years["to_year"] or to_year
            if years["former"]:
                status = STATUS_FORMER

        roles = []
        for piece in re.split(r",\s*|\s+и\s+", role_text):
            piece = piece.strip(" *.,;:")
            if re.search(_YEAR, piece):  # «капитан с 1997», «покинул команду после финала 2018 года»
                years = parse_years(piece)
                from_year = years["from_year"] or from_year
                to_year = years["to_year"] or to_year
                if years["former"]:
                    status = STATUS_FORMER
                notes.append(piece)
                piece = re.sub(r"\s*\b(?:с|до|по)?\s*(?:19|20)\d{2}.*$", "", piece).strip()
            if not piece:
                continue
            if len(piece.split()) > 4 or re.search(r"покинул|выступ|сыграл|рассказ|вернул", piece.lower()):
                notes.append(piece)  # пояснение, а не роль
                continue
            roles.append(normalize_role(piece))
        if not roles and context.get("role"):
            roles = [context["role"]]

        person_slug = None
        for link in block["links"]:
            match = _PERSON_LINK.search(link["href"] or "")
            if match:
                person_slug = match.group(1).lower()
                break

        entries.append({
            "person_name": name,
            "person_slug": person_slug,
            "name_key": name_key(name),
            "roles": roles,
            "from_year": from_year,
            "to_year": to_year,
            "status": status,
            "note": "; ".join(notes) + (" *" if "*" in text else ""),
            "raw": text,
        })

    return {"entries": entries, "complete": bool(entries) and not unparsed, "unparsed": unparsed}


def find_roster_modules(team: dict) -> list[dict]:
    return [
        m for m in team.get("modules") or []
        if m.get("type") == "text_block" and (m.get("data") or {}).get("title") in ROSTER_TITLES
    ]


# ─── Люди ──────────────────────────────────────────────────────────────────────

class PersonLookup:
    """Поиск человека по slug (старого сайта или текущему) и по имени (только если имя однозначно)."""

    def __init__(self, people: Iterable[dict] = ()):
        self.by_slug: dict[str, str] = {}
        self.by_key: dict[str, Optional[str]] = {}
        for person in people:
            person_id = str(person["_id"])
            if person.get("slug"):
                self.by_slug[person["slug"].lower()] = person_id
            for url in person.get("old_urls") or []:
                match = _PERSON_LINK.search(url.strip("/"))
                if match:
                    self.by_slug.setdefault(match.group(1).lower(), person_id)
            for key in person_keys(person):
                # один ключ у разных людей — неоднозначно, по имени не связываем
                self.by_key[key] = person_id if self.by_key.get(key, person_id) == person_id else None

    def resolve(self, slug: Optional[str] = None, name: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
        """Вернуть (person_id, способ: "slug" | "name")."""
        if slug and slug.lower() in self.by_slug:
            return self.by_slug[slug.lower()], "slug"
        key = name_key(name or "")
        if key and self.by_key.get(key):
            return self.by_key[key], "name"
        return None, None


def person_keys(person: dict) -> set[str]:
    keys = {name_key(person.get(field) or "") for field in ("full_name", "title")}
    for alias in person.get("aliases") or []:
        keys.add(name_key(alias))
    keys.discard("")
    return keys


def membership_link_reason(membership: dict, lookup: PersonLookup) -> Optional[str]:
    """Причина, по которой связь требует редакторской проверки."""
    target_id = membership.get("candidate_person_id") or membership.get("person_id")
    if not target_id or membership.get("link_review_status") in (LINK_CONFIRMED, LINK_REJECTED):
        return None
    slug = (membership.get("person_slug") or "").lower()
    if not slug:
        return "name_only"
    source_person_id = lookup.by_slug.get(slug)
    if not source_person_id:
        return "slug_unresolved"
    if source_person_id != target_id:
        return "slug_conflict"
    return None


def membership_review_status(membership: dict, lookup: PersonLookup) -> str:
    explicit = membership.get("link_review_status")
    if explicit in (LINK_CANDIDATE, LINK_CONFIRMED, LINK_REJECTED):
        return explicit
    if membership.get("person_link_disabled"):
        return LINK_REJECTED
    if membership_link_reason(membership, lookup):
        return LINK_CANDIDATE
    if membership.get("person_id"):
        return LINK_CONFIRMED
    return "unresolved"


def preserve_pending_public_link(doc: dict, existing: Optional[dict], lookup: PersonLookup) -> dict:
    """Не скрывать старую сомнительную связь при повторном импорте до решения редактора."""
    if existing and membership_review_status(existing, lookup) == LINK_CANDIDATE and existing.get("person_id"):
        doc.update({
            "person_id": existing["person_id"],
            "candidate_person_id": existing.get("candidate_person_id"),
            "matched_by": existing.get("matched_by"),
            "link_review_status": LINK_CANDIDATE,
        })
    return doc


async def load_person_lookup(db) -> PersonLookup:
    people = await db.people.find({}, {"_id": 1, "slug": 1, "full_name": 1, "title": 1, "aliases": 1, "old_urls": 1}).to_list(None)
    return PersonLookup(people)


# ─── Импорт составов из текстовых блоков ───────────────────────────────────────

def memberships_from_team(team: dict, lookup: PersonLookup) -> tuple[list[dict], list[dict]]:
    """Записи составов из текстовых блоков команды + отчёт по блокам [{module_id, complete, unparsed, count}]."""
    from services.competitions import stable_id

    docs, report = [], []
    for module in find_roster_modules(team):
        parsed = parse_roster_html((module.get("data") or {}).get("content") or "")
        report.append({
            "module_id": module.get("id"), "complete": parsed["complete"],
            "unparsed": parsed["unparsed"], "count": len(parsed["entries"]),
        })
        for order, entry in enumerate(parsed["entries"]):
            resolved_person_id, matched_by = lookup.resolve(entry["person_slug"], entry["person_name"])
            person_id = resolved_person_id if matched_by == "slug" else None
            candidate_person_id = resolved_person_id if matched_by == "name" else None
            docs.append({
                "_id": stable_id("membership", team["_id"], module.get("id"), order),
                "team_id": team["_id"],
                "person_id": person_id,
                "candidate_person_id": candidate_person_id,
                "matched_by": matched_by,
                "link_review_status": LINK_CONFIRMED if person_id else (LINK_CANDIDATE if candidate_person_id else None),
                "person_name": entry["person_name"],
                "person_slug": entry["person_slug"],
                "name_key": entry["name_key"],
                "roles": entry["roles"],
                "from_year": entry["from_year"],
                "to_year": entry["to_year"],
                "status": entry["status"],
                "season_ids": [],
                "note": entry["note"],
                "source": SOURCE_ROSTER,
                "source_ref": module.get("id"),
                "order": order,
            })
    return docs, report


async def import_team_rosters(db, team: dict, lookup: Optional[PersonLookup] = None) -> dict:
    """
    Перезаписать записи состава команды, импортированные из текста.
    Ручные записи не трогаются; люди, уже заведённые вручную, из текста не дублируются.
    Один человек в нескольких блоках состава объединяется в одну запись (роли складываются).
    """
    lookup = lookup or await load_person_lookup(db)
    docs, report = memberships_from_team(team, lookup)

    existing_roster = {
        m["name_key"]: m async for m in db.memberships.find(
            {"team_id": team["_id"], "source": SOURCE_ROSTER}
        ) if m.get("name_key")
    }

    manual_keys = {
        m["name_key"] async for m in db.memberships.find(
            {"team_id": team["_id"], "source": {"$ne": SOURCE_ROSTER}}, {"name_key": 1}
        )
    }
    merged: dict[str, dict] = {}
    for doc in docs:
        key = doc["name_key"]
        if not key or key in manual_keys:
            continue
        preserve_pending_public_link(doc, existing_roster.get(key), lookup)
        if key in merged:
            target = merged[key]
            target["roles"] += [r for r in doc["roles"] if r not in target["roles"]]
            for field in ("person_id", "candidate_person_id", "matched_by", "person_slug", "from_year", "to_year"):
                target[field] = target[field] or doc[field]
            if doc["status"] == STATUS_CURRENT:
                target["status"] = STATUS_CURRENT
            continue
        merged[key] = doc

    now = now_iso()
    await db.memberships.delete_many({"team_id": team["_id"], "source": SOURCE_ROSTER})
    if merged:
        for doc in merged.values():
            doc["created_at"] = doc["updated_at"] = now
        await db.memberships.insert_many(list(merged.values()), ordered=False)
    roster_meta = [{"module_id": r["module_id"], "complete": r["complete"], "count": r["count"]} for r in report]
    await db.teams.update_one({"_id": team["_id"]}, {"$set": {"roster_import": roster_meta}})
    return {"team_id": team["_id"], "memberships": len(merged), "blocks": report}


async def import_all_rosters(db, query: Optional[dict] = None) -> dict:
    lookup = await load_person_lookup(db)
    stats = {"teams": 0, "memberships": 0, "complete_blocks": 0, "blocks": 0, "errors": []}
    base = {"modules": {"$elemMatch": {"type": "text_block", "data.title": {"$in": list(ROSTER_TITLES)}}}}
    async for team in db.teams.find({"$and": [base, query]} if query else base, {"modules": 1, "slug": 1}):
        try:
            result = await import_team_rosters(db, team, lookup)
        except Exception as e:
            stats["errors"].append(f"{team.get('slug')}: {e}")
            logger.error(f"Memberships: импорт состава {team.get('slug')} не удался: {e}", exc_info=True)
            continue
        stats["teams"] += 1
        stats["memberships"] += result["memberships"]
        stats["blocks"] += len(result["blocks"])
        stats["complete_blocks"] += sum(1 for b in result["blocks"] if b["complete"])
    return stats


async def ensure_rosters_imported(db) -> None:
    """При старте: если записей составов ещё нет — импортировать из текстовых блоков."""
    try:
        if await db.memberships.estimated_document_count() > 0:
            return
        stats = await import_all_rosters(db)
        if stats["teams"]:
            logger.info(f"Memberships: первичный импорт составов: {stats}")
    except Exception as e:
        logger.error(f"Memberships: первичный импорт не удался: {e}", exc_info=True)


async def link_person(db, person: dict) -> int:
    """Связать явный slug; совпадение только по имени сохранить кандидатом для редактора."""
    person_id = str(person["_id"])
    lookup = await load_person_lookup(db)
    slugs = [s for s, pid in lookup.by_slug.items() if pid == person_id]
    keys = [k for k, pid in lookup.by_key.items() if pid == person_id]
    now = now_iso()
    slug_result = await db.memberships.update_many(
        {
            "person_id": None,
            "person_link_disabled": {"$ne": True},
            "person_slug": {"$in": slugs},
        },
        {"$set": {
            "person_id": person_id,
            "candidate_person_id": None,
            "matched_by": "slug",
            "link_review_status": LINK_CONFIRMED,
            "updated_at": now,
        }},
    )
    name_result = await db.memberships.update_many(
        {
            "person_id": None,
            "person_link_disabled": {"$ne": True},
            "name_key": {"$in": keys},
            "$or": [{"person_slug": None}, {"person_slug": ""}, {"person_slug": {"$nin": slugs}}],
        },
        {"$set": {
            "candidate_person_id": person_id,
            "matched_by": "name",
            "link_review_status": LINK_CANDIDATE,
            "updated_at": now,
        }},
    )
    return slug_result.modified_count + name_result.modified_count


def linkable_memberships_query(slugs: list[str], keys: list[str]) -> dict:
    """Автосвязь не должна отменять ручное решение редактора оставить однофамильца без страницы."""
    return {
        "person_id": None,
        "person_link_disabled": {"$ne": True},
        "$or": [{"person_slug": {"$in": slugs}}, {"name_key": {"$in": keys}}],
    }


async def unlink_person(db, person_id: str) -> int:
    result = await db.memberships.update_many(
        {"person_id": person_id},
        {
            "$set": {"person_id": None, "matched_by": None, "updated_at": now_iso()},
            "$unset": {"link_review_status": "", "candidate_person_id": ""},
        },
    )
    return result.modified_count


async def create_membership_indexes(ensure_index, db) -> None:
    await ensure_index(db.memberships, [("team_id", 1), ("status", 1), ("order", 1)])
    await ensure_index(db.memberships, "person_id")
    await ensure_index(db.memberships, "candidate_person_id", sparse=True)
    await ensure_index(db.memberships, "link_review_status", sparse=True)
    await ensure_index(db.memberships, "person_slug", sparse=True)
    await ensure_index(db.memberships, "name_key")
