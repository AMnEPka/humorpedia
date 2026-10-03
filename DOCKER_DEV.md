# Humorpedia — Docker (DEV)

## Prereqs
- Docker Desktop + Docker Compose plugin
- PowerShell 7 или Windows PowerShell 5.1

## Синхронизация ветки и запуск

В основной рабочей папке один раз установить автоматику:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-hooks.ps1
```

Теперь `git switch -c codex/my-feature`, `git switch <ветка>`, `git checkout` ветки и успешный локальный merge автоматически синхронизируют стенд. Checkout отдельных файлов и переключения в дополнительных worktree не затрагивают Docker. Hooks установлены только для этого репозитория, внутри `.git`; старые ветки используют установленную копию скрипта. После обновления hook-скриптов повторить установку. Отключение: `dev-hooks.ps1 -Uninstall`.

После merge PR через Codex или `gh pr merge` завершить работу командой:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-finish.ps1 -PullRequest 56
```

Подставить номер своего PR. Команда получает `origin/main`, проверяет состояние PR, base `main`, точное совпадение текущего HEAD с головой PR и включение merge-коммита в main; поддерживает также squash/rebase. Затем возвращает папку на `main`, обновляет её только fast-forward и синхронизирует Docker. Для локального merge параметр `-PullRequest` не нужен: текущий HEAD должен быть предком `origin/main`. При незакоммиченных изменениях, незавершённом merge/rebase или расхождении локального main останавливается без stash/reset/clean. Удалённый merge не вызывает локальный Git hook; Codex обязан вызвать эту команду. Ветка с несмерженными коммитами сохраняется.

Проверить, откуда работает сайт:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-status.ps1
```

Статус показывает текущую папку, ветку/HEAD, несохранённые файлы и последнюю успешную синхронизацию; проверяет хеши зависимостей/конфигурации, образы, настоящие mounts, состояние контейнеров и оба HTTP-адреса. HEAD последней синхронизации может отличаться после обычного commit: исходники подхватываются через reload/HMR. Команда не подтягивает remote и не доказывает, что все изменения уже видны в браузере; изменённый экран/API проверяется отдельно.

Для первого запуска, изменения зависимостей/конфигурации или восстановления после ошибки:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-sync.ps1
```

Скрипт пересобирает backend/frontend с Docker cache, обновляет зависимости в именованном volume `frontend_node_modules`, поднимает Compose и проверяет доступность backend/frontend. Hooks используют `-Auto`: при неизменных входных файлах и образах лишняя сборка и установка пакетов пропускаются. Если sync упал, следующий запуск выполняется полностью; ошибка видна в статусе. Две синхронизации одновременно запрещены. Ошибка hook не отменяет уже выполненный checkout/merge.

После синхронизации изменения `backend/**/*.py` применяются через Uvicorn reload, а `frontend/src/**/*` — через polling и HMR. Тесты или `yarn build` сами по себе не обновляют уже запущенный dev-сервер.

Изолированная проверка workflow (на Windows, временный Git-репозиторий и подмена внешнего Docker; рабочая база не используется): `powershell -ExecutionPolicy Bypass -File .\scripts\test-dev-workflow.ps1`.

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

Автоматический sync не меняет образ существующего MongoDB. Если старая ветка требует MongoDB 6 вместо действующей 8, hook остановится до build/stop/up: нельзя автоматически понижать версию общей базы. Проверка и подготовка обновления БД выполняются отдельно; после неё доступен ручной полный sync.

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
