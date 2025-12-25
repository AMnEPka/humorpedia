# Humorpedia — Docker (DEV)

## Prereqs
- Docker + docker-compose plugin

## Run
From repo root:
```bash
docker compose up --build
```

URLs:
- Frontend: http://localhost:3000
- Backend:  http://localhost:8001
- Mongo:    mongodb://localhost:27017

## Data persistence
Mongo uses a named volume: `mongo_data`.

## Media
Imported images are served by backend via:
- URL: `/media/imported/...`
- Mounted from: `./frontend/public/media` into backend container.

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
