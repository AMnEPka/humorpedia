"""Закрытые заготовки и файловый обмен с исполнителем на Windows."""
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import uuid

from fastapi import HTTPException
from fastapi.routing import APIRoute
from models.page_builder import GeneratedResult
from services.page_packages import json_bytes, page_warnings, validate_page, seed_page


def now():
    return datetime.now(timezone.utc).isoformat()


def enabled():
    return os.environ.get('ENVIRONMENT') != 'production' and os.environ.get('LOCAL_PAGE_BUILDER_ENABLED', '').lower() == 'true'


def root():
    return Path(os.environ.get('PAGE_BUILDER_DIR', '/app/private/page-builder'))


def identifier(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(404, 'Запись не найдена')


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_bytes(json_bytes(value))
    os.replace(temp, path)


def read_json(path, default=None):
    try:
        if path.stat().st_size > 2 * 1024 * 1024:
            return default
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, OSError, ValueError):
        return default


def worker_status():
    status = read_json(root() / 'worker.json', {})
    try:
        recent = (datetime.now(timezone.utc) - datetime.fromisoformat(status['updated_at'].replace('Z', '+00:00'))).total_seconds() < 35
    except (KeyError, TypeError, ValueError):
        recent = False
    return status if recent else {'status': 'offline', 'error': 'Локальный исполнитель не запущен'}


class ValidatedRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def wrapped(request):
            try:
                response = await handler(request)
                response.headers['Cache-Control'] = 'private, no-store'
                return response
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        return wrapped


async def get_draft(db, draft_id):
    doc = await db.page_builder_drafts.find_one({'_id': identifier(draft_id)})
    if not doc:
        raise HTTPException(404, 'Заготовка не найдена')
    return doc


async def change_draft(db, doc, revision, changes):
    if doc['revision'] != revision:
        raise HTTPException(409, 'Заготовка изменена в другой вкладке. Обновите данные.')
    result = await db.page_builder_drafts.update_one({'_id': doc['_id'], 'revision': revision},
        {'$set': {**changes, 'revision': revision + 1, 'updated_at': now()}})
    if not result.matched_count:
        raise HTTPException(409, 'Заготовка уже изменена. Обновите данные.')
    return await get_draft(db, doc['_id'])


def public_draft(doc):
    return {**{k: v for k, v in doc.items() if k != '_id'}, 'id': doc['_id'],
            'warnings': page_warnings(doc['kind'], doc['page']), 'worker': worker_status()}


def input_facts(materials):
    result = []
    for key, value in materials.items():
        if not value:
            continue
        if key in {'notes', 'achievements'}:
            result.extend({'id': f'{key}:{i}', 'text': line.strip()} for i, line in enumerate(value.splitlines()) if line.strip())
        else:
            result.append({'id': key, 'text': value})
    return result


async def collect_result(db, doc):
    job = doc.get('job')
    if not job or job['status'] not in {'queued', 'running'}:
        return doc
    folder = root() / 'jobs' / identifier(job['id'])
    state = read_json(folder / 'status.json', {})
    status = state.get('status', job['status'])
    changes = {}
    if status == 'completed':
        try:
            data = GeneratedResult.model_validate(read_json(folder / 'result.json'))
            snapshot = read_json(folder / 'input.json')
            known = {f['id'] for f in snapshot['facts']}
            if any(set(section.fact_ids) - known for section in data.sections):
                raise ValueError('Codex сослался на неизвестные исходные факты')
            page = deepcopy(snapshot['page'])
            # Materials can be filled after creating the draft. Copy supplied structured
            # facts into the proposal while preserving fields already edited by hand.
            supplied = seed_page(doc['kind'], snapshot['materials'])
            for key, value in supplied.get('facts', {}).items():
                if not page.setdefault('facts', {}).get(key):
                    page['facts'][key] = value
            page['facts_order'] = list(dict.fromkeys([*page.get('facts_order', []), *page['facts']]))
            if doc['kind'] == 'person':
                for key, value in supplied.get('bio', {}).items():
                    if not page.setdefault('bio', {}).get(key):
                        label = {'birth_date': 'Дата рождения', 'birth_place': 'Место рождения'}.get(key)
                        page['bio'][key] = page['facts'].get(label) or value
            page['modules'] = [m for m in page.get('modules', []) if m['type'] != 'text_block']
            for section in data.sections:
                page['modules'].append({'id': str(uuid.uuid4()), 'type': 'text_block',
                    'order': len(page['modules']), 'visible': True,
                    'data': {'title': section.heading, 'content': ''.join('<p>' + escape(p) + '</p>' for p in section.paragraphs)}})
            page = validate_page(doc['kind'], page)
            version = {'id': job['id'], 'page': page, 'warnings': data.warnings, 'questions': data.questions,
                       'input_revision': snapshot['input_revision'], 'created_at': now(), 'fact_usage': [s.model_dump() for s in data.sections]}
            versions = [v for v in doc.get('versions', []) if v['id'] != job['id']]
            changes['versions'] = (versions + [version])[-10:]
        except (ValueError, KeyError, TypeError) as exc:
            status = 'error'
            state['error'] = 'Некорректный результат: ' + str(exc)[:500]
    if status not in {'queued', 'running', 'completed', 'error', 'cancelled'}:
        status = 'error'
    if status != job['status'] or changes:
        changes['job'] = {**job, 'status': status, 'error': state.get('error', '')}
        # Не меняем page и revision: предложение никак не перезаписывает редактора.
        await db.page_builder_drafts.update_one({'_id': doc['_id'], 'job.id': job['id'], 'job.status': job['status']}, {'$set': changes})
        doc = await get_draft(db, doc['_id'])
    return doc
