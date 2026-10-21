from copy import deepcopy
import pytest
from fastapi import HTTPException
from services.competitions import TeamLookup, legacy_to_season
from services.season_editor import season_editor_data, apply_editor_update


def fixture_season():
    page = {'_id':'p','title':'Season','slug':'s-2000','full_path':'kvn/vl/s-2000','season_data':{'year':2000,'stages':[{'name':'A','games':[{'id':'same','name':'One','teams':[{'person_id':'person','team_name':'Person'}]}]},{'name':'B','games':[{'id':'same','name':'Two'}]}]}}
    return legacy_to_season(page, {'_id':'t','slug':'vl'}, TeamLookup([]))


def test_editor_reorder_preserves_ids_unknown_fields_and_person():
    season=fixture_season()
    season['custom_canonical']={'keep':True}
    season['stages'][0]['private_extension']='keep'
    original=deepcopy(season)
    data=season_editor_data(season)
    data['stages'].reverse()
    data['stages'][1]['name']='Renamed'
    saved=apply_editor_update(season,data,TeamLookup([]))
    assert saved['custom_canonical']=={'keep':True}
    assert saved['stages'][1]['id']==season['stages'][0]['id']
    assert saved['stages'][1]['private_extension']=='keep'
    assert saved['stages'][0]['games'][0]['id']==season['stages'][1]['games'][0]['id']
    assert saved['stages'][1]['games'][0]['results'][0]['person_id']=='person'
    assert '_canonical_id' not in saved['stages'][0]['extra']
    assert season==original


def test_foreign_and_duplicate_editor_ids_are_rejected():
    season=fixture_season()
    data=season_editor_data(season)
    data['stages'][0]['_canonical_id']='foreign'
    with pytest.raises(HTTPException) as error: apply_editor_update(season,data,TeamLookup([]))
    assert error.value.status_code==422
    data=season_editor_data(season)
    data['stages'].append(deepcopy(data['stages'][0]))
    with pytest.raises(HTTPException): apply_editor_update(season,data,TeamLookup([]))


def test_new_game_has_new_identity_and_legacy_only_roundtrip_is_supported():
    season=fixture_season()
    data=season_editor_data(season)
    copied=deepcopy(data['stages'][0]['games'][0]); copied.pop('_canonical_id'); copied.pop('id')
    copied['name']='New'
    data['stages'][0]['games'].append(copied)
    saved=apply_editor_update(season,data,TeamLookup([]))
    assert saved['stages'][0]['games'][0]['id']!=saved['stages'][0]['games'][1]['id']
    from services.competitions import season_to_legacy
    data=season_to_legacy(season)
    data['description']='Changed'
    saved=apply_editor_update(season,data,TeamLookup([]))
    assert [s['id'] for s in saved['stages']]==[s['id'] for s in season['stages']]
    assert saved['description']=='Changed'

def test_editor_preserves_person_only_top_level_participants_and_winners():
    season=fixture_season()
    season['participant_type']='person'
    season['teams']=[{'person_id':'solo','team_id':None,'slug':'solo','name':'Solo','extra':{'custom':'keep'}}]
    season['winners']=deepcopy(season['teams'])
    data=season_editor_data(season)
    data['description']='Edited'
    saved=apply_editor_update(season,data,TeamLookup([]))
    assert saved['teams'][0]['person_id']=='solo'
    assert saved['winners'][0]['person_id']=='solo'
    assert saved['teams'][0]['extra']=={'custom':'keep'}

def test_editor_does_not_rebind_existing_canonical_team_when_slug_lookup_is_ambiguous():
    season=fixture_season()
    ref={'team_id':'historical-id','slug':'duplicate','name':'Historical','extra':{}}
    season['teams']=[deepcopy(ref)];season['winners']=[deepcopy(ref)]
    season['stages'][0]['games'][0]['results']=[{**deepcopy(ref),'legacy_team_id':'legacy-id'}]
    data=season_editor_data(season)
    data['description']='Text change'
    saved=apply_editor_update(season,data,TeamLookup([{'_id':'other-id','slug':'duplicate'}]))
    assert saved['teams'][0]['team_id']=='historical-id'
    assert saved['winners'][0]['team_id']=='historical-id'
    assert saved['stages'][0]['games'][0]['results'][0]['team_id']=='historical-id'


def test_new_copy_before_same_name_canonical_copy_gets_new_identity():
    season = fixture_season()
    existing_copy = deepcopy(season['stages'][0]['games'][0])
    existing_copy.update({
        'id': 'canonical-copy',
        'legacy_id': None,
        'had_legacy_id': False,
        'name': 'One (копия)',
        'extra': {'origin': 'kept'},
        'results': [{'person_id': 'person', 'team_id': None, 'name': 'Person', 'extra': {'note': 'kept'}}],
    })
    season['stages'][0]['games'].append(existing_copy)

    data = season_editor_data(season)
    existing_raw = data['stages'][0]['games'][1]
    new_copy = deepcopy(existing_raw)
    new_copy.pop('_canonical_id')
    new_copy.pop('id', None)
    data['stages'][0]['games'].insert(1, new_copy)

    saved = apply_editor_update(season, data, TeamLookup([]))
    games = saved['stages'][0]['games']
    original_game = next(game for game in games if game['name'] == 'One')
    copies = [game for game in games if game['name'] == 'One (копия)']

    assert original_game['id'] == season['stages'][0]['games'][0]['id']
    assert len(copies) == 2
    assert copies[1]['id'] == 'canonical-copy'
    assert copies[0]['id'] != 'canonical-copy'
    assert copies[1]['extra'] == {'origin': 'kept'}
    assert copies[1]['results'][0]['person_id'] == 'person'
    assert copies[1]['results'][0]['extra'] == {'note': 'kept'}


def test_new_same_name_stage_cannot_claim_a_later_explicit_stage_id():
    season = fixture_season()
    season['stages'][0]['private_extension'] = {'keep': True}
    before = deepcopy(season)
    data = season_editor_data(season)
    data['stages'].insert(0, {'name': data['stages'][0]['name'], 'games': []})

    saved = apply_editor_update(season, data, TeamLookup([]))
    assert saved['stages'][0]['id'] not in {stage['id'] for stage in season['stages']}
    assert saved['stages'][1]['id'] == season['stages'][0]['id']
    assert saved['stages'][1]['private_extension'] == {'keep': True}
    assert saved['stages'][1]['games'][0]['id'] == season['stages'][0]['games'][0]['id']
    assert season == before


@pytest.mark.parametrize('marker', ['foreign', ['foreign'], {'id': 'foreign'}])
@pytest.mark.parametrize('kind', ['stage', 'game'])
def test_invalid_sidecars_remain_422_while_reserving_ids(marker, kind):
    season = fixture_season()
    data = season_editor_data(season)
    target = data['stages'][0] if kind == 'stage' else data['stages'][0]['games'][0]
    target['_canonical_id'] = marker
    with pytest.raises(HTTPException) as error:
        apply_editor_update(season, data, TeamLookup([]))
    assert error.value.status_code == 422


def test_duplicate_explicit_game_id_is_still_rejected():
    season = fixture_season()
    data = season_editor_data(season)
    data['stages'][1]['games'].append(deepcopy(data['stages'][0]['games'][0]))
    with pytest.raises(HTTPException) as error:
        apply_editor_update(season, data, TeamLookup([]))
    assert error.value.status_code == 422
