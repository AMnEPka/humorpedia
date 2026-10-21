"""All source content remains editor-only until the explicit approve command."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ValidationError

from utils.auth import require_editor
from utils.database import get_db
from models.editorial_import import ImportURLs, ScanRequest, ImportEdit, ImportDecision, ImportSettings, SourceId
from services import editorial_imports as service
from services import source_import_scheduler as scheduler

router = APIRouter(prefix='/editorial-imports', tags=['editorial-imports'], dependencies=[Depends(require_editor)])


def actor(user):
    return str(user.get('_id') or user.get('id') or 'editor')


@router.get('')
async def list_items(response: Response, kind: str | None = Query(None, pattern='^(biography|news)$'),
        status: str | None = Query(None, pattern='^(pending|accepted|rejected|conflict|publishing)$'),
        source_id: SourceId | None = None,
        skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    response.headers['Cache-Control'] = 'private, no-store'
    db = await get_db()
    query = {key: value for key, value in {'kind': kind, 'status': status, 'source_id': source_id}.items() if value}
    items = await db.editorial_imports.find(query, {'lease_token': 0}).sort('updated_at', -1).skip(skip).limit(limit).to_list(limit)
    return {'items': items, 'total': await db.editorial_imports.count_documents(query)}


@router.get('/settings')
async def get_settings(response: Response, source_id: SourceId = '24smi'):
    response.headers['Cache-Control'] = 'private, no-store'
    return await scheduler.settings(await get_db(), source_id)


@router.put('/settings')
async def set_settings(data: ImportSettings):
    return await scheduler.save_settings(await get_db(), data)


@router.post('/import')
async def import_materials(data: ImportURLs, user: dict = Depends(require_editor)):
    try:
        return await service.import_urls(await get_db(), data.urls, actor(user))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/scan', status_code=202)
async def scan(data: ScanRequest, user: dict = Depends(require_editor)):
    return {'started': await scheduler.start_scan(await get_db(), data.days, data.limit, actor(user), source_id=data.source_id)}


@router.patch('/{item_id}')
async def edit(item_id: str, data: ImportEdit, user: dict = Depends(require_editor)):
    return await service.edit_item(await get_db(), item_id, data, actor(user))


@router.post('/{item_id}/approve')
async def approve(item_id: str, data: ImportDecision, user: dict = Depends(require_editor)):
    try:
        return await service.approve_item(await get_db(), item_id, data.revision, actor(user))
    except ValidationError as exc:
        raise HTTPException(422, 'Проверьте заполнение полей материала: ' + str(exc)[:500]) from exc


@router.post('/{item_id}/reject')
async def reject(item_id: str, data: ImportDecision, user: dict = Depends(require_editor)):
    return await service.reject_item(await get_db(), item_id, data.revision, actor(user))
