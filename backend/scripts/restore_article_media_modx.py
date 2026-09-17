#!/usr/bin/env python3
"""Restore missing images referenced by imported MODX articles and news.

The script is a dry run unless ``--apply`` is passed. It first reuses a file
whose Cyrillic name was mangled as UTF-8 read through CP866. Remaining files
are downloaded only from the allowlisted legacy host, validated as images and
atomically placed in the persistent imported-images volume.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.import_articles_news_modx import IMPORTED_IMAGES_PREFIX, MEDIA_ROOT, _missing_media  # noqa: E402
from utils.database import close_db, get_db  # noqa: E402


LEGACY_ORIGIN = "https://humorpedia.ru"
IMPORTED_IMAGES_ROOT = Path(MEDIA_ROOT) / "images"


def target_path(url: str, root: Path = IMPORTED_IMAGES_ROOT) -> Path:
    prefix = IMPORTED_IMAGES_PREFIX + "images/"
    if not url.startswith(prefix):
        raise ValueError(f"неподдерживаемый путь вне imported images: {url}")
    relative = Path(url[len(prefix):].replace("/", os.sep))
    target = (root / relative).resolve()
    resolved_root = root.resolve()
    if target != resolved_root and resolved_root not in target.parents:
        raise ValueError(f"небезопасный путь: {url}")
    return target


def legacy_url(url: str) -> str:
    relative = url[len(IMPORTED_IMAGES_PREFIX):]
    return f"{LEGACY_ORIGIN}/{quote(relative, safe='/')}"


def mojibake_source(target: Path) -> Path | None:
    if not target.parent.exists():
        return None
    for candidate in target.parent.iterdir():
        if not candidate.is_file():
            continue
        try:
            decoded = candidate.name.encode("cp866").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if decoded == target.name:
            return candidate
    return None


def validate_image(path: Path) -> None:
    with Image.open(path) as image:
        image.verify()


def copy_image(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name + ".", suffix=".part", delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        shutil.copy2(source, temporary)
        validate_image(temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def download(url: str, target: Path) -> None:
    source = legacy_url(url)
    target.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(source, timeout=30, stream=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if not content_type.startswith("image/"):
        raise ValueError(f"{source}: ожидалось изображение, получено {content_type or 'без MIME'}")
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name + ".", suffix=".part", delete=False) as tmp:
        temporary = Path(tmp.name)
        try:
            for chunk in response.iter_content(64 * 1024):
                if chunk:
                    tmp.write(chunk)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    try:
        if temporary.stat().st_size == 0:
            raise ValueError(f"{source}: получен пустой файл")
        validate_image(temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


async def missing_content_media(kinds: list[str]) -> list[str]:
    db = await get_db()
    missing: set[str] = set()
    collections = {"article": db.articles, "news": db.news}
    for kind in kinds:
        async for document in collections[kind].find({}, {"cover_image": 1, "modules": 1}):
            missing.update(_missing_media(document))
    return sorted(url for url in missing if url.startswith(IMPORTED_IMAGES_PREFIX + "images/"))


async def run(apply: bool, kinds: list[str]) -> int:
    urls = await missing_content_media(kinds)
    copied = downloaded = failed = 0
    print(f"Отсутствующих изображений ({', '.join(kinds)}): {len(urls)}")
    for url in urls:
        target = target_path(url)
        local_source = mojibake_source(target)
        action = f"копия {local_source.name}" if local_source else f"скачивание {legacy_url(url)}"
        if not apply:
            print(f"DRY RUN: {url} <- {action}")
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if local_source:
                copy_image(local_source, target)
                copied += 1
            else:
                download(url, target)
                downloaded += 1
            print(f"OK: {url}")
        except Exception as exc:
            failed += 1
            print(f"ERROR: {url}: {exc}")
    print(f"Итого: скопировано {copied}, скачано {downloaded}, ошибок {failed}")
    return 1 if failed else 0


def parse_args():
    parser = argparse.ArgumentParser(description="Восстановление изображений импортированных статей и новостей MODX")
    parser.add_argument("--kind", choices=("article", "news", "all"), default="all")
    parser.add_argument("--apply", action="store_true", help="скопировать/скачать файлы; без флага только dry-run")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    kinds = ["article", "news"] if args.kind == "all" else [args.kind]
    try:
        return await run(args.apply, kinds)
    finally:
        await close_db()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
