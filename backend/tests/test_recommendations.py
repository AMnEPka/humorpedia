import asyncio

from services.recommendations import rank_articles, recommendations_for


def test_rank_articles_is_deterministic_and_prefers_direct_relation_then_tags():
    source = {"_id": "person-1", "content_type": "person", "tags": ["КВН"]}
    candidates = [
        {"_id": "c", "tags": ["КВН"], "views": 50},
        {"_id": "b", "tags": [], "related_person_ids": ["person-1"]},
        {"_id": "a", "tags": ["КВН"], "views": 50},
    ]
    assert [item["_id"] for item in rank_articles(source, candidates)] == ["b", "a", "c"]


class _Cursor:
    def __init__(self, items):
        self.items = items

    async def to_list(self, _limit):
        return list(self.items)


class _Collection:
    def __init__(self, docs):
        self.docs = docs

    async def find_one(self, query):
        for doc in self.docs:
            if any(doc.get(key) == value for clause in query.get("$or", []) for key, value in clause.items()):
                return dict(doc)
        return None

    def find(self, query, _projection=None):
        items = []
        for doc in self.docs:
            if query.get("status") and doc.get("status") != query["status"]:
                continue
            ids = query.get("_id", {})
            if "$in" in ids and doc.get("_id") not in ids["$in"]:
                continue
            if "$nin" in ids and doc.get("_id") in ids["$nin"]:
                continue
            items.append(dict(doc))
        return _Cursor(items)


class _Db:
    def __init__(self, articles):
        self.articles = _Collection(articles)

    def __getitem__(self, key):
        return getattr(self, key)


def test_manual_recommendations_keep_order_and_filter_invalid_targets():
    docs = [
        {"_id": "current", "slug": "current", "title": "Текущая", "status": "published", "tags": ["КВН"],
         "related_article_ids": ["b", "current", "draft", "missing", "b"]},
        {"_id": "b", "slug": "b", "title": "Ручная", "status": "published", "tags": []},
        {"_id": "draft", "slug": "draft", "title": "Черновик", "status": "draft", "tags": ["КВН"]},
        {"_id": "d", "slug": "d", "title": "Автоматическая", "status": "published", "tags": ["КВН"]},
    ]
    result = asyncio.run(recommendations_for(_Db(docs), "article", "current", 3))
    assert [(item["id"], item["manual"]) for item in result["items"]] == [("b", True), ("d", False)]
