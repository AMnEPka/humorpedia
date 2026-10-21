"""Read-only отчёт private page-package storage. Никогда не удаляет данные."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

ASSET = re.compile(r'^[A-Za-z0-9_-]{1,100}$')
EXTENSION = re.compile(r'^[a-z0-9]{1,8}$')


def _uuid(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError('Некорректный UUID')
    return value


def _link(path):
    return path.is_symlink() or bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT) if os.name == 'nt' else path.is_symlink()


def scan_storage(package_dir, imports):
    root = Path(package_dir).absolute()
    expected, required, invalid = set(), set(), []
    for document in imports:
        try:
            package_id, entity = _uuid(document['_id']), _uuid(document['entity_key'])
            private = {package_id + '/package.zip'}
            public = set()
            for asset in document.get('assets', []):
                aid, ext = asset['id'], asset['ext']
                if not ASSET.fullmatch(aid) or not EXTENSION.fullmatch(ext):
                    raise ValueError('Некорректное имя asset')
                private.add(package_id + '/' + aid)
                public.add('published/' + entity + '/' + aid + '.' + ext)
        except (KeyError, ValueError, TypeError, AttributeError):
            invalid.append(str(document.get('_id', '<missing-id>')))
            continue
        required.update(private)
        # Даже error/applying хранит файлы для повторного применения.
        expected.update(private | public)
    found, unsafe = set(), []

    def walk(directory):
        for entry in directory.iterdir():
            relative = entry.relative_to(root).as_posix()
            if _link(entry):
                unsafe.append(relative)
            elif entry.is_dir():
                walk(entry)
            elif entry.is_file():
                found.add(relative)
            else:
                unsafe.append(relative)

    if any(_link(parent) for parent in (root, *root.parents) if parent.exists() or parent.is_symlink()):
        raise ValueError('Корень storage или его родитель содержит ссылку')
    exists = root.is_dir()
    if root.exists() and not exists:
        raise ValueError('Storage должен быть каталогом')
    if exists:
        walk(root)
    return {'storage_exists': exists, 'unreferenced_files': sorted(found - expected),
            'missing_package_files': sorted(required - found), 'unsafe_entries': sorted(unsafe),
            'invalid_records': sorted(invalid)}


async def report(args):
    from utils.database import get_db, close_db
    os.environ['DB_NAME'] = args.db_name
    try:
        db = await get_db()
        assert db.name == args.db_name
        documents = await db.page_package_imports.find({}, {'_id': 1, 'entity_key': 1, 'assets': 1}).to_list(None)
        result = scan_storage(args.package_dir, documents)
        result['note'] = 'Кандидаты по снимку БД и файлов. Это не разрешение на удаление; сверяйте при остановленных writers.'
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        await close_db()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db-name', required=True, help='Явное имя БД для чтения')
    parser.add_argument('--package-dir', required=True, help='Корень private storage')
    args = parser.parse_args()
    if not (os.environ.get('MONGO_URL') or os.environ.get('MONGO_HOST')):
        parser.error('Задайте подключение через MONGO_URL или MONGO_HOST в окружении')
    asyncio.run(report(args))


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()
