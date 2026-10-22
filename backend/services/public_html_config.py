"""Explicit optional public HTML settings. Canonical origin is never request-derived."""
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

@dataclass(frozen=True)
class PublicHtmlSettings:
    enabled: bool
    indexing_enabled: bool
    site_origin: str
    build_dir: Path | None
    default_image_url: str | None

def load_public_html_settings(env: Mapping[str, str]) -> PublicHtmlSettings:
    def flag(name):
        value = env.get(name, "false")
        if value not in {"true", "false"}:
            raise ValueError(f"{name} must be true or false")
        return value == "true"
    enabled = flag("PUBLIC_HTML_ENABLED")
    indexing = flag("SEARCH_INDEXING_ENABLED")
    if indexing and not enabled:
        raise ValueError("SEARCH_INDEXING_ENABLED requires PUBLIC_HTML_ENABLED")
    build_dir = env.get("PUBLIC_HTML_BUILD_DIR")
    image = env.get("PUBLIC_HTML_DEFAULT_IMAGE_URL")
    if enabled and (not build_dir or not image):
        raise ValueError("Enabled public HTML requires build directory and default image")
    return PublicHtmlSettings(enabled, indexing, "https://humorpedia.ru",
                              Path(build_dir) if build_dir else None, image or None)
