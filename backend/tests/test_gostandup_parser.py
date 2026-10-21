from datetime import datetime, timezone

import pytest

from services.source_adapters.gostandup import discover_news, parse_document


BIO_URL = "https://gostandup.ru/comedians/kostya_pushkin"
NEWS_URL = "https://gostandup.ru/articles/bogdan_lisevskiy_put_otkvn_dostendapkomedii"

BIO_HTML = """<!doctype html><html><head><link rel="canonical" href="https://gostandup.ru/comedians/kostya_pushkin">
<title>Костя Пушкин: о стендап-комике</title></head><body>
<header><span>Город: Москва</span><div class="comic-page-header__desktop"><h1 class="comic-page-header__title">Костя Пушкин</h1>
<div class="comic-page-birthdate__info-date">Дата рождения 04.07.1983</div><div class="comic-page-birthdate__info-place">Ухта</div></div></header>
<main><div class="comic-page-header__description page-content"><p>Лучшую репрезентацию Кости дал его брат в <a href="/articles/predelnik">шоу «Предельник»</a>:</p>
<p>Константин Викторович Пушкин — непревзойденный мастер слова.</p><div class="photo"><img src="photo.jpg">Фото подпись</div>
<div class="tabs-with-content"><p>Список видео с городами и мероприятиями</p></div></div></main></body></html>"""

NEWS_HTML = """<!doctype html><html><head><link rel="canonical" href="https://gostandup.ru/articles/bogdan_lisevskiy_put_otkvn_dostendapkomedii">
<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2024-02-08T10:00:00+03:00","dateModified":"2024-02-09T11:00:00+03:00"}</script>
</head><body><h1 class="article-page__title container-small">Богдан Лисевский — путь от КВН до стендап-комедии</h1>
<div class="article-page__date container-small">8 февраля 2024</div><main><div class="article-page__content container-small">
<p>Как развивалась карьера стендап-комика.</p><p>Подписывайтесь на наш телеграм-канал — там удобнее следить за новостями.</p>
<p>Многие знают <a href="/comedians/bogdan_lisevskiy">Лисевского</a> по интервью и выступлениям в КВН.</p>
<h2>КВН</h2><p>В 2012 году появилась команда «Плюшки».</p><div class="video"><iframe src="https://youtube.com/embed/123"></iframe>Видео исключить</div>
<p>Выбирайте свой город, переходите по ссылке — и покупайте билеты в два клика:</p><ul><li>17 февраля, Коломна</li></ul>
<div class="recommended-articles"><p>Смотрите также</p></div><div class="ad-banner"><p>Реклама</p></div></div></main></body></html>"""


def test_live_shape_comedian_profile_extracts_only_explicit_biography_fields():
    result = parse_document(BIO_HTML, BIO_URL)
    assert result["kind"] == "biography"
    assert result["title"] == "Костя Пушкин"
    assert result["full_name"] == "Костя Пушкин"
    assert result["bio"] == {"birth_date": "1983-07-04", "birth_place": "Ухта"}
    assert "Константин Викторович Пушкин" in result["body_html"]
    assert "Москва" not in result["bio"].get("birth_place", "")
    assert "Фото" not in result["body_html"]
    assert "Список видео" not in result["body_html"]
    assert result["canonical_url"] == BIO_URL


def test_live_shape_journal_article_strips_media_tours_ads_and_recommendations():
    result = parse_document(NEWS_HTML, NEWS_URL)
    assert result["kind"] == "news"
    assert result["title"].startswith("Богдан Лисевский")
    assert result["published_at"] == "2024-02-08T10:00:00+03:00"
    assert result["modified_at"] == "2024-02-09T11:00:00+03:00"
    assert "2012" in result["body_html"]
    assert "Подписывайтесь" not in result["body_html"]
    for excluded in ("Видео исключить", "Маршрут стендап-тура", "Купить билеты", "Фото", "Смотрите также", "Реклама"):
        assert excluded not in result["body_html"]
    assert result["mentioned_names"] == ["Лисевского"]


def test_profile_does_not_infer_birth_place_from_site_city_or_unrelated_copy():
    html = BIO_HTML.replace('<div class="comic-page-birthdate__info-place">Ухта</div>', '')
    result = parse_document(html, BIO_URL)
    assert result["bio"] == {"birth_date": "1983-07-04"}


def test_parser_rejects_unlisted_paths_hosts_and_foreign_canonical():
    with pytest.raises(ValueError, match="type"):
        parse_document(NEWS_HTML, "https://gostandup.ru/articles")
    with pytest.raises(ValueError, match="type"):
        parse_document(NEWS_HTML, "https://gostandup.ru/api/private")
    foreign = NEWS_HTML.replace("https://gostandup.ru/articles/bogdan_lisevskiy_put_otkvn_dostendapkomedii", "https://evil.example/articles/a")
    with pytest.raises(ValueError, match="canonical"):
        parse_document(foreign, NEWS_URL)


def test_parser_fails_closed_if_confirmed_body_container_is_missing():
    with pytest.raises(ValueError, match="main text"):
        parse_document(NEWS_HTML.replace("article-page__content", "unknown-content"), NEWS_URL)


def test_discover_news_reads_recent_article_urls_from_sitemap_only():
    xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://gostandup.ru/articles/new_story</loc><lastmod>2026-10-20T12:00:00+03:00</lastmod></url>
      <url><loc>https://gostandup.ru/comedians/new_comic</loc><lastmod>2026-10-20T13:00:00+03:00</lastmod></url>
      <url><loc>https://gostandup.ru/articles/old_story</loc><lastmod>2026-10-19</lastmod></url>
      <url><loc>https://evil.example/articles/foreign</loc><lastmod>2026-10-20</lastmod></url>
    </urlset>"""
    assert discover_news(xml, datetime(2026, 10, 20, tzinfo=timezone.utc)) == ["https://gostandup.ru/articles/new_story"]
    assert discover_news(xml, datetime(2026, 10, 20, tzinfo=timezone.utc), limit=0) == []
    with pytest.raises(ValueError, match="index"):
        discover_news("not XML", datetime.now(timezone.utc))


def test_discover_news_parses_allowed_html_journal_index_without_calling_apis():
    html = """<html><body><main><h1>Стендап-журнал</h1>
    <article><a href="/articles/new_story">Новая статья</a><time datetime="2026-10-20T12:00:00+03:00">Сегодня</time></article>
    <article><a href="/articles/old_story">Старая статья</a><time datetime="2026-10-18">Ранее</time></article>
    <a href="/api/articles?page=2">Показать еще</a>
    </main></body></html>"""
    assert discover_news(html, datetime(2026, 10, 20, tzinfo=timezone.utc)) == ["https://gostandup.ru/articles/new_story"]
