"""
Скрипт для восстановления БД из конкретного файла бэкапа
Можно использовать для восстановления бэкапа с другого ПК
"""
import os
import sys
import subprocess
import tarfile
import shutil
from pathlib import Path
import argparse
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


def restore_from_backup(backup_path, force=False):
    """Восстанавливает БД из бэкапа"""
    backup_path = Path(backup_path)
    
    if not backup_path.exists():
        logger.error(f"Файл бэкапа не найден: {backup_path}")
        return False
    
    if not backup_path.name.endswith('.tar.gz'):
        logger.error(f"Файл должен быть в формате .tar.gz: {backup_path}")
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
            # Попробуем найти любую директорию внутри
            all_dirs = [d for d in extract_dir.iterdir() if d.is_dir()]
            if all_dirs:
                dump_dirs = all_dirs
            else:
                logger.error("Не найдена директория с дампом в архиве")
                return False
        
        dump_dir = dump_dirs[0] / DB_NAME
        
        # Если нет поддиректории с именем БД, используем саму директорию
        if not dump_dir.exists():
            # Проверяем, может быть дамп находится прямо в этой директории
            if (dump_dirs[0] / 'humorpedia').exists():
                dump_dir = dump_dirs[0] / 'humorpedia'
            elif any((dump_dirs[0] / f).is_dir() for f in os.listdir(dump_dirs[0])):
                # Ищем первую поддиректорию, которая может быть БД
                subdirs = [d for d in dump_dirs[0].iterdir() if d.is_dir()]
                if subdirs:
                    dump_dir = subdirs[0]
                    logger.info(f"Используем найденную директорию БД: {dump_dir}")
            else:
                logger.error(f"Директория дампа не найдена: {dump_dir}")
                logger.info(f"Содержимое архива: {list(extract_dir.rglob('*'))}")
                return False
        
        # Извлекаем хост и порт из MONGO_URL
        mongo_host = MONGO_URL.replace('mongodb://', '').split('/')[0]
        if ':' in mongo_host:
            host, port = mongo_host.split(':')
        else:
            host = mongo_host
            port = '27017'
        
        logger.info(f"Восстановление БД {DB_NAME} на хост {host}:{port}...")
        if force:
            logger.warning("⚠️  ВНИМАНИЕ: БД будет полностью перезаписана!")
        
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
        ]
        
        if force:
            cmd.append('--drop')  # Удаляем существующую БД перед восстановлением
        
        cmd.append(str(dump_dir))
        
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


def main():
    """Основная функция восстановления"""
    parser = argparse.ArgumentParser(
        description='Восстановление БД из конкретного файла бэкапа'
    )
    parser.add_argument(
        'backup_file',
        type=str,
        help='Путь к файлу бэкапа (tar.gz)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Принудительное восстановление (перезаписать существующую БД)'
    )
    
    args = parser.parse_args()
    
    logger.info("Запуск восстановления БД из бэкапа")
    logger.info(f"БД: {DB_NAME}, URL: {MONGO_URL}")
    logger.info(f"Файл бэкапа: {args.backup_file}")
    
    # Преобразуем путь к бэкапу
    backup_path = Path(args.backup_file)
    
    # Если путь относительный, проверяем в BACKUP_DIR
    if not backup_path.is_absolute():
        backup_path = BACKUP_DIR / backup_path
    
    # Если файл не найден, пробуем найти по имени в BACKUP_DIR
    if not backup_path.exists():
        potential_backup = BACKUP_DIR / args.backup_file
        if potential_backup.exists():
            backup_path = potential_backup
        else:
            logger.error(f"Файл бэкапа не найден: {args.backup_file}")
            logger.info(f"Искали в: {backup_path}")
            logger.info(f"Искали в: {potential_backup}")
            sys.exit(1)
    
    # Восстанавливаем БД
    success = restore_from_backup(backup_path, force=args.force)
    
    if success:
        logger.info("✅ Восстановление БД завершено успешно")
        sys.exit(0)
    else:
        logger.error("❌ Ошибка при восстановлении БД")
        sys.exit(1)


if __name__ == '__main__':
    main()
