#!/usr/bin/env python3
"""Restore cover images referenced by published MODX quizzes.

Dry-run by default. Files are copied from the local archive when an explicit
match is known; otherwise they are downloaded from the allowlisted legacy host
and validated as images before an atomic replace.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.restore_article_media_modx import copy_image, download, legacy_url  # noqa: E402
from services.modx_content import IMPORTED_IMAGES_PREFIX, image_url  # noqa: E402
from services.modx_dump import load_modx_site  # noqa: E402
from services.modx_quizzes import QUIZ_PARENT_ID, quiz_resources  # noqa: E402


DEFAULT_DUMP = "/app/backups/idemsku8_modx2.sql"
MEDIA_ROOT = Path("/app/media/imported")
LOCAL_ARCHIVE_OVERRIDES = {
    "assets/project_files/img/studiya-soyuz-tnt.jpg":
        Path("/app/backups/images/quiz/studiya-soyuz-tnt.jpg"),
}


def target_path(url: str, root: Path = MEDIA_ROOT) -> Path:
    if not url.startswith(IMPORTED_IMAGES_PREFIX):
        raise ValueError(f"неподдерживаемый путь: {url}")
    relative = Path(url[len(IMPORTED_IMAGES_PREFIX):].replace("/", os.sep))
    target = (root / relative).resolve()
    resolved_root = root.resolve()
    if target == resolved_root or resolved_root not in target.parents:
        raise ValueError(f"небезопасный путь: {url}")
    return target


def quiz_cover_urls(dump: str) -> list[str]:
    site = load_modx_site(
        dump,
        keep_content_for=lambda resource: resource.get("parent") == QUIZ_PARENT_ID,
    )
    urls = []
    for resource in quiz_resources(site):
        url = image_url(site.tv(resource["id"], "img"))
        if url:
            urls.append(url)
    return sorted(set(urls))


def run(dump: str, apply: bool) -> int:
    urls = [url for url in quiz_cover_urls(dump) if not target_path(url).exists()]
    copied = downloaded = failed = 0
    print(f"Отсутствующих обложек опубликованных квизов: {len(urls)}")
    for url in urls:
        relative = url[len(IMPORTED_IMAGES_PREFIX):]
        target = target_path(url)
        local_source = LOCAL_ARCHIVE_OVERRIDES.get(relative)
        action = f"копия {local_source}" if local_source and local_source.is_file() else f"скачивание {legacy_url(url)}"
        if not apply:
            print(f"DRY RUN: {url} <- {action}")
            continue
        try:
            if local_source and local_source.is_file():
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
    parser = argparse.ArgumentParser(description="Восстановление обложек квизов MODX")
    parser.add_argument("--dump", default=DEFAULT_DUMP)
    parser.add_argument("--apply", action="store_true", help="скопировать/скачать файлы; без флага только dry-run")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(run(args.dump, args.apply))
