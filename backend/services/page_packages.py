"""Проверяемый ZIP одной страницы. Никаких локальных ID или исполняемой разметки."""
from copy import deepcopy
from datetime import date
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import PurePosixPath
import re
from urllib.parse import urlsplit
import uuid
import zipfile

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from models.content import PersonCreate, TeamCreate, ShowCreate
from utils.slugify import generate_slug

MAX_ZIP = 50 * 1024 * 1024
MAX_IMAGE = 10 * 1024 * 1024
MAX_TOTAL = 100 * 1024 * 1024
MODELS = {'person': PersonCreate, 'team': TeamCreate, 'show': ShowCreate}
COLLECTIONS = {'person': 'people', 'team': 'teams', 'show': 'shows'}
MEDIA_FIELDS = {'person': 'photo', 'team': 'logo', 'show': 'poster'}
MODULES = {'text_block', 'timeline', 'image', 'gallery', 'table', 'quote', 'hero_card',
           'tags', 'poster_photo', 'facts_table', 'tags_cloud', 'social_links',
           'rating_widget', 'participants'}
COMMON = {'title', 'slug', 'facts', 'facts_order', 'modules', 'tags', 'seo', 'social_links', 'aliases'}
FIELDS = {'person': COMMON | {'full_name', 'photo', 'bio', 'primary_tag', 'foreign_agent'},
          'team': COMMON | {'name', 'logo', 'primary_tag', 'team_type'},
          'show': COMMON | {'name', 'poster', 'description'}}
URL_KEYS = {'url', 'href', 'link', 'src', 'thumbnail', 'image', 'person_url', 'video_url', 'photo', 'og_image'}

# Формат переноса ограничен данными, которые умеют читать штатные формы и
# публичные компоненты. PageModule.data сам по себе принимает произвольный dict.
_TEXT = (str, type(None))
_FACT = {'title': _TEXT, 'label': _TEXT, 'value': _TEXT, 'link': _TEXT}
_IMAGE = {key: _TEXT for key in ('url', 'thumbnail', 'alt', 'caption')}
_EVENT = {**{key: _TEXT for key in ('date', 'title', 'description', 'image', 'link', 'type')},
          'year': (str, int, type(None)), 'month': (int, type(None))}
_SOCIAL = {key: _TEXT for key in ('vk', 'telegram', 'youtube', 'instagram', 'website')}
MODULE_DATA = {
    'text_block': {'title': _TEXT, 'content': _TEXT, 'anchor_id': _TEXT, 'collapsed': (bool,)},
    'timeline': {'title': _TEXT, 'events': [_EVENT]},
    'image': _IMAGE,
    'gallery': {'title': _TEXT, 'images': [_IMAGE]},
    'quote': {'text': _TEXT, 'author': _TEXT, 'source': _TEXT},
    'hero_card': {'title': _TEXT, 'photo': _TEXT, 'image': _TEXT, 'photo_alt': _TEXT,
                  'caption': _TEXT, 'facts': [_FACT], 'social_links': _SOCIAL},
    'tags': {'title': _TEXT, 'tags': [(str,)]},
    'table': {'title': _TEXT, 'description': _TEXT, 'headers': [(str,)],
              'rows': [[(str, int, float, type(None))]],
              'hasHeaders': (bool,), 'sortable': (bool,), 'collapsed': (bool,),
              'columns': [{'key': (str,), 'label': (str,), 'width': _TEXT,
                           'sortable': (bool,), 'highlight': (bool,)}]},
    'participants': {'title': _TEXT, 'items': [{
        **{key: _TEXT for key in ('name', 'person_slug', 'person_url', 'photo', 'image', 'caption', 'role')},
        'facts': [_FACT], 'from_year': (int, type(None)), 'to_year': (int, type(None)),
        'episodes_count': (int, type(None)),
    }]},
    **{kind: {'title': _TEXT} for kind in ('poster_photo', 'facts_table', 'tags_cloud', 'social_links', 'rating_widget')},
}


