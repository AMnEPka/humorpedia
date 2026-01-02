#!/usr/bin/env python3
"""
Скрипт для периодического связывания городов с людьми и командами.

Использование:
    # Разовый запуск
    python link_cities.py
    
    # Через cron (каждые 30 минут)
    */30 * * * * cd /app/backend && python link_cities.py >> /var/log/link_cities.log 2>&1
    
    # Или через systemd timer
"""

import asyncio
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor.motor_asyncio import AsyncIOMotorClient
from services.city_linking import link_all_cities

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'humorpedia')


async def main():
    print(f"[{datetime.now()}] Starting city linking...")
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        result = await link_all_cities(db)
        
        print(f"[{datetime.now()}] Linking complete:")
        print(f"  Cities processed: {result['cities_processed']}")
        print(f"  Total people linked: {result['total_people_linked']}")
        print(f"  Total teams linked: {result['total_teams_linked']}")
        
        for detail in result['details']:
            if detail.get('people_count', 0) > 0 or detail.get('teams_count', 0) > 0:
                print(f"  {detail['city_name']}: {detail['people_count']} people, {detail['teams_count']} teams")
        
    finally:
        client.close()


if __name__ == '__main__':
    asyncio.run(main())
