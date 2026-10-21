"""Legacy-shaped editor transport with explicit canonical identities.

Sidecars are transport only, never stored in public projections or extra fields.
"""
from copy import deepcopy
import uuid
from fastapi import HTTPException
from services.competitions import legacy_to_season, season_to_legacy


def season_editor_data(season):
    data = season_to_legacy(season)
    for stage, source in zip(data.get('stages', []), season.get('stages') or []):
        stage['_canonical_id'] = source['id']
        for game, original in zip(stage.get('games', []), source.get('games') or []):
            game['_canonical_id'] = original['id']
    return data


def _select(raw, old, used, *, game=False, reserved=None):
    marker = raw.get('_canonical_id')
    if marker is not None and marker != '':
        if not isinstance(marker, str):
            raise HTTPException(422, 'Некорректный или повторный идентификатор этапа/игры')
        matches = [item for item in old if item.get('id') == marker]
        if len(matches) != 1 or marker in used:
            raise HTTPException(422, 'Некорректный или повторный идентификатор этапа/игры')
        return matches[0]
    # Older clients lack sidecars. Match only unambiguous identities; never use position.
    reserved = reserved or set()
    candidates = [item for item in old if item.get('id') not in used and item.get('id') not in reserved]
    if game and raw.get('id'):
        found = [item for item in candidates if (item.get('legacy_id') or item.get('id')) == raw['id']]
        if len(found) == 1:
            return found[0]
    found = [item for item in candidates if item.get('name', '') == raw.get('name', '')]
    return found[0] if len(found) == 1 else None



def _retain_references(refs, old_refs, all_old_refs):
    # A legacy slug is not an identity. Preserve the canonical entity for an
    # unchanged participant, including detached refs, rather than resolving again.
    output = []
    for ref in refs:
        def matching(pool):
            if ref.get('person_id'):
                return [old for old in pool if old.get('person_id') == ref['person_id']]
            if ref.get('slug'):
                return [old for old in pool if old.get('slug') == ref['slug'] and not old.get('person_id')]
            return [old for old in pool if old.get('name') == ref.get('name') and not old.get('person_id')]
        matches = matching(old_refs) or matching(all_old_refs)
        identities = {(old.get('team_id'), old.get('person_id')) for old in matches}
        if len(identities) > 1:
            raise HTTPException(422, 'Неоднозначная ссылка участника: укажите канонический ID через API сезона')
        if matches:
            original = matches[0]
            ref = {**ref, 'team_id': original.get('team_id')}
            if original.get('person_id') is not None:
                ref['person_id'] = original['person_id']
        output.append(ref)
    return output

def apply_editor_update(season, data, lookup):
    if not isinstance(data, dict) or not isinstance(data.get('stages', []), list):
        raise HTTPException(422, 'Некорректные данные редактора сезона')
    source = deepcopy(data)
    raw_stages = source.get('stages') or []
    raw_games = []
    for stage in raw_stages:
        if not isinstance(stage, dict) or not isinstance(stage.get('games', []), list):
            raise HTTPException(422, 'Некорректный этап сезона')
        games = stage.get('games') or []
        if any(not isinstance(game, dict) for game in games):
            raise HTTPException(422, 'Некорректная игра сезона')
        raw_games.append(deepcopy(games))
    raw_stages = deepcopy(raw_stages)
    # Reserve explicit identities before name/legacy fallback can match an earlier new copy.
    reserved_stage_ids = {
        stage['_canonical_id'] for stage in raw_stages
        if isinstance(stage.get('_canonical_id'), str) and stage['_canonical_id']
    }
    reserved_game_ids = {
        game['_canonical_id']
        for games in raw_games
        for game in games
        if isinstance(game.get('_canonical_id'), str) and game['_canonical_id']
    }
    for stage in source.get('stages') or []:
        stage.pop('_canonical_id', None)
        for game in stage.get('games') or []:
            game.pop('_canonical_id', None)
    page = {'_id': season.get('page_id') or season['_id'], 'title': season.get('title'),
            'slug': season.get('slug'), 'full_path': season.get('page_path'),
            'status': season.get('status'), 'season_data': source}
    tournament = {'_id': season.get('tournament_id'), 'slug': season.get('tournament_slug'),
                  'show': season.get('show'), 'participant_type': season.get('participant_type')}
    try:
        converted = legacy_to_season(page, tournament, lookup)
    except (AttributeError, TypeError, ValueError) as exc:
        raise HTTPException(422, 'Некорректные участники или результаты сезона') from exc
    result = deepcopy(season)
    all_old_refs = [*(season.get('teams') or []), *(season.get('winners') or []),
                    *(ref for stage in season.get('stages') or [] for game in stage.get('games') or [] for ref in game.get('results') or [])]
    for field in ('teams', 'winners'):
        converted[field] = _retain_references(converted[field], season.get(field) or [], all_old_refs)
    for key in ('year', 'number', 'league_name', 'intro_html', 'description', 'metadata', 'hosts', 'host',
                'editors', 'jury', 'extra_sections', 'late_joined_teams', 'teams', 'winners', 'legacy_keys', 'extra'):
        result[key] = converted[key]
    used_stages, used_games = set(), set()
    all_games = [game for stage in season.get('stages') or [] for game in stage.get('games') or []]
    stages = []
    for raw, new_stage, games in zip(raw_stages, converted['stages'], raw_games):
        original = _select(raw, season.get('stages') or [], used_stages, reserved=reserved_stage_ids)
        stage_id = original['id'] if original else str(uuid.uuid4())
        used_stages.add(stage_id)
        merged = {**deepcopy(original or {}), **new_stage, 'id': stage_id}
        merged_games = []
        for raw_game, new_game in zip(games, new_stage['games']):
            old_game = _select(raw_game, all_games, used_games, game=True, reserved=reserved_game_ids)
            game_id = old_game['id'] if old_game else str(uuid.uuid4())
            used_games.add(game_id)
            new_game['results'] = _retain_references(new_game['results'], (old_game or {}).get('results') or [], all_old_refs)
            merged_games.append({**deepcopy(old_game or {}), **new_game, 'id': game_id})
        merged['games'] = merged_games
        stages.append(merged)
    result['stages'] = stages
    return result
