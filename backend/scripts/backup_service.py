"""
Сервис автоматического бэкапа MongoDB
Периодически проверяет изменения в БД и создает бэкапы при наличии изменений
"""
import os
import sys
import asyncio
import subprocess
import hashlib
import json
import tarfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import logging
from urllib.parse import quote_plus

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
MONGO_URL = os.environ.get('MONGO_URL')
MONGO_HOST = os.environ.get('MONGO_HOST', 'mongodb')
MONGO_PORT = os.environ.get('MONGO_PORT', '27017')
MONGO_USER = os.environ.get('MONGO_USER')
MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD')
MONGO_AUTH_SOURCE = os.environ.get('MONGO_AUTH_SOURCE', 'admin')
DB_NAME = os.environ.get('DB_NAME', 'humorpedia')
BACKUP_DIR = Path(os.environ.get('BACKUP_DIR', '/app/backups'))
CHECK_INTERVAL = int(os.environ.get('BACKUP_CHECK_INTERVAL', 3600))  # Проверка каждые 3600 секунд (1 час)
STATE_FILE = BACKUP_DIR / 'backup_state.json'

def build_mongo_url():
    if MONGO_URL:
        return MONGO_URL
    if MONGO_USER and MONGO_PASSWORD is not None:
        return f"mongodb://{quote_plus(MONGO_USER)}:{quote_plus(MONGO_PASSWORD)}@{MONGO_HOST}:{MONGO_PORT}/?authSource={MONGO_AUTH_SOURCE}"
    return f"mongodb://{MONGO_HOST}:{MONGO_PORT}"


async def get_db_hash(db):
    """Вычисляет хеш состояния БД для определения изменений"""
    collections_info = {}
    
    collections = await db.list_collection_names()
    for collection_name in collections:
        collection = db[collection_name]
        count = await collection.count_documents({})
        
        # Получаем последний документ для определения последнего изменения
        last_doc = await collection.find_one(
            sort=[("updated_at", -1)]
        ) or await collection.find_one(
            sort=[("_id", -1)]
        )
        
        last_update = None
        if last_doc:
            if 'updated_at' in last_doc:
                last_update = last_doc['updated_at']
            elif '_id' in last_doc:
                # Используем ObjectId для определения времени
                if hasattr(last_doc['_id'], 'generation_time'):
                    last_update = last_doc['_id'].generation_time.isoformat()
        
        collections_info[collection_name] = {
            'count': count,
            'last_update': last_update
        }
    
    return collections_info


def calculate_state_hash(collections_info):
    """Вычисляет хеш состояния БД"""
    state_str = json.dumps(collections_info, sort_keys=True, default=str)
    return hashlib.md5(state_str.encode()).hexdigest()


def load_backup_state():
    """Загружает состояние последнего бэкапа"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки состояния бэкапа: {e}")
    return None


def save_backup_state(state_hash, collections_info):
    """Сохраняет состояние последнего бэкапа"""
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        state = {
            'state_hash': state_hash,
            'collections_info': collections_info,
            'last_backup': datetime.now(timezone.utc).isoformat()
        }
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Ошибка сохранения состояния бэкапа: {e}")


def create_backup():
    """Создает дамп БД и архивирует его"""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    backup_name = f"humorpedia_backup_{timestamp}"
    dump_dir = BACKUP_DIR / backup_name
    archive_path = BACKUP_DIR / f"{backup_name}.tar.gz"
    
    try:
        # Создаем директорию для дампа
        dump_dir.mkdir(parents=True, exist_ok=True)
        
        host = str(MONGO_HOST)
        port = str(MONGO_PORT)
        
        logger.info(f"Создание дампа БД {DB_NAME} с хоста {host}:{port}...")
        
        # Выполняем mongodump
        cmd = [
            'mongodump',
            '--host', host,
            '--port', port,
            '--db', DB_NAME,
            '--out', str(dump_dir)
        ]

        if MONGO_USER and MONGO_PASSWORD is not None:
            cmd.extend(['--username', MONGO_USER])
            cmd.extend(['--password', MONGO_PASSWORD])
            cmd.extend(['--authenticationDatabase', MONGO_AUTH_SOURCE])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info(f"Дамп создан успешно: {dump_dir}")
        
        # Архивируем дамп
        logger.info(f"Архивирование дампа...")
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(dump_dir, arcname=backup_name)
        
        # Удаляем временную директорию
        shutil.rmtree(dump_dir)
        
        logger.info(f"Бэкап создан и заархивирован: {archive_path}")
        
        # Удаляем старые бэкапы (оставляем последние 10)
        cleanup_old_backups()
        
        return archive_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при создании дампа: {e.stderr}")
        if dump_dir.exists():
            shutil.rmtree(dump_dir)
        raise
    except Exception as e:
        logger.error(f"Ошибка при создании бэкапа: {e}")
        if dump_dir.exists():
            shutil.rmtree(dump_dir)
        raise


def cleanup_old_backups(keep_count=10):
    """Удаляет старые бэкапы, оставляя только последние N"""
    try:
        backups = sorted(
            BACKUP_DIR.glob('humorpedia_backup_*.tar.gz'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if len(backups) > keep_count:
            for old_backup in backups[keep_count:]:
                logger.info(f"Удаление старого бэкапа: {old_backup.name}")
                old_backup.unlink()
                
    except Exception as e:
        logger.error(f"Ошибка при очистке старых бэкапов: {e}")


async def check_and_backup():
    """Проверяет изменения в БД и создает бэкап при необходимости"""
    try:
        # Подключаемся к БД
        client = AsyncIOMotorClient(build_mongo_url())
        db = client[DB_NAME]
        
        # Получаем текущее состояние БД
        logger.info("Проверка изменений в БД...")
        current_collections_info = await get_db_hash(db)
        current_state_hash = calculate_state_hash(current_collections_info)
        
        # Загружаем предыдущее состояние
        previous_state = load_backup_state()
        
        if previous_state:
            previous_hash = previous_state.get('state_hash')
            
            if current_state_hash == previous_hash:
                logger.info("Изменений в БД не обнаружено. Бэкап не требуется.")
                client.close()
                return False
            else:
                logger.info("Обнаружены изменения в БД. Создание бэкапа...")
        else:
            logger.info("Предыдущее состояние не найдено. Создание первого бэкапа...")
        
        # Создаем бэкап
        backup_path = create_backup()
        
        # Сохраняем новое состояние
        save_backup_state(current_state_hash, current_collections_info)
        
        logger.info(f"Бэкап успешно создан: {backup_path}")
        
        client.close()
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при проверке и создании бэкапа: {e}", exc_info=True)
        return False


async def main():
    """Основной цикл сервиса бэкапа"""
    logger.info("Запуск сервиса автоматического бэкапа MongoDB")
    logger.info(f"БД: {DB_NAME}, host: {MONGO_HOST}:{MONGO_PORT}, authSource: {MONGO_AUTH_SOURCE}, auth: {'on' if MONGO_USER else 'off'}")
    logger.info(f"Интервал проверки: {CHECK_INTERVAL} секунд")
    logger.info(f"Директория бэкапов: {BACKUP_DIR}")
    
    # Создаем директорию для бэкапов
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Создаем первый бэкап при запуске
    logger.info("Создание начального бэкапа...")
    await check_and_backup()
    
    # Периодическая проверка
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL)
            await check_and_backup()
        except KeyboardInterrupt:
            logger.info("Остановка сервиса бэкапа...")
            break
        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {e}", exc_info=True)
            await asyncio.sleep(60)  # Ждем минуту перед следующей попыткой


if __name__ == '__main__':
    asyncio.run(main())

