"""
Скрипт для немедленного создания бэкапа MongoDB
Использование: python scripts/create_backup_now.py
"""
import os
import sys
from pathlib import Path

# Добавляем путь к backend для импорта модулей
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from scripts.backup_service import create_backup
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    try:
        logger.info("Запуск создания бэкапа...")
        backup_path = create_backup()
        logger.info(f"Бэкап успешно создан: {backup_path}")
        print(f"\n✓ Бэкап создан: {backup_path}")
    except Exception as e:
        logger.error(f"Ошибка при создании бэкапа: {e}", exc_info=True)
        print(f"\n✗ Ошибка при создании бэкапа: {e}")
        sys.exit(1)
