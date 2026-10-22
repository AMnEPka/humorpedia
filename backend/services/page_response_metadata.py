"""Optional response metadata; no DB work and no production app configuration."""
from dataclasses import asdict
from typing import Literal
from starlette.requests import Request
from services.page_metadata import build_page_metadata

def attach_page_metadata(kind: Literal["people", "articles"], document: dict,
                         request: Request | None, *, enabled: bool) -> dict:
    config = getattr(getattr(request, "app", None).state, "html_page_metadata", None) if request is not None else None
    if not enabled or config is None:
        return document
    try:
        metadata = asdict(build_page_metadata(kind, document, **config))
    except (ValueError, TypeError, AttributeError, KeyError):
        metadata = None
    return {**document, "page_metadata": metadata}
