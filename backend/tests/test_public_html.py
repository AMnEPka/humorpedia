import asyncio
import copy
from unittest.mock import AsyncMock
from html.parser import HTMLParser
import pytest
from fastapi import HTTPException

OPTIONS = dict(site_origin="https://humorpedia.ru", indexing_enabled=True, default_image_url="/media/pilot-share.png")

def module(kind, **data):
    return {"type": kind, "data": data}

async def load(monkeypatch, document, kind="people"):
    from services import public_html
    read = AsyncMock(return_value=document)
    monkeypatch.setattr(public_html, "get_by_id_or_slug", read)
    monkeypatch.setattr(public_html.LinkResolver, "resolve_document", AsyncMock(side_effect=lambda d: d))
    monkeypatch.setattr(public_html, "decorate_document", AsyncMock(side_effect=lambda d: d))
    page = await public_html.load_html_page(kind, document["slug"], **OPTIONS)
    assert read.call_args.kwargs == {"increment_views": False, "editor": False}
    return page

def test_reader_is_anonymous_and_never_enqueues_views(monkeypatch):
    async def check():
        document = {"slug": "alpha", "title": "Альфа", "status": "draft", "modules": [module("text_block", content="<p>Текст</p>")]}
        before = copy.deepcopy(document)
        page = await load(monkeypatch, document)
        assert document == before
        assert page.metadata.robots == "noindex,follow"
        assert page.blocks[0].body_text == "Текст"
    asyncio.run(check())

def test_module_visibility_order_and_article_fallback(monkeypatch):
    async def check():
        first = module("text_block", title="Начало", content="<p>А</p>")
        first["order"] = 1
        second = module("quote", text="<b>Цитата</b>", author="Автор")
        second["order"] = 1
        hidden = module("text_block", content="SECRET")
        hidden["visible"] = False
        sidebar = module("facts_table", content="SIDE")
        timeline = module("timeline", title="История", events=[{"year": "2020", "title": "Старт", "description": "<p>Событие</p>"}])
        timeline["order"] = 2
        page = await load(monkeypatch, {"slug": "a", "title": "А", "modules": [timeline, first, second, hidden, sidebar]})
        body = " ".join(b.heading + " " + b.body_text for b in page.blocks)
        assert body.index("Начало") < body.index("Цитата") < body.index("История")
        assert "<b>Цитата</b>" in body
        assert "2020" in body and "Событие" in body
        assert "SECRET" not in body and "SIDE" not in body
        for modules, expected in [([], True), ([hidden], False), ([module("image", url="/a.png")], True), ([module("text_block", content="Main")], False)]:
            page = await load(monkeypatch, {"slug": "a", "title": "А", "modules": modules, "content": "<p>Legacy text</p>"}, "articles")
            assert ("Legacy text" in " ".join(b.body_text for b in page.blocks)) is expected
    asyncio.run(check())

def test_semantic_html_head_text_and_escaping(monkeypatch):
    async def check():
        from services.public_html import render_html_page
        document = {"slug": "a", "title": 'А <b>Б</b> "Ё"', "status": "published",
                    "foreign_agent": True, "foreign_agent_notice": True,
                    "foreign_agent_notices": [{"marker": "*", "text": "Пометка"}],
                    "seo": {"meta_description": 'Описание "x"><script>alert(1)</script>'},
                    "modules": [module("text_block", content='<p>Текст &amp; <a href="/people/b">ссылка</a></p><script>SECRET</script><style>STYLE</style><iframe><a href="/bad">BAD</a></iframe><a href="javascript:alert(1)" onclick="bad()">bad link</a>')]}
        page = await load(monkeypatch, document)
        html = render_html_page(page)
        assert html.count("<title>") == 1 and html.count('rel="canonical"') == 1
        for key in ["og:title", "og:description", "og:url", "og:image", "og:image:alt", "og:type", "og:locale"]:
            assert html.count(f'property="{key}"') == 1
        assert '<html lang="ru"' in html and '<h1>А &lt;b&gt;Б&lt;/b&gt; &quot;Ё&quot;*' in html
        assert '<script>' not in html and "onclick=" not in html and 'href="javascript:' not in html
        assert "SECRET" not in html and "STYLE" not in html and "BAD" not in html
        assert '<a href="/people/b">ссылка</a>' in html
        assert '* — признан в РФ иностранным агентом.' in html
        assert '* — Пометка.' not in html
        assert '&lt;script&gt;' in html
    asyncio.run(check())

@pytest.mark.parametrize("status", ["private", "unknown", "archived"])
def test_pilot_rejects_non_public_status_before_enrichment(monkeypatch, status):
    async def check():
        with pytest.raises(HTTPException) as error:
            await load(monkeypatch, {"slug": "private", "title": "SECRET", "status": status})
        assert error.value.status_code == 404
        from services import public_html
        assert public_html.LinkResolver.resolve_document.await_count == 0
        assert public_html.decorate_document.await_count == 0
    asyncio.run(check())
