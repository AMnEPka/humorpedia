"""Legacy MODX article/news conversion without database access."""
import asyncio
import json
from unittest.mock import AsyncMock

from models.content import ArticleCreate, ArticleUpdate, NewsCreate
from routes.redirects import _try_pattern_redirect
from services.modx_articles_news import (
    build_content, content_resources, content_url_builder, person_slugs_in_modules,
)
from services.modx_content import LinkMapper
from services.modx_dump import ModxSite
from services.linking import LinkingService


def content_site():
    site = ModxSite()
    site.resources = {
        14: {"id": 14, "uri": "novosti/"},
        29: {"id": 29, "uri": "articles/"},
        116: {"id": 116, "template": 20, "alias": "anton-shastun", "uri": "people/anton-shastun.html"},
        100: {
            "id": 100, "parent": 14, "template": 7, "pagetitle": "Короткая новость",
            "longtitle": "Полный заголовок новости", "alias": "short-news", "uri": "novosti/short-news.html",
            "published": 1, "deleted": 0, "createdon": 1716367575, "publishedon": 1716367560,
            "editedon": 1716459683, "description": "", "keywords": "КВН, юмор", "popular": 1,
            "rating": 0, "votes": 0, "createdby": 23, "content": "",
        },
        200: {
            "id": 200, "parent": 29, "template": 13, "pagetitle": "Статья",
            "longtitle": "Статья — полный заголовок", "alias": "article", "uri": "articles/article.html",
            "published": 0, "deleted": 0, "createdon": 1716633411, "publishedon": 0,
            "editedon": 1719327157, "description": "Описание статьи", "keywords": "интервью",
            "popular": 1, "rating": 8.75, "votes": 4, "createdby": 33, "content": "",
        },
    }
    site.by_uri = {resource["uri"].strip("/"): resource_id for resource_id, resource in site.resources.items()
                   if resource.get("uri")}
    site.tv_values[100] = {
        "config": json.dumps([
            {"MIGX_formname": "news_header"},
            {"MIGX_formname": "text", "title": "", "content":
             '<p>Новость об <a href="people/anton-shastun.html">Антоне</a>.</p>'},
            {"MIGX_formname": "ad_250"},
        ]),
        "tags": "5||6",
    }
    site.tv_values[200] = {
        "config": json.dumps([
            {"MIGX_formname": "text", "title": "Введение", "content": "<p>Текст&nbsp;статьи.</p>"},
            {"MIGX_formname": "table", "content": "<table><tr><td>A</td><td>B</td></tr></table>"},
            {"MIGX_formname": "quote", "title": "Автор", "content": "<p>Цитата</p>"},
            {"MIGX_formname": "text", "title": "Скрыто", "content": "<p>Нет</p>", "hide_section": "1"},
        ]),
        "preview": "images/articles/preview.jpg", "img": "images/articles/header.jpg",
        "img_alt": "Обложка", "tags": "6",
    }
    site.tags = {5: "Антон Шастун", 6: "КВН"}
    site.tag_resources = {100: [6, 5], 200: [6]}
    return site


def test_build_news_matches_admin_format_and_rewrites_links():
    site = content_site()
    mapper = LinkMapper(site, _try_pattern_redirect, url_builders=[
        content_url_builder(site, "article"), content_url_builder(site, "news")
    ])
    payload, extra, warnings = build_content(site, 100, "news", mapper)

    NewsCreate(**payload)
    assert payload["title"] == "Короткая новость" and payload["slug"] == "short-news"
    assert payload["important"] is True and payload["status"] == "published"
    assert payload["seo"]["meta_title"] == "Полный заголовок новости"
    assert payload["excerpt"].startswith("Новость об Антоне")
    assert payload["modules"][0]["data"]["content"] == \
        '<p>Новость об <a href="/people/anton-shastun">Антоне</a>.</p>'
    assert payload["content"] == payload["modules"][0]["data"]["content"]
    assert person_slugs_in_modules(payload["modules"]) == ["anton-shastun"]
    assert extra["old_id"] == 100 and extra["old_urls"] == ["/novosti/short-news.html"]
    assert extra["published_at"].startswith("2024-05-22") and warnings == []


