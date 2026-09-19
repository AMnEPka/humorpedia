import re

from utils.search import literal_search_pattern, normalize_search_text


def test_search_normalization_treats_yo_as_e():
    assert normalize_search_text("  ЗВЁЗДЫ   на НТВ ") == "звезды на нтв"
    assert normalize_search_text("звезды") == normalize_search_text("ЗВЁЗДЫ")


def test_literal_pattern_matches_e_and_yo_and_escapes_special_characters():
    pattern = literal_search_pattern("звезды.")

    assert pattern == "зв[её]зды\\."
    assert re.search(pattern, "Звёзды.", re.IGNORECASE)
    assert re.search(pattern, "звезды.", re.IGNORECASE)
    assert not re.search(pattern, "звёзды!", re.IGNORECASE)
