"""
Скрипт для добавления team_type='kvn' всем командам, у которых он не указан.
Все команды в базе данных на данный момент - это команды КВН.
"""
import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient

async def fix_team_types():
    """Добавляет team_type='kvn' всем командам, у которых он не указан"""
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'humorpedia')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Находим все команды без team_type или с пустым team_type
    query = {
        "$or": [
            {"team_type": {"$exists": False}},
            {"team_type": None},
            {"team_type": ""}
        ]
    }
    
    teams_without_type = await db.teams.find(query).to_list(None)
    total = len(teams_without_type)
    
    if total == 0:
        print("Все команды уже имеют team_type. Ничего обновлять не нужно.")
        return
    
    print(f"Найдено {total} команд без team_type. Обновляем...")
    
    # Обновляем все команды
    result = await db.teams.update_many(
        query,
        {"$set": {"team_type": "kvn"}}
    )
    
    print(f"Обновлено {result.modified_count} команд. Добавлен team_type='kvn'")
    
    # Проверяем результат
    remaining = await db.teams.count_documents(query)
    if remaining > 0:
        print(f"Внимание: осталось {remaining} команд без team_type")
    else:
        print("Все команды успешно обновлены!")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(fix_team_types())
