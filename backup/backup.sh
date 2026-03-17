#!/bin/sh
# Простой бэкап MongoDB: mongodump + tar.gz. Без проверки по хешу.
# Переменные: MONGO_HOST, MONGO_PORT, MONGO_USER, MONGO_PASSWORD, MONGO_AUTH_SOURCE, DB_NAME, BACKUP_DIR, KEEP_LAST_N

set -e

BACKUP_DIR="${BACKUP_DIR:-/backup/output}"
DB_NAME="${DB_NAME:-humorpedia}"
MONGO_HOST="${MONGO_HOST:-mongodb}"
MONGO_PORT="${MONGO_PORT:-27017}"
KEEP_LAST_N="${KEEP_LAST_N:-10}"

TS=$(date -u +%Y%m%d_%H%M%S)
DUMP_DIR="${BACKUP_DIR}/humorpedia_backup_${TS}"
ARCHIVE="${BACKUP_DIR}/humorpedia_backup_${TS}.tar.gz"

mkdir -p "$BACKUP_DIR"
mkdir -p "$DUMP_DIR"

echo "Backup: dumping ${DB_NAME} from ${MONGO_HOST}:${MONGO_PORT}..."

if [ -n "$MONGO_USER" ] && [ -n "$MONGO_PASSWORD" ]; then
  mongodump \
    --host="$MONGO_HOST" \
    --port="$MONGO_PORT" \
    --db="$DB_NAME" \
    --username="$MONGO_USER" \
    --password="$MONGO_PASSWORD" \
    --authenticationDatabase="${MONGO_AUTH_SOURCE:-admin}" \
    --out="$DUMP_DIR"
else
  mongodump \
    --host="$MONGO_HOST" \
    --port="$MONGO_PORT" \
    --db="$DB_NAME" \
    --out="$DUMP_DIR"
fi

echo "Backup: archiving to $ARCHIVE..."
tar -czf "$ARCHIVE" -C "$BACKUP_DIR" "humorpedia_backup_${TS}"
rm -rf "$DUMP_DIR"
echo "Backup: created $ARCHIVE"

# Удаляем старые бэкапы, оставляем последние KEEP_LAST_N
cd "$BACKUP_DIR"
if ls humorpedia_backup_*.tar.gz 1>/dev/null 2>&1; then
  COUNT=$(ls -1 humorpedia_backup_*.tar.gz | wc -l)
  if [ "$COUNT" -gt "$KEEP_LAST_N" ]; then
    ls -1t humorpedia_backup_*.tar.gz | tail -n +$((KEEP_LAST_N + 1)) | xargs rm -f
    echo "Backup: removed old backups, kept last $KEEP_LAST_N"
  fi
fi

echo "Backup: done."
