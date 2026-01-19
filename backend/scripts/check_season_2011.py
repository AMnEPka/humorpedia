#!/usr/bin/env python3
"""Проверка структуры season_data для сезона 2011"""

import os
import pymongo

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://mongodb:27017')
DB_NAME = os.environ.get('DB_NAME', 'humorpedia')

client = pymongo.MongoClient(MONGO_URL)
db = client[DB_NAME]

doc = db.kvn.find_one({'_id': '056c1c06-1d0b-45ee-9572-0a3701ca128b'})
if not doc:
    print("Документ не найден")
    exit(1)

season_data = doc.get('season_data', {})
print(f"league_slug: {season_data.get('league_slug')}")
print(f"year: {season_data.get('year')}")
print(f"stages count: {len(season_data.get('stages', []))}")

stages = season_data.get('stages', [])
for i, stage in enumerate(stages[:5]):
    games = stage.get('games', [])
    print(f"  Stage {i+1}: {stage.get('name')} - {len(games)} games")
    for j, game in enumerate(games[:2]):
        jury = game.get('jury', [])
        print(f"    Game {j+1}: {game.get('name')} - jury: {len(jury)} members")
        if jury:
            print(f"      Jury: {jury[:3]}")

client.close()
