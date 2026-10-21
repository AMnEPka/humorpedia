"""R5: реальная Mongo, перезапуск приложения и восстановление БД вместе с private media."""
import asyncio
from hashlib import sha256
from io import BytesIO
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import uuid

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from services.page_packages import image_info, pack_page, seed_page
from utils import database
from utils.auth import create_token


@pytest.fixture
def isolated_app(monkeypatch, tmp_path):
    if os.environ.get("READINESS_INTEGRATION") != "1":
        pytest.skip("Нужен READINESS_INTEGRATION=1 с отдельной MongoDB")
    name = "humorpedia_r5_test_" + uuid.uuid4().hex
    monkeypatch.setenv("DB_NAME", name)
    monkeypatch.setenv("ADMIN_EMAIL", "")
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "empty-backups"))
    data = tmp_path / "data"
    for folder in ("uploads", "page-packages"):
        (data / folder).mkdir(parents=True, mode=0o700)
    monkeypatch.setenv("UPLOAD_DIR", str(data / "uploads"))
    monkeypatch.setenv("PAGE_PACKAGE_DIR", str(data / "page-packages"))
    import server

    def client():
        return TestClient(server.app)

    async def cleanup():
        db = await database.get_db()
        assert db.name == name and name.startswith("humorpedia_r5_test_")
        await db.client.drop_database(name)
        await database.close_db()

    try:
        yield client, name, data
    finally:
        asyncio.run(cleanup())


def test_readiness_detects_removed_unique_index_and_missing_storage(isolated_app, monkeypatch, tmp_path):
    client_factory, name, data = isolated_app
    with client_factory() as client:
        response = client.get("/api/ready")
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/api/health").json() == {"status": "healthy"}

        async def change_index(drop):
            db = await database.get_db()
            assert db.name == name and name.startswith("humorpedia_r5_test_")
            if drop:
                await db.users.drop_index("username_1")
            else:
                await db.users.create_index("username", unique=True)
        client.portal.call(change_index, True)
        response = client.get("/api/ready")
        assert response.status_code == 503
        assert response.json()["checks"]["indexes"] == "error"
        assert client.get("/api/health").status_code == 200
        client.portal.call(change_index, False)
        assert client.get("/api/ready").status_code == 200

        monkeypatch.setenv("PAGE_PACKAGE_DIR", str(tmp_path / "missing"))
        response = client.get("/api/ready")
        assert response.status_code == 503
        assert response.json()["checks"]["package_storage"] == "error"
        assert not (tmp_path / "missing").exists()
        monkeypatch.setenv("PAGE_PACKAGE_DIR", str(data / "page-packages"))
        assert client.get("/api/ready").status_code == 200


