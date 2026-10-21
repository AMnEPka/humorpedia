from services.source_html import sanitize


def test_sanitize_keeps_formatting_and_safe_links():
    assert sanitize('<h2>Заголовок</h2><p><strong>Текст</strong> и <a href="https://example.org/a?b=1&amp;c=2" onclick="run()">ссылка</a></p>') == (
        '<h2>Заголовок</h2><p><strong>Текст</strong> и '
        '<a href="https://example.org/a?b=1&amp;c=2">ссылка</a></p>')


def test_sanitize_removes_active_content_and_media_but_keeps_text():
    value = '<p>До<img src="https://example.org/x.jpg"><video>кадр</video><script>alert(1)</script>После</p>'
    assert sanitize(value) == '<p>ДокадрПосле</p>'


def test_sanitize_drops_unsafe_and_control_character_links():
    value = '<a href="javascript:alert(1)">js</a><a href="data:text/html,x">data</a><a href="/safe/path">local</a><a href="https://example.org/\nattack">control</a>'
    assert sanitize(value) == '<a>js</a><a>data</a><a href="/safe/path">local</a><a>control</a>'


def test_sanitize_escapes_text_and_unwraps_unknown_tags():
    assert sanitize('<custom title="x">a &amp; <b>"b"</b></custom>') == 'a &amp; <b>"b"</b>'
