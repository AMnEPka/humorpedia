"""Synthetic wrapper around the REAL app and its sole native lifespan."""
from contextlib import asynccontextmanager
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from copy import deepcopy

run_id = os.environ.get("HTML_GATEWAY_RUN_ID", "")
database_name = "humorpedia_html_gateway_" + run_id
if not re.fullmatch("[0-9a-f]{32}", run_id) or os.environ.get("DB_NAME") != database_name:
    raise RuntimeError("Only an owned gateway UUID database is allowed")
state = tempfile.TemporaryDirectory(prefix="humorpedia-gateway-" + run_id + "-")
for key, folder in (("UPLOAD_DIR","uploads"),("PAGE_PACKAGE_DIR","packages"),("PAGE_BUILDER_DIR","builder"),("BACKUP_DIR","backups")):
    directory = Path(state.name) / folder
    directory.mkdir()
    os.environ[key] = str(directory)
os.environ.update(ENVIRONMENT="development", LOCAL_PAGE_BUILDER_ENABLED="true",
                  JWT_SECRET="gateway-only-"+run_id, ADMIN_EMAIL="gateway@example.invalid",
                  ADMIN_PASSWORD="Gateway-only-2026")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, "/app")  # Release source; harness mounts fixtures only.
from pymongo import monitoring
from server import app
from utils.database import get_db, close_db
from services.views_counter import views_counter
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from pilot_server import PNG, _Commands
from react_pilot_fixtures import seed_react_records
from gateway_ownership import assert_owner as verify_owner, create_owner, drop_owned_database

commands = _Commands(database_name)
monitoring.register(commands)
original = app.router.lifespan_context
release = getattr(app.state, "public_html_release", None)

async def assert_owner(db):
    await verify_owner(db, run_id)

@asynccontextmanager
async def owned(application):
    seeded = False
    try:
        db = await get_db()
        await create_owner(db, run_id)
        seeded = True
        fixtures=json.loads((ROOT/"backend/tests/fixtures/html_pilot.json").read_text(encoding="utf-8-sig"))
        for kind, records in fixtures.items():
            await db[kind].insert_many(deepcopy(records))
        for kind in ("people","articles"):
            for kib in (10,250):
                slug=f"perf-{kind}-{kib}k"
                text="Тест " * (kib * 1024 // len("Тест ".encode()))
                await db[kind].insert_one({"_id":slug,"slug":slug,"title":f"Fixture {kind} {kib} KiB",
                    "status":"published","modules":[{"type":"text_block","data":{"content":f"<p>{text}</p>"}}]})
        await seed_react_records(db)
        await db.people.update_one({"_id":"person-alpha"},{"$push":{"old_urls":{"$each":["/old&name","/old/alpha"]}}})
        await db.people.update_one({"slug":"private"},{"$set":{"old_urls":["/old/private"]}})
        await db.seasons.insert_one({"_id":"gateway-season","title":"CAS","slug":"gateway-season","updated_at":"v1","stages":[]})
        async with original(application):
            yield
    finally:
        try:
            if seeded:
                db=await get_db()
                # Original lifespan has already stopped scheduler, views and client.
                await drop_owned_database(db, run_id)
        finally:
            await close_db()
            state.cleanup()
app.router.lifespan_context = owned

async def image(request):
    return Response(PNG,media_type="image/png",headers={"Cache-Control":"no-store"})

async def measure(request):
    db=await get_db()
    await assert_owner(db)
    rss=next((int(line.split()[1]) for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("VmRSS:")),None)
    return JSONResponse({"run_id":run_id,"database":database_name,"commands":dict(commands.counts),"rss_kib":rss},
                        headers={"Cache-Control":"no-store"})

async def control(request):
    payload=await request.json()
    if payload.get("run_id")!=run_id:
        return JSONResponse({"detail":"Wrong owner"},status_code=403)
    db=await get_db()
    await assert_owner(db)
    action=payload.get("action")
    if action in {"archive","restore","rename"}:
        await db.people.update_one({"_id":"person-alpha"},{"$set":{
            "status":"archived" if action=="archive" else "published", "slug":"alpha-renamed" if action=="rename" else "alpha"}})
    elif action=="mismatch":
        app.state.public_html_release=replace(release,release_id="0"*64)
    elif action=="match":
        app.state.public_html_release=release
    elif action!="flush":
        return JSONResponse({"detail":"Unknown action"},status_code=400)
    await views_counter.flush()
    views={kind:{doc["_id"]:doc.get("views",0) for doc in await db[kind].find({},{"views":1}).to_list(None)} for kind in ("people","articles")}
    return JSONResponse({"views":views,"run_id":run_id})

for route in (
    Route("/media/pilot-share.png",image,methods=["GET"]),
    Route("/media/imported/images/pattern/{path:path}",image,methods=["GET"]),
    Route("/api/__html_gateway__/measure",measure,methods=["GET"]),
    Route("/api/__html_gateway__/control",control,methods=["POST"]),
):
    app.router.routes.insert(0,route)

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8001)
