#!/bin/sh
# Запуск бэкапов: один раз при старте, затем по интервалу (или один раз при BACKUP_INTERVAL=0).
# Переменная BACKUP_INTERVAL — секунды между бэкапами (по умолчанию 3600). 0 = только один раз и выход.

BACKUP_INTERVAL="${BACKUP_INTERVAL:-3600}"

/backup/backup.sh

if [ "$BACKUP_INTERVAL" = "0" ]; then
  exit 0
fi

echo "Backup: next run in ${BACKUP_INTERVAL}s (repeat until container stops)."
while true; do
  sleep "$BACKUP_INTERVAL"
  /backup/backup.sh
done
