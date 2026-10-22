from fastapi import FastAPI
from services.static_media import MediaStaticFiles
from fastapi.testclient import TestClient


def test_webp_static_files_use_image_mime_without_changing_other_types(tmp_path):
    payloads = {
        "poster.webp": b"webp-lower",
        "poster-copy.webP": b"webp-upper",
        "photo.jpg": b"jpeg",
        "cover.png": b"png",
    }
    for filename, payload in payloads.items():
        (tmp_path / filename).write_bytes(payload)

    app = FastAPI()
    app.mount("/media", MediaStaticFiles(directory=tmp_path), name="media")

    with TestClient(app) as client:
        for filename, payload in payloads.items():
            response = client.get(f"/media/{filename}")
            assert response.status_code == 200
            assert response.content == payload
            expected_type = "image/webp" if filename.lower().endswith(".webp") else {
                ".jpg": "image/jpeg",
                ".png": "image/png",
            }[tmp_path.joinpath(filename).suffix.lower()]
            assert response.headers["content-type"] == expected_type

        webp_get = client.get("/media/poster.webp")
        head = client.head("/media/poster.webp")
        assert head.status_code == 200
        assert head.content == b""
        assert head.headers["content-type"] == "image/webp"
        assert head.headers["content-length"] == str(len(payloads["poster.webp"]))
        assert head.headers["etag"] == webp_get.headers["etag"]

        not_modified = client.get(
            "/media/poster.webp",
            headers={"If-None-Match": webp_get.headers["etag"]},
        )
        assert not_modified.status_code == 304
        assert not_modified.content == b""

        missing = client.get("/media/missing.webp")
        assert missing.status_code == 404
