"""Owned fixture server for the HTML/React pilot; never run against primary."""
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from html_react_pilot import create_app
from utils.database import get_db, close_db
from routes.auth import hash_password
from services.views_counter import views_counter
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from pilot_server import seed_fixture_database, cleanup_fixture_database, _check_name, PNG, _Commands
from pymongo import monitoring

def create_fixture_app():
    app = create_app()
    original = app.router.lifespan_context
    run_id = os.environ["HTML_PILOT_RUN_ID"]
    commands = _Commands(os.environ["DB_NAME"])
    if os.environ.get("HTML_REACT_PILOT_MEASURE") == "1":
        monitoring.register(commands)
    state = tempfile.TemporaryDirectory(prefix="html-react-" + run_id + "-")
    os.environ["UPLOAD_DIR"] = str(Path(state.name) / "uploads")

    @asynccontextmanager
    async def owned(application):
        owned_db = False
        try:
            db = await get_db()
            await seed_fixture_database(db, run_id)
            owned_db = True
            fixtures = json.loads((ROOT / "backend/tests/fixtures/html_react_pilot.json").read_text(encoding="utf-8-sig"))
            for kind, records in fixtures.items():
                await db[kind].insert_many(records)
            await db.people.update_one({"_id": "person-alpha"}, {"$push": {"modules": {"type": "poll", "order": 50, "data": {"poll_id": "poll-demo"}}}})
            await db.polls.insert_one({"_id": "poll-demo", "question": "Как вам пилот?", "status": "published",
                "show_results_before_vote": False, "options": [
                    {"id": "yes", "text": "Подходит", "historical_votes": 0},
                    {"id": "no", "text": "Нужно доработать", "historical_votes": 0}]})
            await db.users.insert_one({"_id": "pilot-user", "username": "pilot-user", "email": "pilot@example.invalid",
                                      "password_hash": hash_password("Pilot-only-2026"), "role": "user", "permissions": ["vote"], "profile": {}})
            await db.teams.insert_one({"_id": "team-demo", "name": "Команда пилота", "title": "Команда пилота", "slug": "pilot-team", "status": "published", "show_id": None})
            await db.memberships.insert_one({"_id": "member-demo", "person_id": "person-alpha", "team_id": "team-demo",
                                             "roles": ["Участник"], "year_from": 2020, "year_to": 2021})
            await db.shows.insert_one({"_id": "show-demo", "title": "Шоу пилота", "name": "Шоу пилота", "slug": "show-demo",
                                       "full_path": "show-demo", "status": "published"})
            await db.show_appearances.insert_one({"_id": "appearance-demo", "person_id": "person-alpha", "show_id": "show-demo",
                                                  "source_page_id": "show-demo", "achievement": "participant", "kind": "appearance"})
            async with original(application):
                yield
        finally:
            try:
                if owned_db:
                    await cleanup_fixture_database(await get_db(), run_id)
            finally:
                await close_db()
                state.cleanup()
    app.router.lifespan_context = owned

    async def image(request):
        return Response(PNG, media_type="image/png")
    async def measure(request):
        rss = next((int(line.split()[1]) for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("VmRSS:")), None)
        return JSONResponse({"run_id": run_id, "database": os.environ["DB_NAME"], "commands": dict(commands.counts), "rss_kib": rss})
    async def control(request):
        payload = await request.json()
        if payload.get("run_id") != run_id:
            return JSONResponse({"detail": "Wrong owner"}, status_code=403)
        db = await get_db()
        _check_name(db, run_id)
        if not await db.html_pilot_owner.find_one({"_id": run_id}):
            return JSONResponse({"detail": "Owner missing"}, status_code=409)
        action = payload.get("action")
        if action in {"archive", "restore"}:
            await db.people.update_one({"_id": "person-alpha"}, {"$set": {"status": "archived" if action == "archive" else "published"}})
        elif action != "flush":
            return JSONResponse({"detail": "Unknown action"}, status_code=400)
        await views_counter.flush()
        views = {kind: {doc["_id"]: doc.get("views", 0) for doc in await db[kind].find({}, {"views": 1}).to_list(None)} for kind in ("people", "articles")}
        return JSONResponse({"views": views, "run_id": run_id})
    for route in (
        Route("/media/pilot-share.png", image, methods=["GET"]),
        Route("/media/imported/images/pattern/{path:path}", image, methods=["GET"]),
        Route("/__html_react_pilot__/measure", measure, methods=["GET"]),
        Route("/__html_react_pilot__/control", control, methods=["POST"]),
    ):
        app.router.routes.insert(0, route)
    return app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_fixture_app(), host=os.environ.get("HTML_PILOT_BIND", "127.0.0.1"),
                port=int(os.environ.get("HTML_PILOT_PORT", "18014")))
