import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
spec=importlib.util.spec_from_file_location("gateway_ownership",Path(__file__).resolve().parents[2]/"scripts/seo/gateway_ownership.py")
guard=importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

def db(owner=True):
    result=MagicMock()
    result.name="humorpedia_html_gateway_"+"a"*32
    result.list_collection_names=AsyncMock(return_value=[])
    result.html_gateway_owner.insert_one=AsyncMock()
    result.html_gateway_owner.find_one=AsyncMock(return_value={"_id":"a"*32} if owner else None)
    result.client.drop_database=AsyncMock()
    return result

def test_foreign_name_never_mutates():
    target=db()
    target.name="humorpedia"
    with pytest.raises(RuntimeError): asyncio.run(guard.create_owner(target,"a"*32))
    with pytest.raises(RuntimeError): asyncio.run(guard.drop_owned_database(target,"a"*32))
    target.html_gateway_owner.insert_one.assert_not_called()
    target.client.drop_database.assert_not_called()

def test_nonempty_database_is_not_seeded():
    target=db()
    target.list_collection_names.return_value=["people"]
    with pytest.raises(RuntimeError): asyncio.run(guard.create_owner(target,"a"*32))
    target.html_gateway_owner.insert_one.assert_not_called()

def test_ownership_loss_never_drops_database():
    target=db(False)
    with pytest.raises(RuntimeError): asyncio.run(guard.drop_owned_database(target,"a"*32))
    target.client.drop_database.assert_not_called()
    target.html_gateway_owner.find_one.return_value={"_id":"a"*32}
    asyncio.run(guard.drop_owned_database(target,"a"*32))
    target.client.drop_database.assert_awaited_once_with(target.name)
