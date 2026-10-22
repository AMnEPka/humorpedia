"""Verify a trusted immutable build once at app registration, never on each GET."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType
from typing import Mapping
from services.html_react_shell import validate_template

class ReleaseError(ValueError):
    pass

@dataclass(frozen=True)
class HtmlRelease:
    release_id: str
    template_html: str
    files: Mapping[str, str]

def load_html_release(build_dir: Path) -> HtmlRelease:
    try:
        root = Path(build_dir)
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Invalid build directory")
        manifest_path = root / "public-html-release.json"
        if manifest_path.is_symlink():
            raise ValueError("Symlink manifest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest["files"]
        if manifest["schema_version"] != 1 or not isinstance(files, dict) or "index.html" not in files:
            raise ValueError("Invalid manifest schema")
        for name, digest in files.items():
            parts = PurePosixPath(name)
            if not name or parts.is_absolute() or "\\" in name or any(p in {".", ".."} for p in name.split("/")) or name == "public-html-release.json":
                raise ValueError("Invalid manifest path")
            if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
                raise ValueError("Invalid file hash")
            file = root / name
            if any(p.is_symlink() for p in [file, *file.parents] if p != root.parent):
                raise ValueError("Symlink in build")
            if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
                raise ValueError("Missing or changed build file")
        actual = set()
        for file in root.rglob("*"):
            if file.is_symlink():
                raise ValueError("Symlink in build")
            if file.is_file() and file != manifest_path:
                actual.add(file.relative_to(root).as_posix())
        if actual != set(files):
            raise ValueError("Unhashed build files")
        identity = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        if manifest["release_id"] != identity:
            raise ValueError("Invalid release identity")
        template = (root / "index.html").read_text(encoding="utf-8")
        validate_template(template)
        return HtmlRelease(identity, template, MappingProxyType(dict(files)))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError) as exc:
        raise ReleaseError("Public HTML release is unavailable or invalid") from exc
