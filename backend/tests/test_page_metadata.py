from dataclasses import FrozenInstanceError
import pytest

def build(document=None, kind="people", **overrides):
    from services.page_metadata import build_page_metadata
    options = dict(site_origin="https://humorpedia.ru", indexing_enabled=True,
                   default_image_url="/media/pilot-share.png")
    options.update(overrides)
    return build_page_metadata(kind, document or {"title": "Альфа", "slug": "alpha", "status": "published"}, **options)

def test_title_origin_and_robots_contract():
    meta = build({"title": "Альфа", "slug": "alpha", "status": "published",
                  "seo": {"meta_title": "  Мета  ", "meta_description": 'Текст "Ёж" & <b>факт</b>'}})
    assert meta.title == "Мета | humorpedia.ru"
    assert meta.description == 'Текст "Ёж" & <b>факт</b>'
    assert meta.canonical_url == "https://humorpedia.ru/people/alpha"
    assert (meta.robots, meta.lang, meta.locale, meta.og_type) == ("index,follow", "ru", "ru_RU", "website")
    assert meta.image_url == "https://humorpedia.ru/media/pilot-share.png"
    with pytest.raises(FrozenInstanceError):
        meta.title = "changed"

@pytest.mark.parametrize("status", ["draft", None, "", "published", "archived"])
@pytest.mark.parametrize("enabled", [True, False])
def test_index_requires_explicit_published_and_flag(status, enabled):
    assert build({"title": "А", "slug": "a", "status": status}, indexing_enabled=enabled).robots == (
        "index,follow" if enabled and status == "published" else "noindex,follow")

def test_description_fallback_and_suffix():
    meta = build({"title": "Альфа | humorpedia.ru", "slug": "альфа", "excerpt": "<p>Текст <b>факт</b></p><script>secret</script>"}, kind="articles")
    assert meta.title == "Альфа | humorpedia.ru"
    assert meta.description == "Текст факт"
    assert meta.canonical_url == "https://humorpedia.ru/articles/%D0%B0%D0%BB%D1%8C%D1%84%D0%B0"
    assert meta.og_type == "article"
    assert "Альфа" in build().description

@pytest.mark.parametrize("slug", ["", "../a", "a/b", "//evil", "a?x=1", "a#x", "a\\b", "a\nb"])
def test_invalid_slug_is_rejected(slug):
    with pytest.raises(ValueError):
        build({"title": "А", "slug": slug})

@pytest.mark.parametrize("origin", ["http://humorpedia.ru", "https://evil/a", "https://u:p@humorpedia.ru", "https://humorpedia.ru?x=1", "//humorpedia.ru"])
def test_origin_must_be_a_trusted_https_origin(origin):
    with pytest.raises(ValueError):
        build(site_origin=origin)

@pytest.mark.parametrize("bad", ["https://[", "javascript:alert(1)", "//evil/image.png", "data:image/png;base64,a", "http://127.0.0.1/x", "http://localhost/x", "/../secret", "/x\\y", "https://user:pass@cdn.example/x"])
def test_unsafe_image_uses_safe_fallback(bad):
    assert build({"title": "А", "slug": "a", "seo": {"og_image": bad}}).image_url == "https://humorpedia.ru/media/pilot-share.png"

def test_image_precedence_and_alt():
    meta = build({"title": "А", "slug": "a", "seo": {"og_image": "/seo.png"}, "photo": {"url": "/photo.png"}})
    assert meta.image_url == "https://humorpedia.ru/seo.png"
    assert meta.image_alt == "А"
    assert build({"title": "А", "slug": "a", "photo": "/person.png"}).image_url.endswith("/person.png")
    article = build({"title": "А", "slug": "a", "modules": [{"type": "image", "visible": False, "data": {"url": "/hidden.png"}}, {"type": "image", "data": {"url": "/module.png"}}], "cover_image": {"url": "/cover.png"}}, kind="articles")
    assert article.image_url.endswith("/module.png")
def test_relative_and_invalid_port_images():
    assert build({"title": "А", "slug": "a", "photo": "media/photo.png"}).image_url == "https://humorpedia.ru/media/photo.png"
    assert build({"title": "А", "slug": "a", "photo": "https://cdn.example:bad/x"}).image_url == "https://humorpedia.ru/media/pilot-share.png"
