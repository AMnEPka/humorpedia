"""Переносимый документ должен оставаться обычным редактируемым контентом."""
from copy import deepcopy
from io import BytesIO
from hashlib import sha256
import json
import zipfile

import pytest
from PIL import Image

from services.page_packages import seed_page, validate_page, pack_page, unpack_page, image_info


@pytest.mark.parametrize('kind', ['person', 'team', 'show'])
def test_roundtrip_keeps_normal_editable_fields_and_modules(kind):
    page = seed_page(kind, {'name': 'Тестовая страница'})
    page['modules'].append({'id': 'bio', 'type': 'text_block', 'order': 5,
                            'visible': True, 'data': {'title': 'История', 'content': '<p>Первый текст.</p>'}})
    draft = {'id': '2c8c0d89-515c-433e-ab68-9f75e7e2e625', 'kind': kind, 'revision': 2,
             'page': page, 'materials': {}, 'relations': [], 'assets': []}
    data = pack_page(draft, {})
    restored = unpack_page(data)
    assert restored['page']['modules'][-1]['data']['content'] == '<p>Первый текст.</p>'
    restored['page']['modules'][-1]['data']['content'] = '<p>Исправлено редактором.</p>'
    validated = validate_page(kind, restored['page'])
    assert validated['modules'][-1]['data']['content'] == '<p>Исправлено редактором.</p>'
    assert '_id' not in validated
    assert unpack_page(pack_page(draft, {}))['manifest']['package_id'] == restored['manifest']['package_id']


def test_missing_birth_data_and_projects_do_not_block_manual_authoring():
    page = validate_page('person', seed_page('person', {'name': 'Иван Иванов'}))
    assert page['full_name'] == 'Иван Иванов'
    assert not page['bio']['birth_date']


@pytest.mark.parametrize('date', ['1988', '17.04', '1988-04-17'])
def test_partial_birth_date_precision_is_preserved(date):
    page = seed_page('person', {'name': 'Иван Иванов', 'birth_date': date})
    assert validate_page('person', page)['bio']['birth_date'] == date
    assert page['facts']['Дата рождения'] == date


def test_invalid_date_and_external_database_ids_are_rejected():
    page = seed_page('person', {'name': 'Иван Иванов'})
    page['bio']['birth_date'] = '31.02.2000'
    with pytest.raises(ValueError):
        validate_page('person', page)
    page['bio']['birth_date'] = ''
    page['show_ids'] = ['local-id']
    with pytest.raises(ValueError):
        validate_page('person', page)


def test_html_cannot_execute_and_unsafe_urls_are_rejected():
    page = seed_page('person', {'name': 'Иван Иванов'})
    page['modules'].append({'id': 'bio', 'type': 'text_block', 'order': 5, 'visible': True,
        'data': {'content': '<p onclick="alert(1)">Текст<script>alert(2)</script><a href="javascript:alert(3)">ссылка</a></p>'}})
    clean = validate_page('person', page)['modules'][-1]['data']['content']
    assert '<script' not in clean and 'onclick' not in clean and 'javascript:' not in clean
    page['photo'] = {'url': 'http://localhost:8001/uploads/a.jpg'}
    with pytest.raises(ValueError):
        validate_page('person', page)


def test_zip_rejects_traversal_and_hash_mismatch():
    draft = {'id': '2c8c0d89-515c-433e-ab68-9f75e7e2e625', 'kind': 'person', 'revision': 1,
             'page': seed_page('person', {'name': 'Иван Иванов'}), 'materials': {}, 'relations': [], 'assets': []}
    data = pack_page(draft, {})
    out = BytesIO(data)
    with zipfile.ZipFile(out, 'a') as archive:
        archive.writestr('../escape.txt', 'attack')
    with pytest.raises(ValueError):
        unpack_page(out.getvalue())
    out = BytesIO()
    with zipfile.ZipFile(BytesIO(data)) as source, zipfile.ZipFile(out, 'w') as target:
        for name in source.namelist():
            target.writestr(name, b'{}' if name == 'page.json' else source.read(name))
    with pytest.raises(ValueError):
        unpack_page(out.getvalue())


def test_photo_is_packaged_and_verified_as_an_image():
    buffer = BytesIO()
    Image.new('RGB', (12, 12)).save(buffer, 'PNG')
    raw = buffer.getvalue()
    meta = image_info(raw, 'photo.png')
    page = seed_page('person', {'name': 'Иван Иванов'})
    page['photo'] = {'url': 'asset:portrait', 'alt': 'Иван'}
    draft = {'id': '2c8c0d89-515c-433e-ab68-9f75e7e2e625', 'kind': 'person', 'revision': 1,
             'page': page, 'materials': {}, 'relations': [], 'assets': [dict(meta, id='portrait')]}
    unpacked = unpack_page(pack_page(draft, {'portrait': raw}))
    assert unpacked['asset_bytes']['portrait'] == raw
    with pytest.raises(ValueError):
        image_info(b'not an image', 'photo.png')
    with pytest.raises(ValueError):
        pack_page(draft, {})


