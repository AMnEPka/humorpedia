#!/usr/bin/env python3
"""
Скрипт для пересоздания пользователя MongoDB с правильным паролем
"""
import sys
import os
from pymongo import MongoClient
from urllib.parse import quote_plus

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_mongo_user():
    """Пересоздает пользователя MongoDB с паролем из переменных окружения"""
    # Получаем переменные из окружения
    host = os.environ.get("MONGO_HOST", "localhost")
    port = int(os.environ.get("MONGO_PORT", "27017"))
    username = os.environ.get("MONGO_USER") or os.environ.get("MONGO_INITDB_ROOT_USERNAME", "humorpedia")
    password = os.environ.get("MONGO_PASSWORD") or os.environ.get("MONGO_INITDB_ROOT_PASSWORD")
    auth_source = os.environ.get("MONGO_AUTH_SOURCE", "admin")
    
    if not password:
        print("Ошибка: MONGO_PASSWORD или MONGO_INITDB_ROOT_PASSWORD не установлен")
        return False
    
    print(f"Подключение к MongoDB: {host}:{port}")
    print(f"Пользователь: {username}")
    print(f"Auth source: {auth_source}")
    
    # Пытаемся подключиться без аутентификации (если MongoDB запущен без --auth)
    try:
        client = MongoClient(f"mongodb://{host}:{port}/")
        admin_db = client.admin
        
        # Проверяем, включена ли аутентификация
        try:
            users = admin_db.command("usersInfo")
            print("MongoDB работает с аутентификацией")
            # Пытаемся подключиться с текущими учетными данными
            try:
                client_auth = MongoClient(
                    f"mongodb://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/?authSource={auth_source}"
                )
                client_auth.admin.command("ping")
                print("✓ Подключение с текущими учетными данными успешно!")
                return True
            except Exception as e:
                print(f"✗ Ошибка подключения с текущими учетными данными: {e}")
                print("Попытка пересоздать пользователя...")
                
                # Пытаемся подключиться как root (если это root пользователь)
                try:
                    # Если пользователь уже существует, удаляем его
                    try:
                        admin_db.command("dropUser", username)
                        print(f"✓ Пользователь {username} удален")
                    except Exception as e:
                        print(f"Пользователь {username} не существует или ошибка удаления: {e}")
                    
                    # Создаем пользователя заново
                    admin_db.command(
                        "createUser",
                        username,
                        pwd=password,
                        roles=["root"]
                    )
                    print(f"✓ Пользователь {username} создан с новым паролем")
                    
                    # Проверяем подключение
                    client_new = MongoClient(
                        f"mongodb://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/?authSource={auth_source}"
                    )
                    client_new.admin.command("ping")
                    print("✓ Подключение с новыми учетными данными успешно!")
                    return True
                except Exception as e:
                    print(f"✗ Ошибка при пересоздании пользователя: {e}")
                    print("\nВозможные решения:")
                    print("1. Запустите MongoDB без аутентификации временно")
                    print("2. Или используйте другой способ аутентификации")
                    return False
        except Exception:
            print("MongoDB работает без аутентификации")
            # Создаем пользователя
            try:
                # Удаляем существующего пользователя, если есть
                try:
                    admin_db.command("dropUser", username)
                    print(f"✓ Пользователь {username} удален")
                except Exception:
                    pass
                
                # Создаем пользователя
                admin_db.command(
                    "createUser",
                    username,
                    pwd=password,
                    roles=["root"]
                )
                print(f"✓ Пользователь {username} создан с паролем")
                return True
            except Exception as e:
                print(f"✗ Ошибка при создании пользователя: {e}")
                return False
    except Exception as e:
        print(f"✗ Ошибка подключения к MongoDB: {e}")
        return False
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    success = fix_mongo_user()
    sys.exit(0 if success else 1)
