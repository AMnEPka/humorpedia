"""Export read-only enriched fixture payloads for the existing React build."""
import asyncio
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from html_pilot import create_app
from services.crud import get_by_id_or_slug
from services.foreign_agent_notices import decorate_document
from services.link_resolver import LinkResolver
from services.public_html import load_html_page
from utils.database import close_db

async def export():
    create_app()  # Require owned UUID environment; no production lifecycle.
    output = {}
    try:
        for kind, slug in (("people", "alpha"), ("articles", "story"), ("articles", "legacy"), ("articles", "hidden-only"), ("articles", "legacy-notice")):
            document = deepcopy(await get_by_id_or_slug(kind, slug, "Page not found", increment_views=False, editor=False))
            await LinkResolver.resolve_document(document)
            await decorate_document(document)
            page = await load_html_page(kind, slug, site_origin="https://humorpedia.ru", indexing_enabled=False, default_image_url="/media/pilot-share.png")
            output[f"/{kind}/{slug}"] = {"document": document,
                "heading": page.heading, "blocks": [{"heading": b.heading, "text": b.body_text} for b in page.blocks],
                "links": page.links, "notices": page.notices, "unsupported": page.unsupported_types}
        folder = ROOT / ".cache/r13b/reference"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "payloads.json").write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(export())
