#!/usr/bin/env python3
"""Safely restore the allowlisted file trees from a VPS media archive."""

import hashlib
import json
import os
import re
import stat
import sys
import tarfile
from pathlib import Path, PurePosixPath


ALLOWED_ROOTS = {"imported-images", "images", "uploads", "page-packages"}
MANIFEST_NAME = "page-packages-manifest.json"
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _member_path(info):
    name = info.name
    if not name or "\x00" in name or "\\" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise ValueError(f"Unsafe archive path: {name!r}")
    if info.isdir() and name.endswith("/"):
        name = name[:-1]
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"Unsafe archive path: {info.name!r}")
    if path.as_posix() != name:
        raise ValueError(f"Non-canonical archive path: {info.name!r}")
    if name == MANIFEST_NAME:
        if not info.isreg():
            raise ValueError("Package manifest must be a regular file")
        return name
    if path.parts[0] not in ALLOWED_ROOTS:
        raise ValueError(f"Archive path is not allowlisted: {info.name!r}")
    if len(path.parts) == 1 and not info.isdir():
        raise ValueError(f"Archive root must be a directory: {info.name!r}")
    if info.isdir():
        return name
    if info.type not in (tarfile.REGTYPE, tarfile.AREGTYPE):
        raise ValueError(f"Archive member is not a regular file: {info.name!r}")
    return name


def _validate_members(archive):
    names = set()
    members = []
    for info in archive.getmembers():
        name = _member_path(info)
        if name in names:
            raise ValueError(f"Duplicate archive member: {name}")
        names.add(name)
        members.append((name, info))

    files = {name for name, info in members if info.isreg() and name != MANIFEST_NAME}
    for file_name in files:
        prefix = file_name + "/"
        if any(name.startswith(prefix) for name in names):
            raise ValueError(f"File is also used as a directory: {file_name}")
    return members, files


def _read_manifest(archive, members):
    manifest_info = next((info for name, info in members if name == MANIFEST_NAME), None)
    private_files = {name for name, info in members if name.startswith("page-packages/") and info.isreg()}
    if manifest_info is None:
        if private_files:
            raise ValueError("Private package files require a SHA-256 manifest")
        return {}
    if manifest_info.size > MAX_MANIFEST_BYTES:
        raise ValueError("Package manifest is too large")
    stream = archive.extractfile(manifest_info)
    if stream is None:
        raise ValueError("Package manifest cannot be read")
    try:
        with stream:
            document = json.loads(
                stream.read(MAX_MANIFEST_BYTES + 1).decode("utf-8"),
                object_pairs_hook=_unique_object_pairs,
            )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Package manifest is not valid UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("Package manifest must map archive paths to SHA-256 values")
    if set(document) != private_files:
        raise ValueError("Package manifest paths do not exactly match private archive files")
    for name, digest in document.items():
        if not isinstance(name, str) or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ValueError(f"Invalid SHA-256 entry for {name!r}")
    return document


def _unique_object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate package manifest path: {key}")
        result[key] = value
    return result


def _check_no_symlink(path):
    current = Path(path).absolute()
    for part in (current, *current.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError(f"Restore path contains a symlink: {part}")
        try:
            attributes = part.lstat().st_file_attributes
        except (AttributeError, FileNotFoundError):
            attributes = 0
        if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise ValueError(f"Restore path contains a reparse point: {part}")


def _check_destinations(target_root, file_names):
    _check_no_symlink(target_root)
    if target_root.exists() and not target_root.is_dir():
        raise ValueError("Restore target must be a directory")
    for name in file_names:
        destination = target_root.joinpath(*PurePosixPath(name).parts)
        relative = destination.relative_to(target_root)
        _check_no_symlink(destination)
        current = target_root
        for component in relative.parts[:-1]:
            current = current / component
            if current.exists() and not current.is_dir():
                raise ValueError(f"Restore parent is not a directory: {current}")
        if destination.is_symlink() or destination.exists():
            raise FileExistsError(f"Refusing to overwrite restore destination: {destination}")


def _verify_package_hashes(archive, members, manifest):
    for name, info in members:
        if name not in manifest:
            continue
        source = archive.extractfile(info)
        if source is None:
            raise ValueError(f"Private archive member cannot be read: {name}")
        digest = hashlib.sha256()
        with source:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        if digest.hexdigest() != manifest[name]:
            raise ValueError(f"SHA-256 mismatch for private file: {name}")


def _create_parent_dirs(target_root, destination, created_dirs):
    missing = []
    current = destination.parent
    while current != target_root and not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        created_dirs.append(directory)


def extract_verified(archive_path, target_root):
    """Validate every member, verify private file hashes, then restore without overwrites."""
    target_root = Path(target_root).absolute()
    parent = target_root.parent
    if not parent.is_dir():
        raise ValueError("Restore target parent must already exist")
    _check_no_symlink(target_root)

    with tarfile.open(archive_path, mode="r:gz") as archive:
        members, file_names = _validate_members(archive)
        manifest = _read_manifest(archive, members)
        package_names = {name for name in file_names if name.startswith("page-packages/")}
        if package_names != set(manifest):
            raise ValueError("Package manifest paths do not match private archive files")
        _verify_package_hashes(archive, members, manifest)
        _check_destinations(target_root, file_names)
        root_created = not target_root.exists()
        target_root.mkdir(mode=0o700, parents=False, exist_ok=True)
        created_files = []
        created_dirs = []
        try:
            for name, info in members:
                if not info.isreg() or name == MANIFEST_NAME:
                    continue
                destination = target_root.joinpath(*PurePosixPath(name).parts)
                _create_parent_dirs(target_root, destination, created_dirs)
                source = archive.extractfile(info)
                if source is None:
                    raise ValueError(f"Archive member cannot be read: {name}")
                digest = hashlib.sha256() if name in manifest else None
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW
                fd = os.open(destination, flags, 0o600)
                created_files.append(destination)
                with source, os.fdopen(fd, "wb") as output:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        if digest:
                            digest.update(chunk)
                if digest and digest.hexdigest() != manifest[name]:
                    raise ValueError(f"SHA-256 mismatch for private file: {name}")
                os.chmod(destination, 0o600)
        except Exception:
            for path in reversed(created_files):
                path.unlink(missing_ok=True)
            for path in reversed(created_dirs):
                try:
                    path.rmdir()
                except OSError:
                    pass
            if root_created:
                try:
                    target_root.rmdir()
                except OSError:
                    pass
            raise


def main(argv):
    if len(argv) != 3:
        raise SystemExit("Usage: restore_files.py MEDIA_ARCHIVE TARGET_DATA_DIR")
    extract_verified(argv[1], argv[2])


if __name__ == "__main__":
    main(sys.argv)
