"""
Utilities for matching teams by name.

This is intentionally aligned with migration logic in `migration/kvn/team_matcher.py`
so that admin bulk-import and migration scripts behave consistently.
"""

from __future__ import annotations

import re


def normalize_case(name: str) -> str:
    """
    Normalize accusative -> nominative for the first word in Russian team names.

    Examples:
    - "Сборную Пермского края" -> "Сборная Пермского края"
    - "Команду КВН" -> "Команда КВН"
    """
    if not name:
        return name

    words = name.split()
    if not words:
        return name

    first_word = words[0]

    if first_word.endswith("ую") and len(first_word) > 3:
        words[0] = first_word[:-2] + "ая"
    elif first_word.endswith("юю") and len(first_word) > 3:
        words[0] = first_word[:-2] + "яя"
    elif first_word.endswith("у") and len(first_word) > 2:
        # Rough heuristic: convert trailing "у" to "а" for consonant-ending stems
        if first_word[-2] not in "аеёиоуыэюя":
            words[0] = first_word[:-1] + "а"

    return " ".join(words)


def normalize_team_name(name: str) -> str:
    """
    Normalize team name for comparisons:
    - case normalization (accusative -> nominative heuristic)
    - lower-case
    - whitespace normalization
    - remove common quote characters
    """
    if not name:
        return ""

    name = normalize_case(name)
    normalized = re.sub(r"\s+", " ", name.lower().strip())
    normalized = (
        normalized.replace("«", "")
        .replace("»", "")
        .replace('"', "")
        .replace("'", "")
    )
    return normalized

