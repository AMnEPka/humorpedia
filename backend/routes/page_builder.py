"""Конструктор доступен только на явно включённом локальном стенде."""
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse, Response

from models.page_builder import DraftCreate, DraftUpdate, Revision, AcceptVersion
from services.page_builder import (ValidatedRoute, enabled, root, now, atomic_json, worker_status,
    get_draft, change_draft, public_draft, collect_result, identifier, input_facts)
from services.page_packages import seed_page, validate_page, validate_relations, image_info, pack_page, MEDIA_FIELDS, MAX_IMAGE
from utils.auth import require_editor
from utils.database import get_db


def require_local():
    if not enabled():
        raise HTTPException(404, 'Локальный конструктор отключён')


router = APIRouter(prefix='/page-builder', tags=['page-builder'], route_class=ValidatedRoute,
                   dependencies=[Depends(require_editor), Depends(require_local)])


@router.get('/drafts')
async def list_drafts():
    db = await get_db()
    items = await db.page_builder_drafts.find({}).sort('updated_at', -1).limit(100).to_list(100)
    return {'items': [public_draft(d) for d in items]}


@router.post('/drafts')
async def create_draft(data: DraftCreate, user: dict = Depends(require_editor)):
    materials = data.materials.model_dump()
    doc = {'_id': str(uuid.uuid4()), 'kind': data.kind, 'materials': materials,
           'page': seed_page(data.kind, materials), 'relations': [], 'assets': [], 'versions': [],
           'revision': 1, 'job': None, 'created_at': now(), 'updated_at': now(), 'created_by': user['_id']}
    await (await get_db()).page_builder_drafts.insert_one(doc)
    return public_draft(doc)


@router.get('/drafts/{draft_id}')
async def read_draft(draft_id: str):
    db = await get_db()
    return public_draft(await collect_result(db, await get_draft(db, draft_id)))


@router.put('/drafts/{draft_id}')
async def update_draft(draft_id: str, data: DraftUpdate):
    db = await get_db()
    doc = await get_draft(db, draft_id)
    page = validate_page(doc['kind'], data.page)
    from services.page_packages import asset_refs
    if asset_refs(page) - {a['id'] for a in doc['assets']}:
        raise ValueError('В заготовке отсутствует используемое изображение')
    return public_draft(await change_draft(db, doc, data.revision, {'materials': data.materials.model_dump(),
        'page': page, 'relations': validate_relations(doc['kind'], data.relations)}))


@router.post('/drafts/{draft_id}/assets')
async def add_asset(draft_id: str, file: UploadFile = File(...)):
    db = await get_db()
    doc = await get_draft(db, draft_id)
    if len(doc['assets']) >= 80:
        raise ValueError('Допустимо до 80 изображений')
    raw = await file.read(MAX_IMAGE + 1)
    info = dict(image_info(raw, file.filename or 'image'), id=str(uuid.uuid4()))
    path = root() / 'assets' / doc['_id'] / info['id']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    page = dict(doc['page'])
    if not page.get(MEDIA_FIELDS[doc['kind']]):
        page[MEDIA_FIELDS[doc['kind']]] = {'url': 'asset:' + info['id'], 'alt': page['title'], 'caption': ''}
    try:
        return public_draft(await change_draft(db, doc, doc['revision'], {'assets': doc['assets'] + [info], 'page': page}))
    except Exception:
        path.unlink(missing_ok=True)
        raise


@router.get('/drafts/{draft_id}/assets/{asset_id}')
async def get_asset(draft_id: str, asset_id: str):
    doc = await get_draft(await get_db(), draft_id)
    info = next((a for a in doc['assets'] if a['id'] == asset_id), None)
    if not info:
        raise HTTPException(404, 'Изображение не найдено')
    return FileResponse(root() / 'assets' / doc['_id'] / identifier(asset_id), media_type=info['mime'], headers={'Cache-Control': 'private, no-store'})


@router.post('/drafts/{draft_id}/generate')
async def generate(draft_id: str, data: Revision):
    db = await get_db()
    doc = await collect_result(db, await get_draft(db, draft_id))
    if doc.get('job') and doc['job']['status'] in {'queued', 'running'}:
        raise HTTPException(409, 'Генерация уже запущена')
    if worker_status().get('status') != 'ready':
        raise HTTPException(503, 'Запустите локальный исполнитель scripts/start-page-builder.ps1')
    job_id = str(uuid.uuid4())
    changed = await change_draft(db, doc, data.revision, {'job': {'id': job_id, 'status': 'queued'}})
    try:
        atomic_json(root() / 'jobs' / job_id / 'input.json', {'id': job_id, 'draft_id': doc['_id'],
            'input_revision': changed['revision'], 'kind': doc['kind'], 'materials': doc['materials'],
            'facts': input_facts(doc['materials']), 'page': doc['page'], 'prompt_version': 1})
    except OSError:
        await db.page_builder_drafts.update_one({'_id': doc['_id'], 'job.id': job_id}, {'$set': {
            'job.status': 'error', 'job.error': 'Не удалось записать задание в локальную очередь'}})
        raise HTTPException(503, 'Не удалось записать задание в локальную очередь')
    return public_draft(changed)


@router.post('/drafts/{draft_id}/cancel')
async def cancel(draft_id: str):
    db = await get_db()
    doc = await get_draft(db, draft_id)
    job = doc.get('job')
    if job and job['status'] in {'queued', 'running'}:
        folder = root() / 'jobs' / identifier(job['id'])
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'cancel.request').touch()
        doc = await change_draft(db, doc, doc['revision'], {'job': {**job, 'status': 'cancelled'}})
    return public_draft(doc)


@router.post('/drafts/{draft_id}/accept')
async def accept(draft_id: str, data: AcceptVersion):
    db = await get_db()
    doc = await get_draft(db, draft_id)
    version = next((v for v in doc['versions'] if v['id'] == data.version_id), None)
    if not version:
        raise HTTPException(404, 'Версия не найдена')
    if version['input_revision'] != doc['revision']:
        raise HTTPException(409, 'Исходные материалы или редакторская версия уже изменились. Соберите новое предложение.')
    return public_draft(await change_draft(db, doc, data.revision, {'page': validate_page(doc['kind'], version['page'])}))


@router.get('/drafts/{draft_id}/export')
async def export(draft_id: str, reviewed: bool = Query(False)):
    if not reviewed:
        raise ValueError('Подтвердите редакторскую проверку страницы')
    doc = await get_draft(await get_db(), draft_id)
    assets = {a['id']: (root() / 'assets' / doc['_id'] / a['id']).read_bytes() for a in doc['assets']}
    raw = pack_page({**doc, 'id': doc['_id']}, assets)
    return Response(raw, media_type='application/zip', headers={
        'Content-Disposition': f'attachment; filename="{doc["page"]["slug"]}.humorpedia.zip"', 'Cache-Control': 'private, no-store'})
