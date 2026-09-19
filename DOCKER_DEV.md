# Humorpedia — Docker (DEV)

## Prereqs
- Docker Desktop + Docker Compose plugin
- PowerShell 7 или Windows PowerShell 5.1

## Синхронизация ветки и запуск

Из корня репозитория после создания, переключения или обновления ветки:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-sync.ps1
```

Скрипт пересобирает backend/frontend с Docker cache, обновляет зависимости в именованном volume `frontend_node_modules`, поднимает Compose и проверяет доступность backend/frontend. Для заведомо неизменных образов и зависимостей доступны `-SkipBuild` и `-SkipFrontendDependencies`.

После синхронизации изменения `backend/**/*.py` применяются через Uvicorn reload, а `frontend/src/**/*` — через polling и HMR. Тесты или `yarn build` сами по себе не обновляют уже запущенный dev-сервер.

Dev-образ backend включает `requirements-dev.txt`, поэтому полный локальный прогон выполняется без установки пакетов на хост:

```powershell
docker compose exec -T backend pytest -q tests
docker compose exec -T frontend yarn test --watchAll=false --runInBand
```

URLs:
- Frontend: http://localhost:3000
- Backend:  http://localhost:8001
- Mongo доступна контейнерам внутри Compose-сети и не публикуется на хост.

## Data persistence
Mongo uses a named volume: `mongo_data`.

## Media
Imported images are served by backend via:
- URL: `/media/imported/images/...`
- Mounted from: Docker volume `imported_images_volume`.

Site images (from Docker volume) are served via:
- URL: `/images/...` (e.g., `/images/kvn-team/maximum.jpg`)
- Mounted from: Docker named volume `images_volume` into backend container at `/app/images`
- On production: Mount your actual images directory to this volume

## Migration scripts
You can run migration scripts from your host (recommended) or inside backend container.

Host example:
```bash
python3 /path/to/repo/migration/import_people_from_sql.py --from-list --limit 10 --apply
```

Inside docker:
```bash
docker compose exec backend python3 /app/migration/import_people_from_sql.py --from-list --limit 10 --apply
```

Note: backend container has access to `/app/frontend/public/media` (read-only) for image serving.
