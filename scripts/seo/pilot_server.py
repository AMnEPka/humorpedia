"""Owned fixture server for R13b. No production app, paths, data or startup writers."""
from contextlib import asynccontextmanager
from copy import deepcopy
import base64
import json
import os
from pathlib import Path
import re
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from html_pilot import create_app
from utils.database import get_db, close_db
from starlette.responses import Response, JSONResponse
from collections import Counter
from pymongo import monitoring
from starlette.routing import Route

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aBAAAAABJRU5ErkJggg==")

def _check_name(db, run_id):
    if not re.fullmatch(r"[0-9a-f]{32}", run_id) or db.name != "humorpedia_html_pilot_" + run_id:
        raise RuntimeError("Only the owned HTML pilot UUID database is allowed")

async def cleanup_fixture_database(db, run_id):
    _check_name(db, run_id)
    if not await db.html_pilot_owner.find_one({"_id":run_id}):
        raise RuntimeError("HTML pilot ownership marker missing; database was not removed")
    await db.client.drop_database(db.name)

async def seed_fixture_database(db, run_id):
    _check_name(db, run_id)
    if await db.list_collection_names():
        raise RuntimeError("Fixture seed requires a new empty database")
    await db.html_pilot_owner.insert_one({"_id":run_id})
    try:
        fixtures = json.loads((ROOT / "backend/tests/fixtures/html_pilot.json").read_text(encoding="utf-8-sig"))
        for kind, records in fixtures.items():
            await db[kind].insert_many(deepcopy(records))
        for kind in ("people", "articles"):
            for kib in (10, 250):
                slug = f"perf-{kind}-{kib}k"
                text = "Тест " * (kib * 1024 // len("Тест ".encode("utf-8")))
                await db[kind].insert_one({"_id":slug,"slug":slug,"title":f"Fixture {kind} {kib} KiB",
                                          "status":"published","modules":[{"type":"text_block","data":{"content":f"<p>{text}</p>"}}]})
    except Exception:
        await cleanup_fixture_database(db, run_id)
        raise

class _Commands(monitoring.CommandListener):
    def __init__(self, name):
        self.name = name
        self.counts = Counter()
    def started(self, event):
        if event.database_name == self.name:
            self.counts[event.command_name] += 1
    def succeeded(self, event):
        pass
    def failed(self, event):
        pass

def create_fixture_app():
    app = create_app()
    commands = _Commands(os.environ["DB_NAME"]) if os.environ.get("HTML_PILOT_MEASURE") == "1" else None
    if commands:
        monitoring.register(commands)
    original = app.router.lifespan_context
    run_id = os.environ["HTML_PILOT_RUN_ID"]

    startup_ms = None
    @asynccontextmanager
    async def owned_lifespan(application):
        nonlocal startup_ms
        start = perf_counter()
        owned = False
        try:
            db = await get_db()
            await seed_fixture_database(db, run_id)
            owned = True
            async with original(application):
                startup_ms = (perf_counter() - start) * 1000
                yield
        finally:
            try:
                if owned:
                    await cleanup_fixture_database(await get_db(), run_id)
            finally:
                await close_db()
    app.router.lifespan_context = owned_lifespan

    async def image(request):
        return Response(PNG, media_type="image/png", headers={"Cache-Control":"no-store","X-Robots-Tag":"noindex,follow"})
    app.router.routes.insert(0, Route("/media/pilot-share.png", image, methods=["GET"]))
    if commands:
        async def measure(request):
            rss = next((int(line.split()[1]) for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("VmRSS:")), None)
            return JSONResponse({"commands":dict(commands.counts),"rss_kib":rss,"fixture_lifespan_startup_ms":startup_ms}, headers={"Cache-Control":"no-store","X-Robots-Tag":"noindex,follow"})
        app.router.routes.insert(0, Route("/__html_pilot__/measure", measure, methods=["GET"]))
    return app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_fixture_app(), host=os.environ.get("HTML_PILOT_BIND","127.0.0.1"),
                port=int(os.environ.get("HTML_PILOT_PORT","18013")))
