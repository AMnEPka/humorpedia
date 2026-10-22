import hashlib
import json
import pytest
from services.public_html_release import load_html_release, ReleaseError

TEMPLATE = '<!doctype html><html><head><title>App</title></head><body><div id="root"></div></body></html>'

def make_release(root, template=TEMPLATE):
    (root / "assets").mkdir()
    (root / "index.html").write_text(template)
    (root / "assets/chunk.js").write_text("chunk")
    files = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ["assets/chunk.js", "index.html"]}
    release = {"schema_version": 1, "release_id": identity(files), "files": files}
    (root / "public-html-release.json").write_text(json.dumps(release))
    return release

def identity(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def test_valid_release(tmp_path):
    expected = make_release(tmp_path)
    result = load_html_release(tmp_path)
    assert result.release_id == expected["release_id"]
    assert result.template_html == TEMPLATE
    with pytest.raises(TypeError):
        result.files["x"] = "bad"

@pytest.mark.parametrize("fault", ["missing", "changed", "template", "escape", "symlink", "extra", "identity"])
def test_rejects_missing_chunk_or_changed_template(tmp_path, fault):
    release = make_release(tmp_path)
    if fault == "missing": (tmp_path / "assets/chunk.js").unlink()
    elif fault == "changed": (tmp_path / "index.html").write_text("changed")
    elif fault == "template":
        (tmp_path / "index.html").write_text(TEMPLATE.replace('<div id="root"></div>', '<div id="root">unsafe</div>'))
        release["files"]["index.html"] = hashlib.sha256((tmp_path / "index.html").read_bytes()).hexdigest()
    elif fault == "escape": release["files"]["../secret"] = "0" * 64
    elif fault == "symlink":
        (tmp_path / "assets/chunk.js").unlink()
        (tmp_path / "assets/chunk.js").symlink_to(tmp_path / "index.html")
    elif fault == "extra": (tmp_path / "unhashed.js").write_text("extra")
    elif fault == "identity": release["release_id"] = "0" * 64
    if fault != "identity": release["release_id"] = identity(release["files"])
    (tmp_path / "public-html-release.json").write_text(json.dumps(release))
    with pytest.raises(ReleaseError): load_html_release(tmp_path)
