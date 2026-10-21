from datetime import datetime, timezone

import pytest

from services.source_adapters.smi24 import discover_news, parse_document


BIO_HTML = """<!doctype html><html><head>
<title>Михаил Галустян — биография, новости 2026 - 24СМИ</title>
<link rel="canonical" href="https://24smi.org/celebrity/434-mikhail-galustian.html">
<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"05/27/2015 23:32:52","dateModified":"10/19/2026 12:15:23"}</script>
</head><body><div class="head"><h1 class="head__title">Михаил Галустян</h1>
<div class="head__description">Ншан Галустян</div></div>
<div class="cardtable__field"><div class="cardtable__left">Дата рождения</div>
<div class="cardtable__right"><span class="cardtable__date">25 октября 1979 г.</span></div></div>
<div class="cardtable__field"><div class="cardtable__left">Место рождения</div>
<div class="cardtable__right"><a href="https://24smi.org/celebrity/place/sochi-sssr/">Сочи, СССР</a></div></div>
<article class="article" data-type="celebrity" data-cleaned-content="0">
<p>Михаил Галустян — юморист.</p><h2>Карьера</h2><p>Играл в <a href="https://24smi.org/celebrity/88238-kvn.html">КВН</a>.</p>
<figure><img src="https://24smi.org/photo.jpg"><figcaption>Фото: архив</figcaption></figure>
<div class="popular-news"><h2>Похожие новости</h2><p>Не включать.</p></div>
<div class="comments"><p>Комментарии не включать.</p></div>
</article></body></html>"""


NEWS_HTML = """<!doctype html><html><head>
<title>Новости о Галустяне — октябрь 2026 - 24СМИ</title>
<link rel="canonical" href="https://24smi.org/news/483789-mikhail-galustian-vylozhil-vsiu-pravdu-o-molodoi-z.html">
<script type="application/ld+json">{"@type":"NewsArticle","headline":"Михаил Галустян рассказал о семье","datePublished":"2026-10-20T13:06:37+03:00","dateModified":"2026-10-20T13:06:37+03:00"}</script>
</head><body><article class="article" data-type="news" data-cleaned-content="1" data-author="Влад Рига">
<h1>Михаил Галустян рассказал о семье</h1><p>Текст новости.</p><h2>Подробности</h2>
<p>Галустян рассказал о планах. <a href="https://24smi.org/celebrity/434-mikhail-galustian.html">Михаил Галустян</a> дал интервью. <a href="javascript:alert(1)">опасная ссылка</a> <a href="//evil.example">внешний обход</a><script>alert(2)</script></p>
<div id="adfox_1"><p>Реклама не включать</p></div>
<figure><img src="https://24smi.org/pic.jpg"><figcaption>Фото: пресс-служба</figcaption></figure>
<div class="popular-news"><h2>Читайте также</h2><a href="https://24smi.org/news/1.html">Сторонняя новость</a></div>
<div class="article-footer"><p>Поделиться</p></div></article>
<div class="comments"><p>Комментарии не включать</p></div></body></html>"""


def test_parse_biography_uses_structured_fields_and_excludes_media_and_recommendations():
    result = parse_document(
        BIO_HTML,
        "https://24smi.org/celebrity/434-mikhail-galustian.html",
    )

    assert result["kind"] == "biography"
    assert result["title"] == "Михаил Галустян"
    assert result["full_name"] == "Ншан Галустян"
    assert result["bio"] == {
        "birth_date": "1979-10-25",
        "birth_place": "Сочи, СССР",
    }
    assert result["published_at"] == "2015-05-27T23:32:52"
    assert result["modified_at"] == "2026-10-19T12:15:23"
    assert "2026" not in result["title"]
    assert "<p>Михаил Галустян — юморист.</p>" in result["body_html"]
    assert "Фото" not in result["body_html"]
    assert "Не включать" not in result["body_html"]
    assert "Комментарии" not in result["body_html"]
    assert result["mentioned_names"] == ["КВН"]


def test_parse_news_uses_jsonld_dates_and_only_clean_article_body():
    result = parse_document(
        NEWS_HTML,
        "https://24smi.org/news/483789-mikhail-galustian-vylozhil-vsiu-pravdu-o-molodoi-z.html",
    )

    assert result["kind"] == "news"
    assert result["title"] == "Михаил Галустян рассказал о семье"
    assert result["published_at"] == "2026-10-20T13:06:37+03:00"
    assert result["modified_at"] == "2026-10-20T13:06:37+03:00"
    assert "Текст новости." in result["body_html"]
    assert "Читайте также" not in result["body_html"]
    assert "Реклама" not in result["body_html"]
    assert "пресс-служба" not in result["body_html"]
    assert "javascript:" not in result["body_html"]
    assert "alert(2)" not in result["body_html"]
    assert "опасная ссылка" in result["body_html"]
    assert 'href="//evil.example"' not in result["body_html"]
    assert result["mentioned_names"] == ["Михаил Галустян"]


def test_parser_rejects_unrecognized_type_empty_body_and_foreign_canonical():
    with pytest.raises(ValueError, match="type"):
        parse_document('<html><body><h1>Заголовок</h1></body></html>', "https://24smi.org/news/a.html")

    empty = NEWS_HTML.replace("<p>Текст новости.</p>", "").replace(
        '<h2>Подробности</h2>\n<p>Галустян рассказал о планах. '
        '<a href="https://24smi.org/celebrity/434-mikhail-galustian.html">Михаил Галустян</a> дал интервью. '
        '<a href="javascript:alert(1)">опасная ссылка</a> <a href="//evil.example">внешний обход</a>'
        '<script>alert(2)</script></p>',
        "",
    )
    with pytest.raises(ValueError, match="text"):
        parse_document(
            empty,
            "https://24smi.org/news/483789-mikhail-galustian-vylozhil-vsiu-pravdu-o-molodoi-z.html",
        )

    foreign = NEWS_HTML.replace(
        'href="https://24smi.org/news/483789-mikhail-galustian-vylozhil-vsiu-pravdu-o-molodoi-z.html"',
        'href="https://example.com/news.html"',
    )
    with pytest.raises(ValueError, match="canonical"):
        parse_document(foreign, "https://24smi.org/news/483789-mikhail-galustian-vylozhil-vsiu-pravdu-o-molodoi-z.html")


def test_discover_news_filters_since_type_and_limit():
    xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://24smi.org/news/new.html</loc><lastmod>2026-10-20T12:00:00+03:00</lastmod></url>
    <url><loc>https://24smi.org/article/feature.html</loc><lastmod>2026-10-20T13:00:00+03:00</lastmod></url>
    <url><loc>https://24smi.org/news/old.html</loc><lastmod>2026-10-19T10:00:00+03:00</lastmod></url>
    <url><loc>https://example.com/news/foreign.html</loc><lastmod>2026-10-20T14:00:00+03:00</lastmod></url>
    </urlset>"""

    result = discover_news(xml, datetime(2026, 10, 19, 12, tzinfo=timezone.utc), limit=1)

    assert result == ["https://24smi.org/news/new.html"]
