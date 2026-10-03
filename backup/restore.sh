#!/bin/sh
# Restore a backup created by backup.sh. Stop application writers first.
set -eu

if [ "$#" -ne 2 ] || [ "$2" != "--force" ]; then
  echo "Usage: restore.sh humorpedia_backup_YYYYMMDD_HHMMSS.tar.gz --force" >&2
  exit 2
fi

BACKUP_DIR="${BACKUP_DIR:-/backup/output}"
DB_NAME="${DB_NAME:-humorpedia}"
MONGO_HOST="${MONGO_HOST:-mongodb}"
MONGO_PORT="${MONGO_PORT:-27017}"

case "$1" in
  /*) archive="$1" ;;
  *) archive="$BACKUP_DIR/$1" ;;
esac

if [ ! -f "$archive" ]; then
  echo "Backup archive not found: $archive" >&2
  exit 1
fi

archive_name="$(basename "$archive")"
case "$archive_name" in
  humorpedia_backup_*.tar.gz) ;;
  *) echo "Unsupported backup archive: $archive_name" >&2; exit 2 ;;
esac

temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT HUP INT TERM
tar -tzf "$archive" >/dev/null
tar -xzf "$archive" -C "$temp_dir"
dump_dir="$temp_dir/${archive_name%.tar.gz}/$DB_NAME"
if [ ! -d "$dump_dir" ]; then
  echo "MongoDB dump not found in archive: $DB_NAME" >&2
  exit 1
fi

echo "Restoring $DB_NAME from $archive_name to $MONGO_HOST:$MONGO_PORT..."
if [ -n "${MONGO_USER:-}" ] && [ -n "${MONGO_PASSWORD:-}" ]; then
  mongorestore \
    --host="$MONGO_HOST" --port="$MONGO_PORT" --db="$DB_NAME" --drop \
    --username="$MONGO_USER" --password="$MONGO_PASSWORD" \
    --authenticationDatabase="${MONGO_AUTH_SOURCE:-admin}" \
    "$dump_dir"
else
  mongorestore --host="$MONGO_HOST" --port="$MONGO_PORT" --db="$DB_NAME" --drop "$dump_dir"
fi
echo "Restore completed: $archive_name"
