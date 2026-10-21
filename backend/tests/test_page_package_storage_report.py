"""Отчёт private storage не удаляет файлы и не следует по ссылкам."""
from pathlib import Path
import uuid

import pytest


def test_storage_report_keeps_retry_files_and_lists_only_unreferenced_candidates(tmp_path):
    from scripts.report_page_package_storage import scan_storage
    package_id, entity_key, other = [str(uuid.uuid4()) for _ in range(3)]
    doc = {'_id': package_id, 'entity_key': entity_key, 'status': 'error',
           'assets': [{'id': 'photo', 'ext': 'png'}]}
    paths = [package_id + '/package.zip', package_id + '/photo',
             'published/' + entity_key + '/photo.png', other + '/interrupted.tmp']
    for relative in paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'private fixture')
    before = {str(path.relative_to(tmp_path)): path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()}
    report = scan_storage(tmp_path, [doc])
    assert report['unreferenced_files'] == [other + '/interrupted.tmp']
    assert report['missing_package_files'] == []
    assert report['invalid_records'] == []
    assert before == {str(path.relative_to(tmp_path)): path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()}


def test_storage_report_missing_root_does_not_create_it(tmp_path):
    from scripts.report_page_package_storage import scan_storage
    package_id, entity_key = [str(uuid.uuid4()) for _ in range(2)]
    missing = tmp_path / 'absent'
    report = scan_storage(missing, [{'_id': package_id, 'entity_key': entity_key, 'assets': []}])
    assert report['storage_exists'] is False
    assert report['missing_package_files'] == [package_id + '/package.zip']
    assert not missing.exists()


def test_storage_report_rejects_invalid_manifest_paths_without_reading_outside_root(tmp_path):
    from scripts.report_page_package_storage import scan_storage
    package_id, entity_key = [str(uuid.uuid4()) for _ in range(2)]
    report = scan_storage(tmp_path, [{'_id': package_id, 'entity_key': entity_key,
                                    'assets': [{'id': '../secret', 'ext': 'png'}]}])
    assert report['invalid_records'] == [package_id]


def test_storage_report_does_not_follow_symlinks(tmp_path):
    from scripts.report_page_package_storage import scan_storage
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'secret.txt').write_text('private')
    root = tmp_path / 'storage'
    root.mkdir()
    try:
        (root / 'linked').symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('Symlink creation unavailable')
    report = scan_storage(root, [])
    assert report['unsafe_entries'] == ['linked']
    assert report['unreferenced_files'] == []