@pytest.mark.parametrize('module_type,data', [
    ('gallery', {'images': 'oops'}),
    ('gallery', {'images': [None]}),
    ('timeline', {'events': {}}),
    ('timeline', {'events': [{'title': {'bad': 'object'}}]}),
    ('table', {'rows': [{'a': 'value'}]}),
    ('table', {'rows': [[{'bad': 'object'}]]}),
    ('table', {'headers': {'a': 'header'}}),
    ('tags', {'tags': 'tag'}),
    ('hero_card', {'facts': [{'value': []}]}),
    ('participants', {'items': [{'name': 'Иван', 'facts': 'broken'}]}),
    ('participants', {'items': [{'name': 'Иван', 'person_id': 'local-database-id'}]}),
    ('text_block', {'title': {}, 'content': 'Текст'}),
    ('quote', {'text': ['Текст']}),
])
def test_malformed_module_data_cannot_be_saved_or_exported(module_type, data):
    page = seed_page('show', {'name': 'Тест'})
    page['modules'].append({'id': 'bad', 'type': module_type, 'data': data})
    with pytest.raises(ValueError, match='модул'):
        validate_page('show', page)


@pytest.mark.parametrize('module_type,data', [
    ('text_block', {'title': 'Текст', 'content': '<p>Текст.</p>', 'collapsed': True, 'anchor_id': 'bio'}),
    ('gallery', {'title': 'Фото', 'images': [{'url': 'asset:photo', 'alt': 'Фото', 'caption': ''}]}),
    ('timeline', {'events': [{'year': '2007–2013', 'title': '', 'description': '<p>Текст.</p>'}]}),
    ('timeline', {'events': [{'year': 2007, 'date': None, 'title': 'Начало'}]}),
    ('table', {'headers': ['Год', 'Итог'], 'rows': [[2007, 'Текст'], [None, 1.5]], 'hasHeaders': True, 'sortable': False}),
    ('hero_card', {'image': 'asset:photo', 'caption': 'Фото', 'facts': [{'label': 'Город', 'value': 'Москва'}]}),
    ('participants', {'items': [{'name': '', 'person_slug': None, 'photo': '', 'facts': [{'title': '', 'value': ''}]}]}),
    ('tags', {'tags': ['КВН']}),
    ('poster_photo', {}),
])
def test_standard_editor_module_values_are_preserved(module_type, data):
    page = seed_page('show', {'name': 'Тест'})
    page['modules'].append({'id': 'valid', 'type': module_type, 'data': deepcopy(data)})
    assert validate_page('show', page)['modules'][-1]['data'] == data


def test_same_payload_new_revision_has_a_distinct_repeatable_package_id():
    draft = {'id': '2c8c0d89-515c-433e-ab68-9f75e7e2e625', 'kind': 'person', 'revision': 1,
             'page': seed_page('person', {'name': 'Иван Иванов'}), 'materials': {}, 'relations': [], 'assets': []}
    first = unpack_page(pack_page(draft, {}))['manifest']
    draft['revision'] = 2
    second = unpack_page(pack_page(draft, {}))['manifest']
    assert first['entity_key'] == second['entity_key']
    assert first['package_id'] != second['package_id']
    assert second == unpack_page(pack_page(draft, {}))['manifest']


def test_zip_import_rejects_malformed_module_even_with_valid_checksums():
    draft = {'id': '2c8c0d89-515c-433e-ab68-9f75e7e2e625', 'kind': 'show', 'revision': 1,
             'page': seed_page('show', {'name': 'Тест'}), 'materials': {}, 'relations': [], 'assets': []}
    with zipfile.ZipFile(BytesIO(pack_page(draft, {}))) as source:
        files = {name: source.read(name) for name in source.namelist()}
    page = json.loads(files['page.json'])
    page['page']['modules'].append({'id': 'gallery', 'type': 'gallery', 'data': {'images': 'broken'}})
    files['page.json'] = json.dumps(page).encode()
    manifest = json.loads(files['manifest.json'])
    manifest['files']['page.json'] = {'size': len(files['page.json']), 'sha256': sha256(files['page.json']).hexdigest()}
    files['manifest.json'] = json.dumps(manifest).encode()
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w') as target:
        for name, raw in files.items():
            target.writestr(name, raw)
    with pytest.raises(ValueError, match='gallery.images'):
        unpack_page(buffer.getvalue())
