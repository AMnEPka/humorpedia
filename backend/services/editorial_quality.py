"""Minimum verified content required before an editorial candidate becomes a person page."""

from datetime import date
from html import unescape
import re


MIN_BIO_CHARS = 100


def has_day_and_month(value) -> bool:
    if not isinstance(value, str):
        return False
    value = value.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            date.fromisoformat(value)
            return True
        match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", value)
        if match:
            day, month, year = match.groups()
            date(int(year or 2000), int(month), int(day))
            return True
    except ValueError:
        return False
    return False


def _biography_text(value) -> str:
    if isinstance(value, dict):
        value = value.get("content")
    if not isinstance(value, str):
        return ""
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


def missing_candidate_requirements(full_name, accepted_changes: list[tuple[dict, object]]) -> list[str]:
    """Check source-backed accepted facts, never infer missing biography data."""
    fields = {change["field"]: value for change, value in accepted_changes}
    missing = []
    if not isinstance(full_name, str) or len(full_name.split()) < 2:
        missing.append("полное публичное имя (имя и фамилия)")
    if not has_day_and_month(fields.get("bio.birth_date")):
        missing.append("дата рождения (ДД.ММ или ДД.ММ.ГГГГ)")
    birthplace = fields.get("bio.birth_place")
    if not isinstance(birthplace, str) or len(birthplace.strip()) < 2:
        missing.append("город рождения")

    biography = ""
    for change, value in accepted_changes:
        if not re.fullmatch(r"module\.[^.$]+\.content", change["field"]):
            continue
        title = (value.get("title") if isinstance(value, dict) else None) or change.get("label") or ""
        if "биограф" in str(title).casefold():
            biography = _biography_text(value)
            break
    if len(biography) < MIN_BIO_CHARS or len(re.findall(r"[.!?](?:\s|$)", biography)) < 2:
        missing.append("биография: минимум два предложения и 100 символов")

    shows = {change["field"].split(".", 1)[1] for change, value in accepted_changes
             if change["field"].startswith("appearance.") and isinstance(value, dict)}
    if len(shows) < 2:
        missing.append("участие минимум в двух разных проектах/шоу")
    return missing
