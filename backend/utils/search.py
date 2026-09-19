"""Shared normalization helpers for user-entered search text."""
import re


def normalize_search_text(value: object) -> str:
    """Normalize case, whitespace and Russian е/ё for comparison and ranking."""
    return " ".join(str(value or "").casefold().replace("ё", "е").split())


def literal_search_pattern(value: object) -> str:
    """Build a literal MongoDB regex where Russian е and ё are equivalent."""
    parts = []
    for character in str(value or ""):
        if character.casefold() in {"е", "ё"}:
            parts.append("[её]")
        else:
            parts.append(re.escape(character))
    return "".join(parts)