def _validate_module_shape(value, schema, path):
    """Проверить типы без coercion/удаления полей, сохранив данные редактора."""
    if isinstance(schema, dict):
        if not isinstance(value, dict):
            raise ValueError(f'Некорректные данные модуля: {path} должен быть объектом')
        unknown = set(value) - set(schema)
        if unknown:
            raise ValueError(f'Непереносимые поля модуля {path}: ' + ', '.join(sorted(unknown)))
        for key, item in value.items():
            _validate_module_shape(item, schema[key], path + '.' + key)
    elif isinstance(schema, list):
        if not isinstance(value, list):
            raise ValueError(f'Некорректные данные модуля: {path} должен быть списком')
        for index, item in enumerate(value):
            _validate_module_shape(item, schema[0], f'{path}[{index}]')
    elif type(value) not in schema:
        raise ValueError(f'Некорректный тип поля модуля {path}')


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def safe_url(value, media=False):
    if not value:
        return value
    if not isinstance(value, str) or any(ord(c) < 32 for c in value) or '\\' in value:
        raise ValueError('Недопустимый адрес')
    if re.fullmatch(r'asset:[a-zA-Z0-9_-]{1,80}', value):
        return value
    parsed = urlsplit(value)
    if parsed.scheme in ('http', 'https') and parsed.hostname:
        host = parsed.hostname.lower()
        if host in ('localhost', '127.0.0.1', '::1', '0.0.0.0') or host.endswith('.localhost'):
            raise ValueError('Адрес localhost нельзя перенести на другой сайт')
        if not media:
            return value
    if value.startswith('/') and not value.startswith('//') and not parsed.scheme:
        if '..' not in PurePosixPath(parsed.path).parts and not media:
            return value
    if value.startswith('#') and not media:
        return value
    raise ValueError('Изображение нужно добавить в пакет' if media else 'Допустимы только http(s) и внутренние пути сайта')


class _HTML(HTMLParser):
    allowed = {'p', 'br', 'strong', 'em', 'b', 'i', 'u', 's', 'ul', 'ol', 'li', 'h2', 'h3', 'h4',
               'blockquote', 'a', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'span', 'div'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.blocked = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'iframe', 'object', 'svg', 'math'}:
            self.blocked += 1
        if self.blocked or tag not in self.allowed:
            return
        allowed_attrs = []
        for key, value in attrs:
            if tag == 'a' and key == 'href':
                try:
                    allowed_attrs.append(f'href="{escape(safe_url(value or ""), quote=True)}"')
                except ValueError:
                    pass
            if key in ('colspan', 'rowspan') and tag in ('td', 'th') and re.fullmatch(r'[1-9][0-9]?', value or ''):
                allowed_attrs.append(f'{key}="{value}"')
        self.out.append('<' + tag + (' ' + ' '.join(allowed_attrs) if allowed_attrs else '') + '>')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'iframe', 'object', 'svg', 'math'}:
            self.blocked = max(0, self.blocked - 1)
            return
        if not self.blocked and tag in self.allowed and tag != 'br':
            self.out.append(f'</{tag}>')

    def handle_data(self, value):
        if not self.blocked:
            self.out.append(escape(value, quote=False))


def sanitize(value):
    parser = _HTML()
    parser.feed(value)
    parser.close()
    return ''.join(parser.out)


