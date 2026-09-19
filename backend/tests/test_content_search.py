import asyncio

from routes.content_search import (
    _find_ranked_matches,
    _partial_search_query,
    _relevance_key,
)


class FakeCursor:
    def __init__(self, items):
        self.items = items
        self.limit_value = None

    def limit(self, value):
        self.limit_value = value
        return self

    async def to_list(self, value):
        return self.items[:value]


class FakeCollection:
    def __init__(self, items):
        self.items = items
        self.query = None
        self.projection = None

    def find(self, query, projection):
        self.query = query
        self.projection = projection
        return FakeCursor(self.items)


def test_partial_search_escapes_user_input_and_excludes_archived_content():
    query = _partial_search_query("Гу.", ["full_name", "title"])

    assert query["$and"][0] == {"status": {"$ne": "archived"}}
    assert query["$and"][1]["$or"] == [
        {"full_name": {"$regex": "Гу\\.", "$options": "i"}},
        {"title": {"$regex": "Гу\\.", "$options": "i"}},
    ]


def test_relevance_prefers_exact_then_title_and_word_prefixes():
    items = [
        {"_id": "substring", "full_name": "Сергуня"},
        {"_id": "word", "full_name": "Александр Гудков"},
        {"_id": "prefix", "full_name": "Гудков Александр"},
        {"_id": "exact", "full_name": "Гу"},
    ]

    ranked = sorted(items, key=lambda item: _relevance_key(item, ["full_name"], "Гу"))

    assert [item["_id"] for item in ranked] == ["exact", "prefix", "word", "substring"]


def test_equal_prefixes_are_ordered_by_primary_field_then_alphabetically():
    items = [
        {"_id": "short", "full_name": "Оля Гульчак", "title": "Гульчак Оля"},
        {"_id": "wanted", "full_name": "Александр Гудков", "title": "Гудков Александр"},
        {"_id": "primary", "full_name": "Гурам Амарян", "title": "Амарян Гурам"},
    ]

    ranked = sorted(
        items,
        key=lambda item: _relevance_key(item, ["full_name", "title"], "Гу"),
    )

    assert [item["_id"] for item in ranked] == ["primary", "wanted", "short"]


def test_ranked_search_uses_partial_query_and_returns_best_matches_first():
    collection = FakeCollection([
        {"_id": "word", "full_name": "Александр Гудков"},
        {"_id": "prefix", "full_name": "Гудков Александр"},
    ])

    result = asyncio.run(_find_ranked_matches(
        collection, ["full_name", "title"], "Гу", 5, {"modules": 0}
    ))

    assert [item["_id"] for item in result] == ["prefix", "word"]
    assert collection.query["$and"][1]["$or"][0] == {
        "full_name": {"$regex": "Гу", "$options": "i"}
    }
