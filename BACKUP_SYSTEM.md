# Система бэкапа MongoDB

## Описание

Бэкапы MongoDB создаются отдельным лёгким контейнером на Alpine с `mongodump`. Без проверки по хешу — каждый запуск создаёт новый дамп и архив. Восстановление по-прежнему выполняется из контейнера backend.

## Компоненты

### 1. Контейнер бэкапа (`backup/`)

- **Образ**: Alpine + MongoDB Database Tools (только mongodump).
- **Скрипт**: `backup/backup.sh` — делает `mongodump`, упаковывает в `humorpedia_backup_YYYYMMDD_HHMMSS.tar.gz`, удаляет старые (оставляет последние 10).
- **Автозапуск**: контейнер стартует вместе с `docker compose up`, работает в фоне и делает бэкап при старте, затем раз в час (или по `BACKUP_INTERVAL`).

### 2. Восстановление (backend)

- **Скрипты**: `backend/scripts/restore_backup.py` (при старте backend при пустой БД), `backend/scripts/restore_specific_backup.py` (восстановление из выбранного файла).
- Запуск — из контейнера backend (см. ниже).

## Как запускать бэкап вручную (один раз)

По умолчанию контейнер `backup` уже крутится в фоне и бэкапит по расписанию. Чтобы сделать **одноразовый** бэкап и выйти (без фонового цикла):

```bash
docker compose run --rm -e BACKUP_INTERVAL=0 backup
```

Бэкап появится в каталоге `./backups/` в корне проекта.

### Запуск образа backup без compose (один раз)

```bash
docker run --rm \
  --network humorpedia_default \
  -e MONGO_HOST=mongodb \
  -e MONGO_PORT=27017 \
  -e MONGO_USER=humorpedia \
  -e MONGO_PASSWORD=ваш_пароль \
  -e MONGO_AUTH_SOURCE=admin \
  -e DB_NAME=humorpedia \
  -e BACKUP_DIR=/backup/output \
  -v "$(pwd)/backups:/backup/output" \
  humorpedia-backup
```

Сеть `humorpedia_default` — стандартное имя сети при `docker compose` в этой папке. Имя может отличаться (например, `humorpedia_default` или с префиксом папки). Проверить: `docker network ls`.

## Переменные окружения (контейнер backup)

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `MONGO_HOST` | `mongodb` | Хост MongoDB |
| `MONGO_PORT` | `27017` | Порт |
| `MONGO_USER` | — | Пользователь (если есть auth) |
| `MONGO_PASSWORD` | — | Пароль |
| `MONGO_AUTH_SOURCE` | `admin` | База аутентификации |
| `DB_NAME` | `humorpedia` | Имя БД |
| `BACKUP_DIR` | `/backup/output` | Каталог для архивов (в контейнере) |
| `KEEP_LAST_N` | `10` | Сколько последних бэкапов хранить |
| `BACKUP_INTERVAL` | `3600` | Интервал между бэкапами (секунды). `0` = один раз и выход (для ручного запуска) |

## Восстановление из бэкапа

Восстановление по-прежнему выполняется в контейнере backend.

**Из последнего бэкапа** (при пустой БД — автоматически при старте backend):

- Убедитесь, что нужный файл лежит в `./backups/` и backend при старте подхватит последний по имени.

**Вручную из конкретного файла**:

```bash
# Файл в ./backups/
docker exec -it humorpedia-backend python scripts/restore_specific_backup.py имя_файла.tar.gz --force

# Или полный путь в контейнере
docker exec -it humorpedia-backend python scripts/restore_specific_backup.py /app/backups/имя_файла.tar.gz --force
```

Подробнее см. `RESTORE_BACKUP.md`.

## Расписание

При `docker compose up` контейнер `backup` сам делает бэкап при старте и затем раз в `BACKUP_INTERVAL` секунд (по умолчанию 3600 = 1 час). Интервал задаётся переменной окружения `BACKUP_INTERVAL` в `docker-compose.yml`.

Если стек не крутится постоянно, можно вызывать одноразовый бэкап по cron:

```bash
0 * * * * cd /путь/к/humorpedia && docker compose run --rm -e BACKUP_INTERVAL=0 backup >> /var/log/humorpedia-backup.log 2>&1
```

## Структура бэкапа

Архив: `humorpedia_backup_YYYYMMDD_HHMMSS.tar.gz` — внутри дамп MongoDB (как от `mongodump`). Формат совместим со скриптами восстановления в backend.

## Безопасность

- Каталог `backups/` в `.gitignore` — в репозиторий не попадает.
- В бэкапах лежат все данные БД; храните каталог и логи с паролями в безопасном месте.

## Устранение неполадок

**Бэкап не создаётся**

1. Проверить, что MongoDB доступна:
   ```bash
   docker compose exec mongodb mongosh --eval "db.adminCommand('ping')"
   ```
2. Проверить логи контейнера бэкапа:
   ```bash
   docker compose run --rm backup
   ```
   (ошибки будут в выводе)
3. Права на каталог: `ls -la backups/`

**Восстановление** — см. `RESTORE_BACKUP.md`.
