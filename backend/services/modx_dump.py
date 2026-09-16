"""
Чтение SQL-дампа MODX (phpMyAdmin / mysqldump) без MySQL.

Дамп читается потоково, разбираются только INSERT'ы нужных таблиц. Каждая строка INSERT
превращается в dict «колонка → значение» (строки MySQL разэкранируются, числа приводятся к int/float,
NULL → None).

    site = load_modx_site("/app/backups/idemsku8_modx2.sql")
    site.resources[116]["pagetitle"], site.tv(116, "config"), site.tags_of(116)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Tuple

_INSERT_RE = re.compile(r"^INSERT INTO `(\w+)` \(([^)]*)\) VALUES\s*(.*)$", re.S)
_TOKEN_RE = re.compile(
    r"""\s*(?:'((?:[^'\\]|\\.|'')*)'|(NULL)|([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)|([(),;]))""",
    re.S,
)
_ESCAPES = {"0": "\x00", "b": "\b", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a"}
_ESCAPE_RE = re.compile(r"\\(.)|''", re.S)


def unescape_mysql(value: str) -> str:
    """Снять экранирование строкового литерала MySQL."""

    def repl(m: re.Match) -> str:
        if m.group(0) == "''":
            return "'"
        ch = m.group(1)
        if ch in "%_":  # \% и \_ MySQL оставляет как есть
            return "\\" + ch
        return _ESCAPES.get(ch, ch)

    return _ESCAPE_RE.sub(repl, value)


def _number(text: str):
    return float(text) if any(c in text for c in ".eE") else int(text)


def parse_values(text: str, pos: int = 0) -> Tuple[List[list], int, bool]:
    """Разобрать последовательность кортежей `(...), (...);` начиная с pos.

    Возвращает (кортежи, позиция после последнего полного кортежа, встретилась ли `;`).
    Незавершённый хвост (кортеж, оборванный концом текста) не возвращается.
    """
    rows: List[list] = []
    last_complete = pos
    current: Optional[list] = None
    n = len(text)
    while pos < n:
        m = _TOKEN_RE.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            if current is None:
                raise ValueError(f"Неожиданный фрагмент SQL: {text[pos:pos + 80]!r}")
            break  # оборванная строка — ждём продолжения
        pos = m.end()
        string, null, number, punct = m.groups()
        if current is None:
            if punct == "(":
                current = []
            elif punct == ";":
                return rows, pos, True
            elif punct == ",":
                continue
            else:
                raise ValueError(f"Ожидалась '(' в SQL: {text[m.start():m.start() + 80]!r}")
        elif string is not None:
            current.append(unescape_mysql(string))
        elif null:
            current.append(None)
        elif number is not None:
            current.append(_number(number))
        elif punct == ")":
            rows.append(current)
            current = None
            last_complete = pos
        elif punct == ",":
            continue
        else:
            raise ValueError(f"Неожиданный токен SQL: {text[m.start():m.start() + 80]!r}")
    return rows, last_complete, False


def iter_table_rows(lines: Iterable[str], tables: Iterable[str]) -> Iterator[Tuple[str, dict]]:
    """Пройти по строкам дампа и выдать (таблица, строка) для INSERT'ов из tables."""
    wanted = set(tables)
    it = iter(lines)
    for line in it:
        if not line.startswith("INSERT INTO `"):
            continue
        m = _INSERT_RE.match(line)
        if not m or m.group(1) not in wanted:
            continue
        table = m.group(1)
        columns = [c.strip().strip("`") for c in m.group(2).split(",")]
        buffer = m.group(3)
        while True:
            rows, consumed, finished = parse_values(buffer)
            for row in rows:
                if len(row) != len(columns):
                    raise ValueError(f"{table}: {len(row)} значений на {len(columns)} колонок")
                yield table, dict(zip(columns, row))
            if finished:
                break
            buffer = buffer[consumed:]
            try:
                buffer += next(it)
            except StopIteration:
                if buffer.strip():
                    raise ValueError(f"{table}: дамп оборван посреди INSERT")
                break


@dataclass
class ModxSite:
    """Нужные для импорта данные сайта MODX."""
    resources: Dict[int, dict] = field(default_factory=dict)       # id → строка modx_site_content
    tv_names: Dict[int, str] = field(default_factory=dict)         # id TV → имя
    tv_values: Dict[int, Dict[str, str]] = field(default_factory=dict)  # resource → {имя TV: значение}
    tags: Dict[int, str] = field(default_factory=dict)             # id тега → название
    tag_resources: Dict[int, List[int]] = field(default_factory=dict)  # resource → [id тегов]
    by_uri: Dict[str, int] = field(default_factory=dict)           # uri без слэшей по краям → id

    def tv(self, resource_id: int, name: str) -> str:
        return self.tv_values.get(resource_id, {}).get(name) or ""

    def tags_of(self, resource_id: int) -> List[str]:
        """Теги ресурса в порядке, заданном в TV `tags` (как в админке MODX), затем остальные привязки."""
        ordered: List[int] = []
        for part in self.tv(resource_id, "tags").split("||"):
            if part.strip().isdigit():
                ordered.append(int(part))
        for tag_id in self.tag_resources.get(resource_id, []):
            if tag_id not in ordered:
                ordered.append(tag_id)
        names: List[str] = []
        for tag_id in ordered:
            name = (self.tags.get(tag_id) or "").strip()
            if name and name not in names:
                names.append(name)
        return names

    def resource_by_uri(self, uri: str) -> Optional[dict]:
        rid = self.by_uri.get(uri.strip("/"))
        return self.resources.get(rid) if rid is not None else None


# Большие текстовые колонки, которые не нужны для ссылок и списков — не держим их в памяти
_HEAVY_COLUMNS = ("content", "introtext", "properties")


def load_modx_site(path: str, *, keep_content_for: Optional[Callable[[dict], bool]] = None) -> ModxSite:
    """Загрузить ресурсы, TV и теги из дампа.

    keep_content_for(resource) — для каких ресурсов сохранять тяжёлые колонки и значения TV
    (по умолчанию для всех).
    """
    site = ModxSite()
    keep = keep_content_for or (lambda _r: True)
    tables = (
        "modx_site_content", "modx_site_tmplvars", "modx_site_tmplvar_contentvalues",
        "modx_tagger_tags", "modx_tagger_tag_resources",
    )
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for table, row in iter_table_rows(f, tables):
            if table == "modx_site_content":
                if not keep(row):
                    for column in _HEAVY_COLUMNS:
                        row.pop(column, None)
                site.resources[row["id"]] = row
                if row.get("uri"):
                    site.by_uri[str(row["uri"]).strip("/")] = row["id"]
            elif table == "modx_site_tmplvars":
                site.tv_names[row["id"]] = row["name"]
            elif table == "modx_site_tmplvar_contentvalues":
                resource = site.resources.get(row["contentid"])
                if resource is None or not keep(resource):
                    continue
                name = site.tv_names.get(row["tmplvarid"], str(row["tmplvarid"]))
                site.tv_values.setdefault(row["contentid"], {})[name] = row["value"]
            elif table == "modx_tagger_tags":
                site.tags[row["id"]] = row["tag"]
            elif table == "modx_tagger_tag_resources":
                site.tag_resources.setdefault(row["resource"], []).append(row["tag"])
    return site
