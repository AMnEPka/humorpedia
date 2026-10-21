"""Настоящее приложение и production frontend на одноразовой БД для browser smoke."""
from contextlib import asynccontextmanager
import os
import base64
from pathlib import Path
import re
import sys
import tempfile

run_id = os.environ.get("SMOKE_RUN_ID", "")
if not re.fullmatch(r"[0-9a-f]{32}", run_id):
    raise RuntimeError("Нужен уникальный SMOKE_RUN_ID: UUID без дефисов")
database_name = "humorpedia_browser_test_" + run_id
if os.environ.get("DB_NAME") != database_name:
    raise RuntimeError("Smoke разрешён только на собственной humorpedia_browser_test_<run_id> БД")
build = Path(os.environ["BROWSER_BUILD_DIR"]).resolve()
if not (build / "index.html").is_file():
    raise RuntimeError("Сначала соберите frontend и задайте BROWSER_BUILD_DIR")

# Рабочие uploads и private-каталоги приложения не используются.
state = tempfile.TemporaryDirectory(prefix="humorpedia-browser-" + run_id + "-")
for key, folder in (("UPLOAD_DIR", "uploads"), ("PAGE_PACKAGE_DIR", "packages"),
                    ("PAGE_BUILDER_DIR", "builder"), ("BACKUP_DIR", "backups")):
    os.environ[key] = str(Path(state.name) / folder)
os.environ["ENVIRONMENT"] = "development"
os.environ["LOCAL_PAGE_BUILDER_ENABLED"] = "true"
os.environ["JWT_SECRET"] = "browser-smoke-only-" + run_id
os.environ["ADMIN_EMAIL"] = "browser@example.invalid"
os.environ["ADMIN_PASSWORD"] = "Browser-smoke-only-2026"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from server import app  # noqa: E402
from starlette.exceptions import HTTPException  # noqa: E402
from starlette.responses import FileResponse, Response  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402

original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def isolated_lifespan(application):
    owned = False
    try:
        db = await get_db()
        if db.name != database_name or await db.list_collection_names():
            raise RuntimeError("Smoke требует новую пустую БД; существующая не изменена")
        await db.browser_smoke_runs.insert_one({"_id": run_id})
        owned = True
        async with original_lifespan(application):
            yield
    finally:
        # После остановки фоновых writers: они не должны воссоздать удалённую БД.
        try:
            if owned:
                db = await get_db()
                if db.name != database_name or not await db.browser_smoke_runs.find_one({"_id": run_id}):
                    raise RuntimeError("Не подтверждено владение smoke-БД; удаление запрещено")
                await db.client.drop_database(database_name)
        finally:
            try:
                await close_db()
            finally:
                state.cleanup()


app.router.lifespan_context = isolated_lifespan


@app.get("/__browser_smoke__/status")
async def smoke_status():
    return {"run_id": run_id, "database": database_name}


@app.get("/__browser_smoke__/image.png")
async def smoke_image():
    # Same-origin deterministic gallery image; never writes into production media.
    return Response(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ZkAAAAASUVORK5CYII="
    ), media_type="image/png")


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            accepts_html = b"text/html" in dict(scope["headers"]).get(b"accept", b"")
            if error.status_code != 404 or not accepts_html or path.startswith(("api/", "uploads/", "media/", "images/")):
                raise
            return FileResponse(build / "index.html")


app.mount("/", FrontendFiles(directory=build, html=True), name="browser-smoke-frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("SMOKE_BIND", "127.0.0.1"), port=int(os.environ.get("SMOKE_PORT", "18001")))
