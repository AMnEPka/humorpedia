from datetime import datetime, timezone

import pytest

from services.source_adapters.vokrugtv import discover_news, parse_document


BIO_URL = "https://www.vokrug.tv/person/show/viktor_komarov/"
NEWS_URL = "https://www.vokrug.tv/article/show/16116404521/"


BIO_HTML = """<!doctype html><html><head>
<link rel="canonical" href="https://www.vokrug.tv/person/show/viktor_komarov/">
<script type="application/ld+json">{"@type":"ProfilePage","mainEntity":{"@type":"Person","name":"Комаров Виктор","birthDate":"1985-10-16+03:00","birthPlace":{"@type":"Place","name":"Москва, СССР (Россия)"}}}</script>
</head><body><div class="product-detail"><div class="title"><h1>Виктор Комаров</h1></div><div class="info">Реклама</div></div>
<div class="product-detail-content" id="biography"><p>Российский юморист и резидент Stand Up.</p>
<h3>Виктор Комаров Биография</h3><p><strong>Виктор Комаров</strong> выступал в КВН.</p>
<p><img src="/photo.jpg"></p><p style="text-align:center"><em>Виктор Комаров</em></p>
<div class="recommended"><p>Не включать рекомендацию</p></div></div>
<script>не включать</script></body></html>"""


NEWS_HTML = """<!doctype html><html><head>
<link rel="canonical" href="https://www.vokrug.tv/article/show/16116404521/">
<script type="application/ld+json">{"@type":"Article","headline":"Друг Александра Шаляпина заявил о его планах","datePublished":"2021-01-26T09:06:00+03:00","dateModified":"2021-01-26T18:47:11+03:00"}</script>
</head><body><div class="title"><h1>Друг Александра Шаляпина заявил о его планах</h1><h2>Комик хотел привлечь внимание.</h2></div>
<div class="post-detail-content curart"><p>Друг <a href="/person/show/aleksandr_shalyapin/">Александра Шаляпина</a> рассказал подробности.</p>
<p><img src="https://cdn.vokrug.tv/photo.jpg"></p><p style="text-align:center"><em>Александр Шаляпин</em></p>
<p>Цитата и <a href="https://www.vokrug.tv/person/show/garik_kharlamov/">Гарик Харламов</a>.</p>
<p><a href="javascript:alert(1)">опасная ссылка</a> <script>alert(2)</script></p>
<p><strong>Читайте также:</strong></p><p><a href="/article/show/123/">Чужая публикация</a></p></div>
<div class="comments"><p>Комментарии</p></div></body></html>"""


def test_parse_biography_uses_person_jsonld_and_clean_biography_body():
    result = parse_document(BIO_HTML, BIO_URL)

    assert result["kind"] == "biography"
    assert result["title"] == "Виктор Комаров"
    assert result["full_name"] == "Комаров Виктор"
    assert result["bio"] == {
        "birth_date": "1985-10-16",
        "birth_place": "Москва, СССР (Россия)",
    }
    assert result["published_at"] is None
    assert result["modified_at"] is None
    assert "выступал в КВН" in result["body_html"]
    assert "photo.jpg" not in result["body_html"]
    assert "Виктор Комаров</em>" not in result["body_html"]
    assert "рекомендацию" not in result["body_html"]


def test_parse_news_uses_article_jsonld_excludes_media_related_and_xss():
    result = parse_document(NEWS_HTML, NEWS_URL)

    assert result["kind"] == "news"
    assert result["title"] == "Друг Александра Шаляпина заявил о его планах"
    assert result["published_at"] == "2021-01-26T09:06:00+03:00"
    assert result["modified_at"] == "2021-01-26T18:47:11+03:00"
    assert "подробности" in result["body_html"]
    assert "Цитата" in result["body_html"]
    assert "photo.jpg" not in result["body_html"]
    assert "Александр Шаляпин</em>" not in result["body_html"]
    assert "Читайте также" not in result["body_html"]
    assert "Комментарии" not in result["body_html"]
    assert "javascript:" not in result["body_html"]
    assert "alert(2)" not in result["body_html"]
    assert result["mentioned_names"] == ["Александра Шаляпина", "Гарик Харламов"]


def test_discover_news_reads_dated_latest_page_links_and_filters_since_and_limit():
    html = """<div class="article__box-item">
      <a class="article__items" href="/article/show/100/"><div class="article__items-date">07:48, 21.10.2026</div></a>
      <a class="article__items" href="/article/show/99/"><div class="article__items-date">23:48, 19.10.2026</div></a>
      <a class="article__items" href="/article/show/98/"><div class="article__items-date">без даты</div></a>
      <a href="https://evil.example/article/show/97/"><div class="article__items-date">07:48, 21.10.2026</div></a>
    </div>"""

    assert discover_news(html, datetime(2026, 10, 20, tzinfo=timezone.utc), limit=1) == [
        "https://www.vokrug.tv/article/show/100/"
    ]


@pytest.mark.parametrize(
    "url",
    [
        "https://vokrug.tv/person/show/viktor_komarov/",
        "https://www.vokrug.tv/person/show/viktor_komarov/?page=2",
        "https://www.vokrug.tv/article/show/16116404521/#comments",
        "https://www.vokrug.tv.evil.example/article/show/16116404521/",
    ],
)
def test_parser_rejects_unsupported_or_noncanonical_requested_urls(url):
    with pytest.raises(ValueError):
        parse_document(BIO_HTML, url)


def test_parser_rejects_unknown_type_empty_text_and_suspicious_canonical():
    with pytest.raises(ValueError, match="type"):
        parse_document("<html><body><h1>Unknown</h1></body></html>", NEWS_URL)
    empty = NEWS_HTML.replace(
        '<div class="post-detail-content curart"><p>Друг <a href="/person/show/aleksandr_shalyapin/">Александра Шаляпина</a> рассказал подробности.</p>',
        '<div class="post-detail-content curart">',
    )
    empty = empty.replace('<p>Цитата и <a href="https://www.vokrug.tv/person/show/garik_kharlamov/">Гарик Харламов</a>.</p>', "")
    empty = empty.replace('<p><a href="javascript:alert(1)">опасная ссылка</a> <script>alert(2)</script></p>', "")
    with pytest.raises(ValueError, match="text"):
        parse_document(empty, NEWS_URL)
    with pytest.raises(ValueError, match="canonical"):
        parse_document(NEWS_HTML.replace(NEWS_URL, "https://example.com/"), NEWS_URL)


def test_parser_rejects_news_without_explicit_publication_date():
    undated = NEWS_HTML.replace(',"datePublished":"2021-01-26T09:06:00+03:00","dateModified":"2021-01-26T18:47:11+03:00"', "")
    with pytest.raises(ValueError, match="publication date"):
        parse_document(undated, NEWS_URL)
