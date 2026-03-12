"""Database utilities"""
from motor.motor_asyncio import AsyncIOMotorClient
import os
from urllib.parse import quote_plus

_client = None
_db = None


def _build_mongo_url_from_parts() -> str:
    host = os.environ.get("MONGO_HOST", "localhost")
    port = os.environ.get("MONGO_PORT", "27017")
    user = os.environ.get("MONGO_USER")
    password = os.environ.get("MONGO_PASSWORD")
    auth_source = os.environ.get("MONGO_AUTH_SOURCE", "admin")

    if user and password is not None:
        user_q = quote_plus(user)
        pass_q = quote_plus(password)
        # authSource is required when authenticating against admin but using a different DB
        return f"mongodb://{user_q}:{pass_q}@{host}:{port}/?authSource={auth_source}"

    return f"mongodb://{host}:{port}"


async def get_db():
    """Get database instance"""
    global _client, _db
    
    if _db is None:
        mongo_url = os.environ.get("MONGO_URL") or _build_mongo_url_from_parts()
        db_name = os.environ.get("DB_NAME", "humorpedia")
        _client = AsyncIOMotorClient(mongo_url)
        _db = _client[db_name]
    
    return _db


async def close_db():
    """Close database connection"""
    global _client
    if _client:
        _client.close()