def test_build_article_preserves_modules_cover_author_and_draft():
    site = content_site()
    payload, extra, warnings = build_content(site, 200, "article", author_names={33: "Marine"})

    ArticleCreate(**payload)
    ArticleUpdate(**payload)
    assert payload["title"] == "Статья" and payload["status"] == "draft"
    assert payload["author_name"] == "Marine" and payload["featured"] is True
    assert payload["cover_image"]["url"] == "/media/imported/images/articles/preview.jpg"
    assert [module["type"] for module in payload["modules"]] == ["image", "text_block", "text_block", "quote"]
    assert payload["modules"][0]["data"]["url"] == "/media/imported/images/articles/header.jpg"
    assert payload["modules"][1]["data"]["content"] == "<p>Текст статьи.</p>"
    assert payload["modules"][3]["data"] == {"text": "Цитата", "author": "Автор", "source": None}
    assert extra["rating"] == 8.75 and extra["votes_count"] == 4
    assert "published_at" not in extra and warnings == []


def test_build_article_ignores_non_image_preview_and_uses_header_as_cover():
    site = content_site()
    site.tv_values[200]["preview"] = "однажды в россии новый формат 2026"

    payload, _extra, warnings = build_content(site, 200, "article")

    assert payload["cover_image"]["url"] == "/media/imported/images/articles/header.jpg"
    assert [module["type"] for module in payload["modules"]] == ["text_block", "text_block", "quote"]
    assert warnings == [
        "поле preview не похоже на путь к изображению: однажды в россии новый формат 2026"
    ]


def test_build_article_replaces_phpthumb_cache_with_archived_source():
    site = content_site()
    site.tv_values[200]["preview"] = ""
    site.tv_values[200]["img"] = (
        "https://humorpedia.ru/assets/components/phpthumbof/cache/"
        "000003.e2aeb0a67a81d3ad204fc179c1ae15e3.webp"
    )

    payload, _extra, warnings = build_content(site, 200, "article")

    assert payload["cover_image"]["url"] == "/media/imported/images/article/000003.jpg"
    assert warnings == []


def test_resource_selection_url_builders_and_news_redirect():
    site = content_site()
    assert [resource["id"] for resource in content_resources(site, "article")] == []
    assert [resource["id"] for resource in content_resources(site, "article", include_unpublished=True)] == [200]
    assert content_url_builder(site, "article")(site.resources[200]) == "/articles/article"
    assert content_url_builder(site, "news")(site.resources[100]) == "/news/short-news"
    assert _try_pattern_redirect("/novosti/short-news.html") == "/news/short-news"


def test_linking_service_does_not_boolean_test_motor_collection(monkeypatch):
    class Collection:
        def __bool__(self):
            raise TypeError("Motor collections have no truth value")

        async def update_one(self, query, update):
            self.updated = (query, update)

        def find(self, query, projection):
            self.find_args = (query, projection)
            return self

        def sort(self, *args):
            return self

        def limit(self, *args):
            return self

        async def to_list(self, *args):
            return []

    async def scenario():
        articles = Collection()
        fake_db = type("DB", (), {"articles": articles, "news": Collection(), "shows": Collection()})()
        monkeypatch.setattr("services.linking.get_db", AsyncMock(return_value=fake_db))
        ensure = AsyncMock()
        monkeypatch.setattr(LinkingService, "ensure_chronicles_module", ensure)

        await LinkingService.update_person_links("article", "article-id", ["person-id"])

        assert articles.updated == (
            {"_id": "article-id"}, {"$set": {"related_person_ids": ["person-id"]}}
        )
        ensure.assert_awaited_once_with("person-id")
        assert await LinkingService.get_linked_content("person-id", ["article"]) == {"article": []}

    asyncio.run(scenario())
