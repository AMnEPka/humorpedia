"""Isolated HTML experiment. Production server/Compose never import this factory."""
from contextlib import asynccontextmanager
import os
import re
from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from routes.html_pilot import create_router, error_response
from utils.database import get_db, close_db

def create_app():
    run_id = os.environ.get("HTML_PILOT_RUN_ID", "")
    name = os.environ.get("DB_NAME", "")
    if (os.environ.get("HTML_PILOT_ENABLED") != "1" or not re.fullmatch(r"[0-9a-f]{32}", run_id)
            or name != "humorpedia_html_pilot_" + run_id or not os.environ.get("MONGO_URL", "").strip()):
        raise ValueError("HTML pilot requires explicit enablement and its own UUID database/MONGO_URL")

    @asynccontextmanager
    async def lifespan(app):
        try:
            db = await get_db()
            if db.name != name:
                raise RuntimeError("HTML pilot client database mismatch")
            await db.command("ping")
            yield
        finally:
            await close_db()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, error):
        return error_response(error.status_code)

    app.include_router(create_router(run_id=run_id, db_name=name,
                                    indexing_enabled=os.environ.get("HTML_PILOT_INDEXING_ENABLED") == "1"))
    return app
