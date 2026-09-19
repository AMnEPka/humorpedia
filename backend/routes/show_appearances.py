"""Публичные взаимные ссылки и ручная проверка участников шоу редактором."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from services.show_appearances import SHOW_PATHS, public_rows, public_team_projects, sync
from utils.auth import require_editor
from utils.database import get_db
from utils.search import literal_search_pattern

router = APIRouter(prefix='/show-appearances', tags=['show-appearances'])


@router.get('/people/{person_id}')
async def person_shows(person_id: str):
    return {'items': await public_rows(await get_db(), person_id=person_id)}


@router.get('/teams/{id_or_slug}/projects')
async def team_projects(id_or_slug: str):
    db = await get_db()
    team = await db.teams.find_one({
        '$or': [
            {'_id': id_or_slug},
            {'slug': id_or_slug, 'show_id': {'$in': [None, '']}},
        ],
    }, {'_id': 1, 'show_id': 1, 'status': 1})
    if not team or team.get('show_id') or team.get('status') == 'archived':
        raise HTTPException(404, 'Команда КВН не найдена')
    return {'team_id': team['_id'], 'items': await public_team_projects(db, team['_id'])}


@router.get('/review', dependencies=[Depends(require_editor)])
async def review(q: str = '', show_id: Optional[str] = None, unresolved: bool = False,
                 skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    db = await get_db()
    query = {}
    if q: query['person_name'] = {'$regex': literal_search_pattern(q), '$options': 'i'}
    if show_id: query['show_id'] = show_id
    if unresolved: query['person_id'] = None
    items = await db.show_appearances.find(query).sort([('person_name', 1), ('show_path', 1)]).skip(skip).limit(limit).to_list(limit)
    people = {p['_id']: p for p in await db.people.find({'_id': {'$in': [r.get('person_id') for r in items]}}, {'title': 1, 'slug': 1, 'status': 1}).to_list(None)}
    for item in items: item['person'] = people.get(item.get('person_id'))
    shows = await db.shows.find({'full_path': {'$in': list(SHOW_PATHS)}}, {'title': 1, 'full_path': 1}).sort('title', 1).to_list(None)
    return {'items': items, 'total': await db.show_appearances.count_documents(query), 'shows': shows}


@router.post('/sync', dependencies=[Depends(require_editor)])
async def sync_appearances():
    return await sync(await get_db(), apply=True)


class ReviewUpdate(BaseModel):
    person_id: Optional[str] = None
    preferred: Optional[bool] = None
    excluded: Optional[bool] = None
    achievement: Optional[Literal['participant', 'finalist', 'winner']] = None
    group_name: Optional[str] = Field(None, max_length=200)
    group_kind: Optional[Literal['', 'team', 'duet', 'trio', 'group']] = None


@router.patch('/review/{row_id}', dependencies=[Depends(require_editor)])
async def update_review(row_id: str, data: ReviewUpdate):
    db = await get_db()
    row = await db.show_appearances.find_one({'_id': row_id})
    if not row: raise HTTPException(404, 'Запись участия не найдена')
    changes = {}
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is None and field != 'person_id': continue
        if field == 'person_id':
            if value and not await db.people.find_one({'_id': value}): raise HTTPException(404, 'Человек не найден')
            changes.update(person_id=value, manual_person_id=value)
        elif field in ('achievement', 'group_name', 'group_kind'):
            changes['manual_' + field] = value
        else: changes[field] = value
    group_name = changes.get('manual_group_name', row.get('manual_group_name', row.get('group_name')))
    group_kind = changes.get('manual_group_kind', row.get('manual_group_kind', row.get('group_kind')))
    if bool(group_name) != bool(group_kind): raise HTTPException(422, 'Укажите одновременно вид и название состава')
    pid = changes.get('person_id', row.get('person_id'))
    if pid and 'manual_achievement' in changes:
        # Подпись относится к шоу целиком, поэтому ручной статус имеет приоритет
        # над автоматическими результатами других вариантов этого человека.
        await db.show_appearances.update_many({'show_id': row['show_id'], 'person_id': pid},
                                             {'$set': {'manual_achievement': changes['manual_achievement']}})
    if changes.get('preferred'):
        if not pid: raise HTTPException(422, 'Сначала выберите человека')
        await db.show_appearances.update_many({'show_id': row['show_id'], 'person_id': pid}, {'$set': {'preferred': False}})
    await db.show_appearances.update_one({'_id': row_id}, {'$set': changes})
    return {'ok': True}


class CreateCandidate(BaseModel):
    full_name: str = Field(min_length=3, max_length=150)
    slug: str = Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=150)


@router.post('/review/{row_id}/create-person', dependencies=[Depends(require_editor)])
async def create_candidate(row_id: str, data: CreateCandidate):
    """Только явно выбранная запись; создаётся черновик, публикация в редакторе человека."""
    db = await get_db()
    row = await db.show_appearances.find_one({'_id': row_id})
    if not row: raise HTTPException(404, 'Запись участия не найдена')
    if row.get('person_id'): raise HTTPException(409, 'Запись уже связана с человеком')
    from models.content import PersonCreate
    from routes.content_people import create_person
    # Не разрешаем создавать второй профиль по совпадающему однозначному имени.
    from services.memberships import PersonLookup
    people = await db.people.find({}, {'title': 1, 'full_name': 1, 'slug': 1}).to_list(None)
    if PersonLookup(people).resolve(name=data.full_name)[0]:
        raise HTTPException(409, 'Страница с таким именем уже есть. Выберите её через поиск.')
    result = await create_person(PersonCreate(title=data.full_name.strip(), full_name=data.full_name.strip(), slug=data.slug, status='draft'))
    await db.show_appearances.update_one({'_id': row_id}, {'$set': {'person_id': result['id'], 'manual_person_id': result['id']}})
    return result
