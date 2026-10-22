import pytest
from services.page_metadata import build_page_metadata
from services.public_html import HtmlPage,TextBlock

TEMPLATE='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Old</title><meta name="description" content="old"><meta property="og:title" content="old"><link rel="canonical" href="/old"><script src="/config.js"></script><script type="module" src="/assets/main.js"></script><link rel="stylesheet" href="/assets/main.css"></head><body><div id="root"></div><script nomodule src="/assets/legacy.js"></script></body></html>'

def page():
    metadata=build_page_metadata("people",{"title":"Альфа","slug":"alpha","status":"published"},site_origin="https://humorpedia.ru",indexing_enabled=False,default_image_url="/media/pilot-share.png")
    return HtmlPage(metadata,"Альфа",(TextBlock("",'</script><script>danger()</script>',"section-0"),),(),(),"/people/alpha",())

def test_shell_has_one_root_and_preserves_assets():
    from services.html_react_shell import render_react_shell
    html=render_react_shell(page(),TEMPLATE)
    assert html.count('id="root"')==1 and html.count("<title>")==1
    assert html.count('rel="canonical"')==1 and html.count('property="og:title"')==1
    assert '<html lang="ru">' in html
    assert 'id="root" hidden' in html and 'aria-hidden="true"' in html
    assert html.index('id="html-pilot-fallback"')<html.index('id="root"')
    assert 'data-path="/people/alpha"' in html
    for url in ("/config.js","/assets/main.js","/assets/main.css","/assets/legacy.js"):assert url in html
    assert '<script>danger()' not in html and '&lt;/script&gt;' in html
    assert 'name="viewport"' in html and html.count('charset="utf-8"')==1

@pytest.mark.parametrize("template",[TEMPLATE.replace('<div id="root"></div>',''),TEMPLATE.replace('<div id="root"></div>','<div id="root">old</div>'),TEMPLATE.replace('</body>','<div id="root"></div></body>')])
def test_invalid_shell_is_rejected(template):
    from services.html_react_shell import render_react_shell
    with pytest.raises(ValueError):render_react_shell(page(),template)
