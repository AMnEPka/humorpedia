"""Pure metadata contract shared by the isolated HTML pilot."""
from dataclasses import dataclass
from urllib.parse import quote, urljoin, urlsplit
from services.html_text import plain_text, safe_url

@dataclass(frozen=True)
class PageMetadata:
    title: str
    description: str
    canonical_url: str
    og_type: str
    image_url: str
    image_alt: str
    robots: str
    lang: str = "ru"
    locale: str = "ru_RU"

def _value(value):
    return " ".join(value.split()) if isinstance(value, str) else ""

def validate_origin(origin):
    try:
        p = urlsplit(origin)
        if p.scheme != "https" or not p.hostname or p.username or p.password or p.path not in {"", "/"} or p.query or p.fragment or p.port not in {None, 443}:
            raise ValueError("Expected HTTPS site origin")
        return "https://" + p.hostname.lower()
    except (ValueError, TypeError) as error:
        raise ValueError("Expected HTTPS site origin") from error

def _media(value):
    return value.get("url") or value.get("thumbnail") if isinstance(value, dict) else value

def build_page_metadata(kind, document, *, site_origin, indexing_enabled, default_image_url):
    origin = validate_origin(site_origin)
    if kind not in {"people", "articles"}:
        raise ValueError("Unsupported pilot content type")
    slug = document.get("slug")
    if not isinstance(slug, str) or not slug or slug in {".", ".."} or any(c.isspace() or c in "/\\?#" or ord(c) < 32 for c in slug):
        raise ValueError("Missing or invalid canonical slug")
    seo = document.get("seo") if isinstance(document.get("seo"), dict) else {}
    heading = _value(document.get("title")) or "Humorpedia"
    title = _value(seo.get("meta_title")) or heading
    if not title.lower().endswith("| humorpedia.ru"):
        title += " | humorpedia.ru"
    label = "Человек" if kind == "people" else "Статья"
    description = _value(seo.get("meta_description")) or plain_text(document.get("excerpt")) or f"{label}: {heading}."
    candidates = [seo.get("og_image")]
    if kind == "people":
        candidates += [document.get(k) for k in ("photo", "cover_image", "image", "poster")]
    else:
        modules = sorted((m for m in (document.get("modules") or []) if m.get("visible") is not False), key=lambda m: m.get("order") or 0)
        if modules and modules[0].get("type") == "image":
            candidates.append((modules[0].get("data") or {}).get("url"))
        candidates += [document.get("cover_image"), document.get("image")]
    candidates.append(default_image_url)
    def image_url(value):
        raw = _media(value)
        try:
            relative = isinstance(raw, str) and raw and not urlsplit(raw).scheme and not raw.startswith(("/", "#"))
        except ValueError:
            return None
        if relative:
            raw = "/" + raw
        return safe_url(raw, fragment=False)
    image = next((url for v in candidates if (url := image_url(v)) and not url.startswith("#")), None)
    if image is None:
        raise ValueError("Public default image required")
    return PageMetadata(
        title=title, description=description, canonical_url=f"{origin}/{kind}/{quote(slug, safe='')}",
        og_type="website" if kind == "people" else "article", image_url=urljoin(origin + "/", image),
        image_alt=plain_text(heading), robots="index,follow" if indexing_enabled and document.get("status") == "published" else "noindex,follow")
