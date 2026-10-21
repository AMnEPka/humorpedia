"""Run ONLY against the isolated VPS backend; never print credentials or tokens."""
import asyncio
import io
import json
import os
from pathlib import Path
import uuid

import httpx
from PIL import Image
from utils.database import get_db, close_db


async def main():
    marker = "vps-smoke-" + uuid.uuid4().hex
    db = await get_db()
    before = {n: await db[n].count_documents({}) for n in ("wiki", "media")}
    wiki_id = media_id = None
    results = {}
    base_url = os.environ.get("SMOKE_BASE_URL", "http://frontend")
    origin = os.environ.get("SMOKE_ORIGIN", "http://localhost:8080")
    host = httpx.URL(origin).netloc.decode()
    async with httpx.AsyncClient(base_url=base_url, headers={"Host": host}, timeout=40) as client:
        async def request(method, path, status=200, **kwargs):
            response = await client.request(method, path, **kwargs)
            assert response.status_code == status, f"{method} {path}: {response.status_code}"
            return response
        try:
            assert (await request("GET", "/api/health")).json()["status"] == "healthy"
            assert "<html" in (await request("GET", "/")).text.lower()
            assert "window.location.origin" in (await request("GET", "/config.js")).text
            await request("GET", "/api/auth/me", status=401)
            denied = await client.post("/api/content/wiki", json={"title": marker, "slug": marker})
            assert denied.status_code in (401, 403)
            await request("POST", "/api/auth/login", status=401, json={"email": os.environ["ADMIN_EMAIL"], "password": "not-the-password"})
            login = (await request("POST", "/api/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})).json()
            assert login["user"]["role"] == "admin"
            auth = {"Authorization": "Bearer " + login["access_token"]}
            assert (await request("GET", "/api/auth/me", headers=auth)).json()["role"] == "admin"
            results["authentication_and_write_guard"] = True
            cors = await request("OPTIONS", "/api/auth/login", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
            assert cors.headers["access-control-allow-origin"] == origin
            results["cors"] = True
            for collection in ("people", "teams", "shows", "articles", "news", "quizzes"):
                data = (await request("GET", f"/api/content/{collection}?limit=1")).json()
                assert data["items"], collection
                results[collection] = True
                if collection == "people":
                    person = data["items"][0]
                    await request("GET", "/api/content/people/" + person["slug"])
                    results["person_page"] = True
            image = await request("GET", "/media/imported/images/pattern/1.jpg")
            assert image.headers["content-type"].startswith("image/") and len(image.content) > 100
            results["imported_media"] = True
            created = (await request("POST", "/api/content/wiki", json={"title": marker, "slug": marker, "modules": [], "status": "draft"}, headers=auth)).json()
            wiki_id = created.get("id") or created.get("_id")
            assert wiki_id
            await request("PUT", "/api/content/wiki/" + wiki_id, json={"title": marker + " updated"}, headers=auth)
            assert (await request("GET", "/api/content/wiki/" + marker)).json()["title"] == marker + " updated"
            await request("DELETE", "/api/content/wiki/" + wiki_id, headers=auth)
            results["content_crud"] = True
            payload = io.BytesIO()
            Image.new("RGB", (3, 3), "blue").save(payload, "PNG")
            media = (await request("POST", "/api/media/upload", files={"file": (marker + ".png", payload.getvalue(), "image/png")}, headers=auth)).json()
            media_id = media["id"]
            assert (await request("GET", media["url"])).content == payload.getvalue()
            await request("DELETE", "/api/media/" + media_id, headers=auth)
            results["upload_read_delete"] = True
        finally:
            # Remove only our unique test objects, including the upload API's soft-delete.
            if wiki_id:
                await db.wiki.delete_one({"_id": wiki_id, "slug": marker})
            if media_id:
                doc = await db.media.find_one({"_id": media_id, "original_name": marker + ".png"})
                assert doc, "Test media cleanup must match our original filename"
                path = Path(doc["path"]).resolve()
                assert path.is_relative_to(Path("/app/uploads")) and path.name == doc["filename"]
                path.unlink(missing_ok=True)
                await db.media.delete_one({"_id": media_id, "original_name": marker + ".png"})
            after = {n: await db[n].count_documents({}) for n in before}
            assert after == before, "Test data cleanup count mismatch"
            await close_db()
    results["test_data_cleaned"] = True
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
