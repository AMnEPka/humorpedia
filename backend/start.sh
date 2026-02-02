#!/bin/bash
# Скрипт запуска backend с автоматическим восстановлением БД
# Исправляем окончания строк на случай, если файл монтируется через volume с CRLF
SCRIPT_PATH="scripts/restore_backup.py"
SCRIPT_PATH=$(echo "$SCRIPT_PATH" | tr -d '\r')

echo "Запуск backend сервера Humorpedia..."

# Восстанавливаем БД из бэкапа, если нужно
echo "Проверка необходимости восстановления БД..."
python "$SCRIPT_PATH"

# Запускаем сервер
echo "Запуск FastAPI сервера..."
exec "$@"
