#!/bin/bash
# Скрипт запуска backend с автоматическим восстановлением БД

echo "Запуск backend сервера Humorpedia..."

# Восстанавливаем БД из бэкапа, если нужно
echo "Проверка необходимости восстановления БД..."
python scripts/restore_backup.py

# Запускаем сервер
echo "Запуск FastAPI сервера..."
exec "$@"