def _mongo_archive(tool, name, archive):
    assert name.startswith("humorpedia_r5_test_") and len(name.rsplit("_", 1)[1]) == 32
    container = os.environ.get("MONGO_TOOLS_CONTAINER")
    command = ["docker", "exec", "-i", container, tool] if container else [tool]
    assert container or shutil.which(tool), "Нужен mongodump/mongorestore либо MONGO_TOOLS_CONTAINER"
    command += ["--uri", os.environ["MONGO_URL"], "--db", name, "--archive", "--gzip"]
    if tool == "mongodump":
        with archive.open("wb") as output:
            result = subprocess.run(command, stdout=output, stderr=subprocess.PIPE)
    else:
        with archive.open("rb") as source:
            result = subprocess.run(command, stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0, "Не прошла операция с одноразовой MongoDB"
    assert archive.stat().st_size > 0


def test_zip_photo_survives_app_restart_and_database_files_restore(isolated_app, monkeypatch, tmp_path):
    client_factory, name, data = isolated_app
    image = BytesIO()
    Image.new("RGB", (15, 15), color="blue").save(image, "PNG")
    raw = image.getvalue()
    page = seed_page("person", {"name": "Проверка восстановления R5"})
    page["photo"] = {"url": "asset:photo", "alt": "Тестовая фотография"}
    draft = {"id": str(uuid.uuid4()), "kind": "person", "revision": 1, "page": page,
             "materials": {}, "relations": [],
             "assets": [dict(image_info(raw, "photo.png"), id="photo")]}
    with client_factory() as client:
        async def seed_editor():
            db = await database.get_db()
            assert db.name == name
            await db.users.insert_one({"_id": "editor", "username": "Редактор", "role": "editor"})
        client.portal.call(seed_editor)
        token, _ = create_token("editor", "editor")
        client.headers["Authorization"] = "Bearer " + token
        response = client.post("/api/page-packages/preview",
                               files={"file": ("page.zip", pack_page(draft, {"photo": raw}), "application/zip")})
        assert response.status_code == 200, response.text
        preview = response.json()
        private_zip = data / "page-packages" / preview["id"] / "package.zip"
        archive_hash = sha256(private_zip.read_bytes()).hexdigest()
        image_url = "/uploads/page-packages/" + draft["id"] + "/photo.png"
        assert client.get(image_url).status_code == 404

    # Новый lifespan и новый Mongo client; файловый каталог сохраняется.
    with client_factory() as client:
        client.headers["Authorization"] = "Bearer " + token
        assert client.get("/api/page-packages/" + preview["id"]).status_code == 200
        assert sha256(private_zip.read_bytes()).hexdigest() == archive_hash
        response = client.post("/api/page-packages/" + preview["id"] + "/apply",
                               json={"hash": preview["hash"], "reviewed": True})
        assert response.status_code == 200, response.text
        target = response.json()["result"]["id"]
        photo = client.get(image_url)
        assert photo.status_code == 200 and sha256(photo.content).hexdigest() == sha256(raw).hexdigest()

    # После остановки writers сохраняем настоящий dump и все файлы.
    db_archive = tmp_path / "database.archive.gz"
    _mongo_archive("mongodump", name, db_archive)
    manifest = {"page-packages/" + item.relative_to(data / "page-packages").as_posix(): sha256(item.read_bytes()).hexdigest()
                for item in (data / "page-packages").rglob("*") if item.is_file()}
    files_archive = tmp_path / "media.tar.gz"
    with tarfile.open(files_archive, "w:gz") as archive:
        for folder in ("uploads", "page-packages"):
            archive.add(data / folder, arcname=folder)
        encoded = json.dumps(manifest).encode()
        info = tarfile.TarInfo("page-packages-manifest.json")
        info.size = len(encoded)
        archive.addfile(info, BytesIO(encoded))

    async def clear_test_db():
        db = await database.get_db()
        assert db.name == name and name.startswith("humorpedia_r5_test_")
        await db.client.drop_database(name)
        await database.close_db()
    asyncio.run(clear_test_db())
    _mongo_archive("mongorestore", name, db_archive)
    helper_path = Path(__file__).resolve().parents[2] / "scripts/vps-test/restore_files.py"
    spec = importlib.util.spec_from_file_location("r5_restore_files", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    restored = tmp_path / "restored"
    helper.extract_verified(files_archive, restored)
    monkeypatch.setenv("PAGE_PACKAGE_DIR", str(restored / "page-packages"))
    monkeypatch.setenv("UPLOAD_DIR", str(restored / "uploads"))
    with client_factory() as client:
        assert client.get("/api/ready").status_code == 200
        client.headers["Authorization"] = "Bearer " + token
        assert client.get("/api/content/people/" + target + "?raw=true").status_code == 200
        assert client.get("/api/page-packages/" + preview["id"]).status_code == 200
        restored_zip = restored / "page-packages" / preview["id"] / "package.zip"
        assert sha256(restored_zip.read_bytes()).hexdigest() == archive_hash
        photo = client.get(image_url)
        assert photo.status_code == 200 and sha256(photo.content).hexdigest() == sha256(raw).hexdigest()
        Image.open(BytesIO(photo.content)).verify()
