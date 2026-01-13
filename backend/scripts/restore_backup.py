"""
Скрипт для восстановления БД из бэкапа при развертывании
"""
import os
import sys
import subprocess
import tarfile
import shutil
from pathlib import Path
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://mongodb:27017')
DB_NAME = os.environ.get('DB_NAME', 'humorpedia')
BACKUP_DIR = Path(os.environ.get('BACKUP_DIR', '/app/backups'))


def find_latest_backup():
    """Находит последний бэкап"""
    backups = sorted(
        BACKUP_DIR.glob('humorpedia_backup_*.tar.gz'),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if backups:
        return backups[0]
    return None


def restore_from_backup(backup_path):
    """Восстанавливает БД из бэкапа"""
    if not backup_path or not backup_path.exists():
        logger.error(f"Бэкап не найден: {backup_path}")
        return False
    
    extract_dir = BACKUP_DIR / 'restore_temp'
    
    try:
        logger.info(f"Распаковка бэкапа: {backup_path.name}")
        
        # Распаковываем архив
        extract_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(backup_path, 'r:gz') as tar:
            tar.extractall(extract_dir)
        
        # Находим директорию с дампом
        dump_dirs = list(extract_dir.glob('humorpedia_backup_*'))
        if not dump_dirs:
            logger.error("Не найдена директория с дампом в архиве")
            return False
        
        dump_dir = dump_dirs[0] / DB_NAME
        
        if not dump_dir.exists():
            logger.error(f"Директория дампа не найдена: {dump_dir}")
            return False
        
        # Извлекаем хост и порт из MONGO_URL
        mongo_host = MONGO_URL.replace('mongodb://', '').split('/')[0]
        if ':' in mongo_host:
            host, port = mongo_host.split(':')
        else:
            host = mongo_host
            port = '27017'
        
        logger.info(f"Восстановление БД {DB_NAME} на хост {host}:{port}...")
        
        # Ждем, пока MongoDB будет готов
        logger.info("Ожидание готовности MongoDB...")
        max_retries = 30
        for i in range(max_retries):
            try:
                cmd_test = ['mongosh', '--host', host, '--port', port, '--eval', 'db.adminCommand("ping")']
                result = subprocess.run(
                    cmd_test,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.info("MongoDB готов")
                    break
            except Exception:
                pass
            
            if i < max_retries - 1:
                import time
                time.sleep(2)
        else:
            logger.warning("MongoDB не отвечает, но продолжаем восстановление...")
        
        # Выполняем mongorestore
        cmd = [
            'mongorestore',
            '--host', host,
            '--port', port,
            '--db', DB_NAME,
            '--drop',  # Удаляем существующую БД перед восстановлением
            str(dump_dir)
        ]
        
        logger.info(f"Выполнение команды: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info("БД успешно восстановлена из бэкапа")
        logger.info(f"Вывод mongorestore:\n{result.stdout}")
        
        # Очищаем временные файлы
        shutil.rmtree(extract_dir)
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при восстановлении БД: {e.stderr}")
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        return False
    except Exception as e:
        logger.error(f"Ошибка при восстановлении БД: {e}", exc_info=True)
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        return False


def check_db_empty():
    """Проверяет, пустая ли БД"""
    try:
        from pymongo import MongoClient
        
        client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]
        
        collections = db.list_collection_names()
        total_docs = 0
        for collection_name in collections:
            count = db[collection_name].count_documents({})
            total_docs += count
        
        client.close()
        return total_docs == 0
    except Exception as e:
        logger.error(f"Ошибка при проверке БД: {e}")
        # Если не можем проверить, считаем что БД не пустая, чтобы не перезаписать данные
        return False


def main():
    """Основная функция восстановления"""
    logger.info("Запуск восстановления БД из бэкапа")
    logger.info(f"БД: {DB_NAME}, URL: {MONGO_URL}")
    logger.info(f"Директория бэкапов: {BACKUP_DIR}")
    
    # Проверяем, пустая ли БД
    if not check_db_empty():
        logger.info("БД содержит данные. Восстановление не требуется.")
        return
    
    # Проверяем наличие директории бэкапов
    if not BACKUP_DIR.exists():
        logger.warning(f"Директория бэкапов не существует: {BACKUP_DIR}")
        logger.info("Пропуск восстановления. БД будет пустой.")
        return
    
    # Находим последний бэкап
    latest_backup = find_latest_backup()
    
    if not latest_backup:
        logger.warning("Бэкапы не найдены. Пропуск восстановления.")
        return
    
    logger.info(f"Найден последний бэкап: {latest_backup.name}")
    
    # Восстанавливаем БД
    success = restore_from_backup(latest_backup)
    
    if success:
        logger.info("✅ Восстановление БД завершено успешно")
    else:
        logger.error("❌ Ошибка при восстановлении БД")
        # Не завершаем процесс с ошибкой, чтобы сервер мог запуститься даже если восстановление не удалось
        logger.warning("Продолжение запуска сервера без восстановления БД")


if __name__ == '__main__':
    main()

