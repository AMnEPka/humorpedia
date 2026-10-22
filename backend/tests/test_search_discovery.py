import asyncio
from dataclasses import replace
import xml.etree.ElementTree as ET
import pytest
from services.public_html_config import load_public_html_settings
from services.search_discovery import render_robots, render_sitemap, SitemapError
from services.page_metadata import canonical_document_url

class Cursor:
    def __init__(self, docs): self.docs=docs
    def sort(self,*args): return self
    def batch_size(self,n): assert n==500; return self
    def __aiter__(self):
        async def items():
            for doc in self.docs: yield doc
        return items()
class Collection:
    def __init__(self,docs): self.docs=docs
    def find(self, query, projection):
        assert query=={"status":"published"}
        assert projection=={"_id":1,"slug":1,"status":1}
        return Cursor([d for d in self.docs if d.get("status")=="published"])

def cfg(indexing=True):
    return load_public_html_settings({"PUBLIC_HTML_ENABLED":"true","SEARCH_INDEXING_ENABLED":str(indexing).lower(),
        "PUBLIC_HTML_BUILD_DIR":"/build","PUBLIC_HTML_DEFAULT_IMAGE_URL":"/share.png"})

def urls(data):
    return [n.text for n in ET.fromstring(data).findall("{*}url/{*}loc")]

def test_sitemap_only_published_valid_canonical():
    db={"people":Collection([{"slug":"А & Ё","status":"published"},{"slug":"альфа&ёж","status":"published"},
        {"slug":"draft","status":"draft"},{"slug":"private","status":"private"},{"slug":"missing"},
        {"slug":"a/b","status":"published"},{"slug":"quote\"","status":"published"},{"slug":"альфа&ёж","status":"published"}]),
        "articles":Collection([{"slug":"a","status":"published"}])}
    result=asyncio.run(render_sitemap(db,settings=cfg()))
    assert urls(result)==["https://humorpedia.ru/people/%D0%B0%D0%BB%D1%8C%D1%84%D0%B0%26%D1%91%D0%B6",
        "https://humorpedia.ru/people/quote%22","https://humorpedia.ru/articles/a"]
    assert b"lastmod" not in result
    assert canonical_document_url("people",{"slug":"x"},site_origin="https://humorpedia.ru")=="https://humorpedia.ru/people/x"

def test_status_slug_changes_are_live_without_views():
    docs=[{"slug":"first","status":"published"}]
    db={"people":Collection(docs),"articles":Collection([])}
    assert "/first" in urls(asyncio.run(render_sitemap(db,settings=cfg())))[0]
    docs[0]["slug"]="second"
    assert "/second" in urls(asyncio.run(render_sitemap(db,settings=cfg())))[0]
    docs[0]["status"]="draft"
    assert urls(asyncio.run(render_sitemap(db,settings=cfg())))==[]

def test_closed_crawl_does_not_list_urls():
    assert urls(asyncio.run(render_sitemap({},settings=cfg(False))))==[]
    assert render_robots(cfg(False))=="User-agent: *\nDisallow: /\n"
    assert "Sitemap: https://humorpedia.ru/sitemap.xml" in render_robots(cfg())

def test_failure_or_over_limit_is_not_partial_xml(monkeypatch):
    from services import search_discovery as discovery
    with pytest.raises(SitemapError): asyncio.run(render_sitemap({},settings=cfg()))
    db={"people":Collection([{"slug":"a","status":"published"},{"slug":"b","status":"published"}]),"articles":Collection([])}
    monkeypatch.setattr(discovery,"MAX_URLS",1)
    with pytest.raises(SitemapError): asyncio.run(render_sitemap(db,settings=cfg()))
    monkeypatch.setattr(discovery,"MAX_URLS",50000)
    monkeypatch.setattr(discovery,"MAX_BYTES",10)
    with pytest.raises(SitemapError): asyncio.run(render_sitemap(db,settings=cfg()))
