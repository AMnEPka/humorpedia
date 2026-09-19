import asyncio
from datetime import datetime

from models.related_news import RelatedNewsSettings
from services.related_news import related_news_for
from services.related_news_migration import clean_document, split_legacy_news_section


class FakeCursor:
    def __init__(self, items):
        self.items = items
        self.sort_args = None
        self.limit_value = None

    def sort(self, *args):
        self.sort_args = args
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    async def to_list(self, value):
        return self.items[:value]


class FakeCollection:
    def __init__(self, one=None, items=None):
        self.one = one
        self.items = items or []
        self.find_query = None

    async def find_one(self, query, projection=None):
        return self.one

    def find(self, query, projection=None):
        self.find_query = query
        return FakeCursor(self.items)


def test_settings_limit_is_capped_at_three():
    assert RelatedNewsSettings(max_items=3).max_items == 3
    try:
        RelatedNewsSettings(max_items=4)
    except ValueError:
        pass
    else:
        raise AssertionError("max_items above three must be rejected")


def test_related_news_uses_explicit_relation_and_freshness_cutoff():
    news = FakeCollection(items=[{
        "_id": "news-1", "title": "Свежая новость", "slug": "fresh",
        "published_at": "2026-09-19T10:00:00+00:00",
    }])
    db = type("DB", (), {
        "site_settings": FakeCollection(one=None),
        "people": FakeCollection(one={"_id": "person-1"}),
        "teams": FakeCollection(),
        "shows": FakeCollection(),
        "news": news,
    })()

    result = asyncio.run(related_news_for(db, "person", "person-1"))

    assert result["enabled"] is True
    assert result["max_items"] == 3
    assert result["items"][0]["id"] == "news-1"
    assert news.find_query["related_person_ids"] == "person-1"
    assert news.find_query["status"] == {"$ne": "archived"}
    assert datetime.fromisoformat(news.find_query["published_at"]["$gte"])


def test_legacy_news_tail_is_removed_without_breaking_wrapping_div():
    content = (
        '<div><p>Основной текст.</p><h3 style="text-align: justify;">Новости</h3>'
        '<p><a href="/novosti/example.html">Старая новость</a></p></div>'
    )

    prefix, links = split_legacy_news_section(content)

    assert prefix == "<div><p>Основной текст.</p></div>"
    assert links == ["/novosti/example.html"]


def test_cleanup_removes_empty_news_module_and_chronicles_only():
    document = {
        "modules": [
            {"id": "intro", "type": "text_block", "data": {"content": "<p>Описание</p>"}},
            {"id": "news", "type": "text_block", "data": {
                "content": '<h4>Новости</h4><p><a href="/news/fresh">Свежая</a></p>'}},
            {"id": "chronicles", "type": "humor_chronicles", "data": {}},
        ]
    }

    updated, links, sections, chronicles = clean_document(document)

    assert [module["id"] for module in updated["modules"]] == ["intro"]
    assert links == ["/news/fresh"]
    assert sections == 1
    assert chronicles == 1


def test_cleanup_does_not_touch_news_word_in_regular_text():
    document = {"modules": [{
        "id": "text", "type": "text_block",
        "data": {"content": "<p>Эта новость стала частью истории команды.</p>"},
    }]}

    updated, links, sections, chronicles = clean_document(document)

    assert updated == document
    assert links == [] and sections == 0 and chronicles == 0
