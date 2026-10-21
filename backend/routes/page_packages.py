"""Перенос одной страницы: закрытая проверка → явное создание редактором."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from models.page_builder import ApplyPackage
from services.page_builder import ValidatedRoute, enabled
from services.page_packages import MAX_ZIP
from services.page_packages import COLLECTIONS
from services import page_package_import as service
from utils.auth import require_editor
from utils.database import get_db

router = APIRouter(prefix='/page-packages', tags=['page-packages'], route_class=ValidatedRoute,
                   dependencies=[Depends(require_editor)])
media_router = APIRouter()


@media_router.api_route('/uploads/page-packages/{entity_key}/{asset_path:path}', methods=['GET', 'HEAD'])
async def published_asset(entity_key: str, asset_path: str):
    """Before StaticFiles: staged package assets must never be public."""
    db = await get_db()
    owner = await db.page_package_entities.find_one({'_id': entity_key})
    doc = await db.page_package_imports.find_one({'_id': owner['package_id']}) if owner else None
    asset = next((a for a in doc['assets'] if asset_path == f"{a['id']}.{a['ext']}"), None) if doc else None
    target = await db[COLLECTIONS[doc['kind']]].find_one({'_id': doc['target_id']}) if asset else None
    if not asset or not (doc['status'] == 'applied' or (target and target.get('page_package_state') == 'published')):
        raise HTTPException(404, 'Изображение не найдено')
    path = service.storage() / 'published' / entity_key / asset_path
    if not path.is_file():
        raise HTTPException(404, 'Изображение не найдено')
    return FileResponse(path, media_type=asset['mime'], headers={'X-Content-Type-Options': 'nosniff'})


@router.get('/capabilities')
async def capabilities():
    return {'builder_enabled': enabled(), 'package_version': 1}


@router.post('/preview')
async def preview(file: UploadFile = File(...), user: dict = Depends(require_editor)):
    return service.wire(await service.receive(await get_db(), await file.read(MAX_ZIP + 1), user['_id']))


@router.get('/{package_id}')
async def get_package(package_id: str):
    return service.wire(await service.get_import(await get_db(), package_id))


@router.get('/{package_id}/assets/{asset_id}')
async def get_asset(package_id: str, asset_id: str):
    doc = await service.get_import(await get_db(), package_id)
    asset = next((a for a in doc['assets'] if a['id'] == asset_id), None)
    if not asset:
        raise HTTPException(404, 'Изображение не найдено')
    return FileResponse(service.storage() / doc['_id'] / asset['id'], media_type=asset['mime'], headers={'Cache-Control': 'private, no-store'})


@router.post('/{package_id}/apply')
async def apply_package(package_id: str, data: ApplyPackage, user: dict = Depends(require_editor)):
    return service.wire(await service.apply(await get_db(), package_id, data, user['_id']))
