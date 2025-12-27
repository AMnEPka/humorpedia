#!/usr/bin/env python3
"""Initialize default admin user.

Run once to create admin user if not exists.
Usage: python3 init_admin.py
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "emergent_db")

DEFAULT_ADMIN = {
    "username": "admin",
    "email": "admin@humorpedia.local",
    "password": "admin"
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def init_admin():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Check if admin exists
    existing = await db.users.find_one({
        "$or": [
            {"username": DEFAULT_ADMIN["username"]},
            {"email": DEFAULT_ADMIN["email"]}
        ]
    })
    
    if existing:
        print(f"Admin user already exists: {existing.get('username')} ({existing.get('email')})")
        client.close()
        return False
    
    # Create admin user
    admin_doc = {
        "_id": str(uuid4()),
        "username": DEFAULT_ADMIN["username"],
        "email": DEFAULT_ADMIN["email"],
        "password_hash": hash_password(DEFAULT_ADMIN["password"]),
        "profile": {
            "full_name": "Administrator",
            "avatar": None,
            "bio": None,
            "birth_date": None,
            "location": None
        },
        "role": "admin",
        "permissions": ["comment", "vote", "edit", "delete", "moderate", "admin"],
        "oauth": {
            "vk_id": None,
            "yandex_id": None,
            "vk_data": None,
            "yandex_data": None
        },
        "auth_provider": "email",
        "stats": {
            "articles_count": 0,
            "comments_count": 0,
            "votes_count": 0,
            "quiz_attempts": 0
        },
        "active": True,
        "verified": True,
        "banned": False,
        "old_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_login_at": None
    }
    
    await db.users.insert_one(admin_doc)
    print(f"✅ Admin user created:")
    print(f"   Username: {DEFAULT_ADMIN['username']}")
    print(f"   Email: {DEFAULT_ADMIN['email']}")
    print(f"   Password: {DEFAULT_ADMIN['password']}")
    
    client.close()
    return True


if __name__ == "__main__":
    result = asyncio.run(init_admin())
    sys.exit(0 if result else 1)
