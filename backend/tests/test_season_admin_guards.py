"""Raw admin operations must not bypass the canonical season workflow."""
import asyncio
import pytest
from fastapi import HTTPException
from routes import mongo_admin


@pytest.mark.parametrize('collection',['kvn','seasons','participations'])
@pytest.mark.parametrize('operation',['import','delete'])
def test_raw_competition_write_is_rejected_before_database_access(monkeypatch,collection,operation):
    async def forbidden_db(): raise AssertionError('raw write reached database')
    monkeypatch.setattr(mongo_admin,'get_db',forbidden_db)
    request=(mongo_admin.ImportRequest(collection=collection,documents='[{"_id":"row"}]') if operation=='import'
             else mongo_admin.DeleteRequest(collection=collection,query='{"_id":"row"}'))
    action=mongo_admin.import_data if operation=='import' else mongo_admin.delete_data
    with pytest.raises(HTTPException) as error: asyncio.run(action(request))
    assert error.value.status_code==409


@pytest.mark.parametrize('pipeline',['[{"$out":"seasons"}]','[{"$lookup":{"pipeline":[{"$merge":"kvn"}]}}]'])
def test_aggregation_cannot_write_competition_collections(monkeypatch,pipeline):
    async def fake_db(): return object()
    monkeypatch.setattr(mongo_admin,'get_db',fake_db)
    with pytest.raises(HTTPException) as error:
        asyncio.run(mongo_admin.aggregate_data(mongo_admin.AggregateRequest(collection='people',pipeline=pipeline)))
    assert error.value.status_code==409
