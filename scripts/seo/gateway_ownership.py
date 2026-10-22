"""Ownership guards shared by the native gateway wrapper and its negative tests."""
import re

def check_name(db, run_id):
    if not re.fullmatch("[a-f0-9]{32}", run_id) or db.name != "humorpedia_html_gateway_" + run_id:
        raise RuntimeError("Only an owned gateway UUID database is allowed")

async def create_owner(db, run_id):
    check_name(db, run_id)
    if await db.list_collection_names():
        raise RuntimeError("Gateway requires a new empty UUID database")
    await db.html_gateway_owner.insert_one({"_id": run_id})

async def assert_owner(db, run_id):
    check_name(db, run_id)
    if not await db.html_gateway_owner.find_one({"_id": run_id}):
        raise RuntimeError("Gateway ownership lost; refusing cleanup or mutation")

async def drop_owned_database(db, run_id):
    await assert_owner(db, run_id)
    await db.client.drop_database(db.name)
