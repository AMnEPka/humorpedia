import pytest
from pathlib import Path
from services.public_html_config import load_public_html_settings

def test_defaults_preserve_legacy_mode():
    cfg = load_public_html_settings({})
    assert not cfg.enabled and not cfg.indexing_enabled
    assert cfg.site_origin == "https://humorpedia.ru"
    assert cfg.build_dir is None and cfg.default_image_url is None

def test_rejects_index_without_html():
    with pytest.raises(ValueError):
        load_public_html_settings({"SEARCH_INDEXING_ENABLED": "true"})

@pytest.mark.parametrize("name", ["PUBLIC_HTML_ENABLED", "SEARCH_INDEXING_ENABLED"])
@pytest.mark.parametrize("value", ["", "True", "1", "yes", " true"])
def test_rejects_non_boolean_flags(name, value):
    with pytest.raises(ValueError):
        load_public_html_settings({name: value})

def test_enabled_requires_explicit_build_and_image():
    for env in ({}, {"PUBLIC_HTML_BUILD_DIR": "/build"}, {"PUBLIC_HTML_DEFAULT_IMAGE_URL": "/media/share.png"}):
        with pytest.raises(ValueError):
            load_public_html_settings({"PUBLIC_HTML_ENABLED": "true", **env})
    cfg = load_public_html_settings({"PUBLIC_HTML_ENABLED": "true", "PUBLIC_HTML_BUILD_DIR": "/build",
        "PUBLIC_HTML_DEFAULT_IMAGE_URL": "/media/share.png", "SITE_ORIGIN": "https://evil.example"})
    assert cfg.enabled and cfg.build_dir == Path("/build")
    assert cfg.site_origin == "https://humorpedia.ru"