def clean_tree(value, key=''):
    if isinstance(value, dict):
        return {k: clean_tree(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_tree(v, key) for v in value]
    if isinstance(value, str):
        if len(value) > 100000:
            raise ValueError('Слишком длинный текст')
        if key in URL_KEYS:
            return safe_url(value, media=key in {'url', 'thumbnail', 'image', 'photo', 'og_image'} and value.startswith(('asset:', '/uploads', '/media', 'http')))
        return sanitize(value) if '<' in value else value
    return value


def validate_birth_date(value):
    if not value:
        return
    try:
        if re.fullmatch(r'\d{4}', value):
            date(int(value), 1, 1)
        elif re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            date.fromisoformat(value)
        elif re.fullmatch(r'\d{1,2}\.\d{1,2}(?:\.\d{4})?', value):
            parts = list(map(int, value.split('.')))
            date(parts[2] if len(parts) == 3 else 2000, parts[1], parts[0])
        else:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('Дата рождения: ГГГГ, ДД.ММ, ДД.ММ.ГГГГ или ГГГГ-ММ-ДД')


def validate_page(kind, page):
    if kind not in MODELS or not isinstance(page, dict):
        raise ValueError('Неизвестный тип страницы')
    if len(json_bytes(page)) > 1024 * 1024:
        raise ValueError('Страница превышает 1 MiB')
    # status может прийти из стандартного редактора, но не определяет публикацию.
    extra = set(page) - FIELDS[kind] - {'status', 'content_type'}
    if extra:
        raise ValueError('Непереносимые поля: ' + ', '.join(sorted(extra)))
    data = {k: v for k, v in deepcopy(page).items() if k in FIELDS[kind]}
    if not str(data.get('title', '')).strip() or not re.fullmatch(r'[a-z0-9]+(?:[-_][a-z0-9]+)*', str(data.get('slug', ''))):
        raise ValueError('Нужны название и корректный slug латиницей')
    if kind == 'team' and data.get('team_type', 'kvn') != 'kvn':
        raise ValueError('Первая версия поддерживает команды КВН')
    if kind == 'person':
        bio = data.get('bio') or {}
        validate_birth_date(bio.get('birth_date'))
        facts = data.setdefault('facts', {})
        # Редакторское изменение отображаемого факта важнее устаревшего bio.
        if 'Дата рождения' in facts:
            validate_birth_date(facts['Дата рождения'])
            if bio.get('birth_date') and bio['birth_date'] != facts['Дата рождения']:
                raise ValueError('Дата рождения в биографии и таблице фактов различается')
        elif bio.get('birth_date'):
            facts['Дата рождения'] = bio['birth_date']
        if bio.get('birth_place') and 'Место рождения' not in facts:
            facts['Место рождения'] = bio['birth_place']
    modules = data.get('modules') or []
    ids = set()
    if not isinstance(modules, list):
        raise ValueError('Модули должны быть списком')
    if len(modules) > 80:
        raise ValueError('Допустимо до 80 модулей')
    for module in modules:
        if not isinstance(module, dict):
            raise ValueError('Некорректный модуль')
        if not isinstance(module.get('type'), str) or module['type'] not in MODULES or (module.get('type') == 'participants' and kind != 'show'):
            raise ValueError('Неподдерживаемый модуль: ' + str(module.get('type')))
        if not isinstance(module.get('id'), str) or not module['id'] or module['id'] in ids:
            raise ValueError('ID модулей должны быть заполнены и уникальны')
        ids.add(module['id'])
        _validate_module_shape(module.get('data', {}), MODULE_DATA[module['type']], module['type'])
    data = clean_tree(data)
    for network, url in (data.get('social_links') or {}).items():
        safe_url(url)
    try:
        model = MODELS[kind].model_validate(data)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    result = model.model_dump(mode='json', exclude_none=True)
    return {key: value for key, value in result.items() if key in FIELDS[kind]}


def seed_page(kind, materials):
    name = materials['name'].strip()
    page = {'title': name, 'slug': generate_slug(name), 'modules': [
        {'id': 'photo', 'type': 'poster_photo', 'order': 0, 'visible': True, 'data': {}},
        {'id': 'facts', 'type': 'facts_table', 'order': 1, 'visible': True, 'data': {}},
        {'id': 'social', 'type': 'social_links', 'order': 2, 'visible': True, 'data': {}},
    ], 'facts': {}, 'facts_order': [], 'tags': [], 'seo': {}, 'social_links': {}}
    page['full_name' if kind == 'person' else 'name'] = name
    if kind == 'person':
        page['bio'] = {'birth_date': materials.get('birth_date', ''), 'birth_place': materials.get('birth_place', ''),
                       'occupation': [materials['occupation']] if materials.get('occupation') else [], 'achievements': []}
        for key, label in [('birth_date', 'Дата рождения'), ('birth_place', 'Место рождения'), ('occupation', 'Деятельность')]:
            if materials.get(key):
                page['facts'][label] = materials[key]
    else:
        for key, label in [('birth_date', 'Год основания' if kind == 'team' else 'Премьера'),
                           ('birth_place', 'Город'), ('occupation', 'Формат')]:
            if materials.get(key):
                page['facts'][label] = materials[key]
    page['facts_order'] = list(page['facts'])
    return validate_page(kind, page)


def page_warnings(kind, page):
    result = []
    if not page.get(MEDIA_FIELDS[kind]):
        result.append('Не добавлено изображение')
    if not any(m['type'] == 'text_block' and m.get('data', {}).get('content') for m in page.get('modules', [])):
        result.append('Нет описания или биографии')
    if kind == 'person':
        if not page.get('bio', {}).get('birth_date'):
            result.append('Дата рождения неизвестна')
        if not page.get('bio', {}).get('birth_place'):
            result.append('Место рождения неизвестно')
    return result


def validate_relations(kind, relations):
    if not isinstance(relations, list) or len(relations) > 100:
        raise ValueError('Допустимо до 100 связей')
    seen = set()
    result = []
    for row in relations:
        if not isinstance(row, dict) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', str(row.get('id', ''))) or row['id'] in seen:
            raise ValueError('У связи должен быть уникальный ID')
        seen.add(row['id'])
        allowed = {'id', 'kind', 'target', 'achievement', 'name', 'roles', 'from_year', 'to_year'}
        if set(row) - allowed:
            raise ValueError('Неизвестные поля связи')
        if row.get('kind') == 'appearance' and kind == 'person':
            if row.get('achievement', 'participant') not in {'participant', 'finalist', 'winner'}:
                raise ValueError('Некорректное достижение')
            target_type = 'show'
        elif row.get('kind') == 'membership' and kind == 'team':
            if not isinstance(row.get('name'), str) or not row['name'].strip():
                raise ValueError('Укажите имя участника')
            if not isinstance(row.get('roles', []), list) or any(not isinstance(v, str) for v in row.get('roles', [])):
                raise ValueError('Роли должны быть списком строк')
            for key in ('from_year', 'to_year'):
                if row.get(key) not in (None, '') and (type(row[key]) is not int or not 1800 <= row[key] <= 2200):
                    raise ValueError('Некорректный год участия')
            target_type = 'person'
        else:
            raise ValueError('Неподдерживаемая связь для этого типа страницы')
        target = row.get('target')
        if target:
            if set(target) - {'type', 'slug', 'path'} or target.get('type') != target_type:
                raise ValueError('Некорректная ссылка на страницу')
            if not re.fullmatch(r'[a-z0-9]+(?:[-_][a-z0-9]+)*', target.get('slug', '')):
                raise ValueError('Укажите slug связанной страницы')
            if target.get('path') and not re.fullmatch(r'[a-z0-9/_-]+', target['path']):
                raise ValueError('Некорректный путь связанного шоу')
        elif target_type == 'show':
            raise ValueError('Укажите шоу для участия')
        result.append(deepcopy(row))
    return result


def image_info(raw, filename):
    if not raw or len(raw) > MAX_IMAGE:
        raise ValueError('Изображение должно быть не больше 10 MiB')
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.format not in {'JPEG', 'PNG', 'WEBP', 'GIF'} or image.width * image.height > 40000000:
                raise ValueError('Неподдерживаемое или слишком большое изображение')
            fmt, width, height = image.format, image.width, image.height
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Файл не является корректным изображением') from exc
    ext, mime = {'JPEG': ('jpg', 'image/jpeg'), 'PNG': ('png', 'image/png'),
                 'WEBP': ('webp', 'image/webp'), 'GIF': ('gif', 'image/gif')}[fmt]
    return {'filename': PurePosixPath(filename.replace('\\', '/')).name[:200], 'ext': ext, 'mime': mime,
            'size': len(raw), 'sha256': sha256(raw).hexdigest(), 'width': width, 'height': height, 'alt': '', 'caption': ''}


def asset_refs(value):
    refs = set()
    if isinstance(value, dict):
        for item in value.values():
            refs |= asset_refs(item)
    elif isinstance(value, list):
        for item in value:
            refs |= asset_refs(item)
    elif isinstance(value, str):
        refs.update(re.findall(r'asset:([a-zA-Z0-9_-]+)', value))
    return refs


def remap_assets(value, mapping):
    if isinstance(value, dict):
        return {k: remap_assets(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [remap_assets(v, mapping) for v in value]
    if isinstance(value, str):
        return re.sub(r'asset:([a-zA-Z0-9_-]+)', lambda m: mapping[m[1]], value)
    return value


def pack_page(draft, asset_bytes):
    page = validate_page(draft['kind'], draft['page'])
    relations = validate_relations(draft['kind'], draft.get('relations', []))
    files = {'page.json': json_bytes({'kind': draft['kind'], 'page': page}),
             'relations.json': json_bytes(relations),
             'editorial.json': json_bytes({'materials': draft.get('materials', {}), 'reviewed': True})}
    descriptors = []
    refs = asset_refs(page)
    if refs - set(asset_bytes):
        raise ValueError('В пакете отсутствуют используемые изображения')
    for item in draft.get('assets', []):
        if item['id'] not in refs:
            continue
        info = dict(image_info(asset_bytes[item['id']], item['filename']), id=item['id'])
        info['path'] = f"assets/{info['id']}.{info['ext']}"
        descriptors.append(info)
        files[info['path']] = asset_bytes[item['id']]
    if refs != {item['id'] for item in descriptors}:
        raise ValueError('Неизвестный ID изображения')
    digest = sha256(b''.join(json_bytes([name, sha256(raw).hexdigest()]) for name, raw in sorted(files.items()))).hexdigest()
    manifest = {'format': 'humorpedia.page-package', 'version': 1, 'entity_key': str(uuid.UUID(draft['id'])),
                'revision': draft['revision'], 'package_id': str(uuid.uuid5(uuid.UUID(draft['id']), f"{draft['revision']}:{digest}")),
                'assets': descriptors, 'files': {name: {'size': len(raw), 'sha256': sha256(raw).hexdigest()} for name, raw in files.items()}}
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json_bytes(manifest))
        for name, raw in files.items():
            archive.writestr(name, raw)
    raw = buffer.getvalue()
    if len(raw) > MAX_ZIP or sum(map(len, files.values())) > MAX_TOTAL:
        raise ValueError('Пакет превышает допустимый размер')
    return raw


def unpack_page(raw):
    if len(raw) > MAX_ZIP:
        raise ValueError('ZIP больше 50 MiB')
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            entries = archive.infolist()
            names = [i.filename for i in entries]
            if len(entries) > 100 or len(set(names)) != len(names) or sum(i.file_size for i in entries) > MAX_TOTAL:
                raise ValueError('Слишком большой архив или повторяющиеся имена')
            for item in entries:
                if item.is_dir() or '\\' in item.filename or item.filename.startswith('/') or '..' in PurePosixPath(item.filename).parts or ':' in item.filename or ((item.external_attr >> 16) & 0o170000) == 0o120000:
                    raise ValueError('Небезопасный путь в ZIP')
                if item.file_size > (MAX_IMAGE if item.filename.startswith('assets/') else 2 * 1024 * 1024):
                    raise ValueError('Файл в ZIP слишком большой')
            manifest = json.loads(archive.read('manifest.json'))
            if manifest.get('format') != 'humorpedia.page-package' or type(manifest.get('version')) is not int or manifest['version'] != 1:
                raise ValueError('Неподдерживаемая версия пакета')
            uuid.UUID(manifest['package_id'])
            uuid.UUID(manifest['entity_key'])
            if set(names) != set(manifest['files']) | {'manifest.json'}:
                raise ValueError('Состав ZIP не соответствует manifest')
            files = {}
            for name, info in manifest['files'].items():
                body = archive.read(name)
                if len(body) != info['size'] or sha256(body).hexdigest() != info['sha256']:
                    raise ValueError('Контрольная сумма файла не совпадает')
                files[name] = body
            data = json.loads(files['page.json'])
            kind = data['kind']
            page = validate_page(kind, data['page'])
            relations = validate_relations(kind, json.loads(files['relations.json']))
            editorial = json.loads(files['editorial.json'])
            assets, asset_bytes = [], {}
            for item in manifest['assets']:
                aid = item['id']
                if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', aid) or aid in asset_bytes or not item['path'].startswith('assets/'):
                    raise ValueError('Некорректное изображение в manifest')
                info = image_info(files[item['path']], item['filename'])
                if info['sha256'] != item['sha256'] or info['mime'] != item['mime']:
                    raise ValueError('Метаданные изображения не совпадают')
                assets.append(dict(info, id=aid, path=item['path']))
                asset_bytes[aid] = files[item['path']]
            if asset_refs(page) != set(asset_bytes) or set(files) != {'page.json', 'relations.json', 'editorial.json'} | {a['path'] for a in assets}:
                raise ValueError('Не хватает изображений или есть лишние файлы')
            return {'manifest': manifest, 'kind': kind, 'page': page, 'relations': relations,
                    'editorial': editorial, 'assets': assets, 'asset_bytes': asset_bytes}
    except (zipfile.BadZipFile, KeyError, TypeError, AttributeError, json.JSONDecodeError, UnicodeDecodeError, RuntimeError) as exc:
        raise ValueError('Повреждённый или неполный пакет страницы') from exc
