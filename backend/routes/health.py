"""Отдельный публичный readiness; liveness /api/health сохраняет прежний контракт."""
import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from services.page_package_import import storage
from services.readiness import check_readiness
from utils.database import get_db

router = APIRouter(tags=["health"])


@router.get("/ready")
async def ready(request: Request):
    try:
        db = await get_db()
        result = await check_readiness(
            db,
            indexes_initialized=getattr(request.app.state, "indexes_initialized", False),
            required_indexes=getattr(request.app.state, "required_indexes", []),
            package_dir=storage(),
            public_dirs=[os.environ.get("UPLOAD_DIR", "/app/uploads"), "/app/media",
                         "/app/images", "/app/frontend/public/media"],
        )
    except Exception:
        result = {"status": "not_ready",
                  "checks": {"mongodb": "error", "indexes": "error", "package_storage": "error"}}
    if hasattr(request.app.state, "public_html_settings"):
        html_ready = request.app.state.public_html_release is not None
        result["checks"]["public_html"] = "ok" if html_ready else "error"
        if not html_ready:
            result["status"] = "not_ready"
    return JSONResponse(result, status_code=200 if result["status"] == "ready" else 503,
                        headers={"Cache-Control": "no-store"})
