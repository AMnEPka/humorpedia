"""Shared normalization helpers for user-entered search text."""
import re


_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
    'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f',
    'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '',
    'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def normalize_search_text(value: object) -> str:
    """Normalize case, whitespace and Russian е/ё for comparison and ranking."""
    return " ".join(str(value or "").casefold().replace("ё", "е").split())


def literal_search_pattern(value: object) -> str:
    """Build a literal MongoDB regex where Russian е and ё are equivalent."""
    parts = []
    for character in str(value or ""):
        if character.casefold() in {"е", "ё"}:
            parts.append("[её]")
        elif character.isspace():
            parts.append(r"[\s-]+")
        else:
            parts.append(re.escape(character))
    return "".join(parts)


def search_variants(value: object) -> list[str]:
    """Small, deterministic set of spelling variants for names and slugs."""
    text = normalize_search_text(value)
    variants = [text]
    if len(text) >= 5 and re.search(r'[а-я]$', text):
        stem = text[:-1]
        if text.endswith(('ы', 'и')):
            variants.extend((stem + 'а', stem + 'я'))
        elif text.endswith(('а', 'я')):
            variants.append(stem)
    if re.search(r'[а-я]', text):
        variants.append(''.join(_LATIN.get(char, char) for char in text))
    return [variant for variant in dict.fromkeys(variants) if len(variant) >= 3]


def edit_distance(left: str, right: str, maximum: int = 2) -> int:
    """Bounded Levenshtein distance; return maximum + 1 for distant strings."""
    if abs(len(left) - len(right)) > maximum:
        return maximum + 1
    previous = list(range(len(right) + 1))
    for row, char in enumerate(left, 1):
        current = [row]
        for col, other in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[col] + 1,
                               previous[col - 1] + (char != other)))
        if min(current) > maximum:
            return maximum + 1
        previous = current
    return previous[-1]
