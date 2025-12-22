"""Database utilities"""
from motor.motor_asyncio import AsyncIOMotorClient
import os

_client = None
_db = None


async def get_db():
    """Get database instance"""
    global _client, _db
    
    if _db is None:
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.environ.get('DB_NAME', 'humorpedia')
        _client = AsyncIOMotorClient(mongo_url)
        _db = _client[db_name]
    
    return _db


async def close_db():
    """Close database connection"""
    global _client
    if _client:
        _client.close()
