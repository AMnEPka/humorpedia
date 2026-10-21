from datetime import datetime, timezone

import pytest

from services.source_adapters.zhaba import current_page_url, discover_news, next_page_url, parse_document, parse_feed


FEED_HTML = """<!doctype html><html><head>
<link rel="canonical" href="https://t.me/s/zhabqua?before=21964">
<link rel="prev" href="/s/zhabqua?before=21940">
</head><body>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="zhabqua/21963" data-view="old-count">
<div class="tgme_widget_message_text" dir="auto">Может #жаб_дайджест посмотрите?<br>Щербакова, Винокур, Ахмедова: <a href="https://t.me/other/1">ссылка</a> 😄<script>alert(1)</script><a href="javascript:alert(2)">опасно</a></div>
<a class="tgme_widget_message_date" href="https://t.me/zhabqua/21963"><time datetime="2026-10-20T20:13:59+00:00">20:13</time></a>
<span class="tgme_widget_message_views">999</span><div class="tgme_widget_message_reactions">❤️ 17</div>
<div class="tgme_widget_message_video_player"><video src="https://cdn.t.me/video.mp4"></video></div>
</div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="zhabqua/21961" data-view="media-only">
<div class="tgme_widget_message_photo_wrap"><img src="https://cdn.t.me/photo.jpg"></div>
<a class="tgme_widget_message_date" href="https://t.me/zhabqua/21961"><time datetime="2026-10-20T15:40:22+00:00">15:40</time></a>
</div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="zhabqua/21950" data-view="group">
<div class="tgme_widget_message_grouped_wrap"><img src="https://cdn.t.me/1.jpg"><img src="https://cdn.t.me/2.jpg"></div>
<div class="tgme_widget_message_text" dir="auto">Первая строка заголовка<br>Продолжение текста.</div>
<a class="tgme_widget_message_date" href="https://t.me/zhabqua/21950"><time datetime="2026-10-19T20:51:07+00:00">20:51</time></a>
</div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="otherchannel/777">
<div class="tgme_widget_message_text">Не брать другой канал</div><time datetime="2026-10-20T00:00:00+00:00">00:00</time></div></div>
</body></html>"""


def test_parse_feed_extracts_text_posts_and_keeps_media_only_record():
    records = parse_feed(FEED_HTML)

    assert [record["post_id"] for record in records] == [21963, 21961, 21950]
    text_post = records[0]
    assert text_post["kind"] == "news"
    assert text_post["title"].startswith("Может #жаб_дайджест посмотрите?")
    assert text_post["published_at"] == "2026-10-20T20:13:59+00:00"
    assert text_post["modified_at"] is None
    assert "❤️" not in text_post["body_html"]
    assert "999" not in text_post["body_html"]
    assert "video.mp4" not in text_post["body_html"]
    assert "alert(1)" not in text_post["body_html"]
    assert "javascript:" not in text_post["body_html"]
    assert "опасно" in text_post["body_html"]
    assert text_post["mentioned_names"] == []
    assert text_post["canonical_url"] == "https://t.me/zhabqua/21963"

    media_post = records[1]
    assert media_post["post_id"] == 21961
    assert media_post["body_html"] == ""
    assert media_post["title"] == ""
    assert media_post["published_at"] == "2026-10-20T15:40:22+00:00"


def test_parse_feed_deduplicates_album_post_id_independent_of_view_counts():
    html = FEED_HTML.replace("data-view=\"group\"", "data-view=\"new-count\"")
    html += FEED_HTML[FEED_HTML.index('<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="zhabqua/21950"'):]
    records = parse_feed(html)
    album_posts = [record for record in records if record["post_id"] == 21950]

    assert len(album_posts) == 1
    assert "Первая строка заголовка" in album_posts[0]["body_html"]
    assert "cdn.t.me" not in album_posts[0]["body_html"]
    assert album_posts[0]["published_at"] == "2026-10-19T20:51:07+00:00"


def test_parse_document_returns_exact_post_and_rejects_wrong_or_empty_id():
    result = parse_document(FEED_HTML, "https://t.me/zhabqua/21950")
    assert result["post_id"] == 21950
    assert result["title"] == "Первая строка заголовка"

    with pytest.raises(ValueError, match="не найден"):
        parse_document(FEED_HTML, "https://t.me/zhabqua/99999")
    with pytest.raises(ValueError, match="текстового"):
        parse_document(FEED_HTML, "https://t.me/zhabqua/21961")


def test_parser_rejects_other_channels_and_unsafe_or_noncanonical_urls():
    for url in (
        "https://t.me/otherchannel/21963",
        "https://t.me/zhabqua/21963?single",
        "https://t.me.evil.example/zhabqua/21963",
        "http://t.me/zhabqua/21963",
    ):
        with pytest.raises(ValueError):
            parse_document(FEED_HTML, url)


def test_discover_news_filters_by_date_and_skips_media_only_posts():
    urls = discover_news(FEED_HTML, datetime(2026, 10, 20, tzinfo=timezone.utc), limit=10)
    assert urls == ["https://t.me/zhabqua/21963"]
    no_offset = FEED_HTML.replace("2026-10-20T20:13:59+00:00", "2026-10-20T20:13:59")
    assert parse_feed(no_offset)[0]["published_at"] is None


def test_pagination_uses_only_canonical_and_prev_links_advertised_by_feed():
    assert current_page_url(FEED_HTML) == "https://t.me/s/zhabqua?before=21964"
    assert next_page_url(FEED_HTML) == "https://t.me/s/zhabqua?before=21940"
    malicious = FEED_HTML.replace('href="/s/zhabqua?before=21940"', 'href="https://evil.example/s/zhabqua?before=21940"')
    assert next_page_url(malicious) is None
