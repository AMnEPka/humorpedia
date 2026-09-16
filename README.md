# Humorpedia

Энциклопедия российского юмора и КВН: люди, команды, лиги и сезоны КВН, шоу, статьи, новости, квизы.

**Стек:** FastAPI + MongoDB (Motor) · React 19 (CRA/CRACO) + Tailwind/shadcn · Docker Compose.

## Быстрый старт (разработка)

```bash
cp .env.example .env            # при необходимости задайте ADMIN_EMAIL / ADMIN_PASSWORD
docker compose up --build
```

- Сайт: http://localhost:3000, админка: http://localhost:3000/admin
- API: http://localhost:8001/api, Swagger: http://localhost:8001/docs
- Первый администратор создаётся при старте из `ADMIN_EMAIL` / `ADMIN_PASSWORD`, если в БД ещё нет ни одного admin.
  Либо: `docker compose exec backend python init_admin.py --email you@example.com`

## Продакшен

```bash
cp .env.example .env            # обязательно: JWT_SECRET, MONGO_INITDB_ROOT_PASSWORD, CORS_ORIGINS, REACT_APP_BACKEND_URL
docker compose -f docker-compose-cloud.yml up -d --build
```

## Тесты

```bash
cd backend && pip install -r requirements.txt -r requirements-dev.txt && pytest tests
```

## Документация

- [CLAUDE.md](CLAUDE.md) — обзор проекта и правила работы
- [docs/ai/](docs/ai/) — архитектура, API, модель данных, фронтенд, известные проблемы
- [DOCKER_DEV.md](DOCKER_DEV.md), [BACKUP_SYSTEM.md](BACKUP_SYSTEM.md), [RESTORE_BACKUP.md](RESTORE_BACKUP.md)
