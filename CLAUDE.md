# Humorpedia — контекст для AI-агентов

**Отвечать пользователю на русском.**

Энциклопедия российского юмора и КВН (прод: https://humorpedia.ru). Переезд со старого сайта на MODX (дамп MySQL `humorbd.sql`)
на собственный стек. Репозиторий: https://github.com/AMnEPka/humorpedia, основная ветка `main`.

Подробные справочники (читать по необходимости, а не целиком):

| Файл | Что внутри |
|---|---|
| [docs/ai/ARCHITECTURE.md](docs/ai/ARCHITECTURE.md) | Дерево файлов с назначением, инфраструктура (Docker, медиа, бэкапы), потоки данных |
| [docs/ai/API.md](docs/ai/API.md) | Все эндпоинты `/api/*` по роутерам, что проверяет авторизацию |
| [docs/ai/DATA_MODEL.md](docs/ai/DATA_MODEL.md) | Коллекции MongoDB, Pydantic-модели, модули страниц, иерархия КВН, `season_data` |
| [docs/ai/FRONTEND.md](docs/ai/FRONTEND.md) | Маршруты React, страницы, ключевые компоненты, API-клиенты |
| [docs/ai/KNOWN_ISSUES.md](docs/ai/KNOWN_ISSUES.md) | Найденные баги, дыры безопасности, техдолг |

## Стек

- **Backend**: Python 3.11, FastAPI 0.110, Motor (async MongoDB), Pydantic v2, PyJWT + bcrypt, slowapi, cachetools. Точка входа `backend/server.py`.
- **Frontend**: React 19 + CRA через CRACO, React Router 7, Tailwind + shadcn/ui (Radix), TipTap/react-quill (редакторы), dnd-kit, axios. Алиас `@` → `frontend/src`. Пакетный менеджер — **yarn**.
- **БД**: MongoDB 6, база `humorpedia`. Отдельная коллекция на каждый тип контента (`people`, `teams`, `kvn`, ...), документы с UUID-строкой в `_id`.
- **Инфра**: `docker-compose.yml` (dev, mongo с auth, hot reload выключен), `docker-compose-cloud.yml` (прод: gunicorn ×4 воркера, nginx-статика фронта).

## Запуск

```bash
docker compose up --build          # dev: фронт :3000, бэк :8001, mongo внутри сети
docker compose restart backend     # после правок Python (reload выключен)
```
- В dev фронт ходит на `/api`, `/media`, `/images`, `/uploads` через прокси CRA (`REACT_APP_USE_API_PROXY=true`, см. `frontend/craco.config.js`). В Docker hot reload фронта тоже выключен — обновлять страницу вручную.
- Swagger: http://localhost:8001/docs.
- При старте бэкенд создаёт индексы, админа по умолчанию (`admin` / `admin@humorpedia.local` / пароль `admin`) и запускает батч-счётчик просмотров. `backend/start.sh` перед стартом зовёт `scripts/restore_backup.py` (восстанавливает БД из бэкапа, если она пустая).
- `.env` файлов в репозитории нет (в `.gitignore`); конфигурация через env в compose.

## Устройство кода (коротко)

```
backend/
  server.py           FastAPI app: lifespan (индексы, админ, views_counter), подключение роутеров, /api/stats, /api/random, /api/cache/*, static mounts, CORS, Cache-Control
  routes/             по файлу на домен; content_*.py → префикс /api/content/...
  services/crud.py    ОБЩИЙ CRUD для контента (slug, теги, primary_tag, list/get/update/delete) — использовать его, а не писать заново
  services/           cache (in-memory TTL), views_counter (батч $inc), link_resolver (резолв внутренних ссылок в HTML модулей), linking (связи с людьми), tags, city_linking
  models/             Pydantic: base, content (Person/Team/Show/Article/News/Quiz/Wiki/KVN), modules (PageModule + ModuleType), section, city, user
  utils/database.py   ЕДИНСТВЕННОЕ подключение к Mongo: `db = await get_db()`. Новых клиентов не создавать
  scripts/            разовые фиксы/миграции данных (запускать внутри контейнера backend)
frontend/src/
  App.js              все маршруты; публичные страницы lazy, админка lazy отдельным чанком
  public/             публичный сайт (pages, components, utils/api.js → publicApi)
  admin/              админка /admin/* (pages, components, hooks/useAuth.js, utils/api.js с refresh-интерсептором)
  components/ui/      shadcn/ui — не редактировать без нужды
migration/            импорт из MODX-дампа (people, kvn, shows), парсеры HTML, JSON-маппинги
content/              markdown-тексты страниц КВН/лиг + скрипт update_kvn_pages.py (заливка через API)
backup/               контейнер mongodump (сейчас не подключён в docker-compose.yml)
```

## Ключевые доменные правила

- **КВН — иерархия в коллекции `kvn`**: `full_path` вида `kvn/vl-kvn/vl-2009`, `parent_id` ссылается на поле **`id`** (UUID) родителя, а не всегда на `_id` — в коде везде ищут `find_one({"id": x})`, затем `{"_id": x}`. До 4 уровней вложенности.
- Лиги (slug): `vl-kvn` (Высшая), `premier-liga`, `1l-kvn` (Первая), `ml-kvn` (Международная, с 2014), `vul`. Страница сезона хранит структурированные результаты в `season_data` (стадии → игры → команды/баллы).
- **Страницы команд** — `/kvn/teams/:slug`, коллекция `teams`. Модуль «Список игр команды» генерируется автоматически из `season_data` всех сезонов (`/content/teams/{slug}/refresh`, `teams-refresh-all`), вручную его не править.
- Публичный catch-all `/*` → `SectionDetailPage`: пробует `kvn/by-path`, затем `sections/path`, затем `redirects/lookup` (старые URL MODX в поле `old_urls`).
- Контент страниц собирается из **модулей** (`modules: [{id, type, order, title, visible, data}]`). Системные модули (sidebar): `poster_photo`, `facts_table`, `tags_cloud`, `social_links`, `rating_widget`. Шаблоны модулей — коллекция `templates`.
- `primary_tag` — основной тег сущности; автоматически добавляется в `tags`, должен быть уникален.
- Кэш: после записи через API нужные ключи инвалидируются; после массовых правок напрямую в БД — `POST /api/cache/flush`.

## Правила работы

- Весь UI, комментарии и сообщения об ошибках в коде — на русском (так принято в проекте).
- Новые роуты: брать `get_db()` из `utils.database`, CRUD — через `services/crud.py`, регистрировать роутер в `server.py` (порядок важен: специфичные пути раньше общих).
- Авторизация сейчас проверяется вручную внутри хендлеров (`get_current_user(request)` из `routes/auth.py`, `require_admin` в `routes/users.py`); большинство write-эндпоинтов контента **не защищены** — см. KNOWN_ISSUES.
- Тестов как таковых нет: `backend_test.py` / `mongo_unification_test.py` — смоук-скрипты против живого API; `test_result.md` — служебный файл прежнего агента Emergent.
- Крупные бинарники в корне (`mongo-dump.archive`, `1l_kvn_games_analysis*.csv/xlsx`) — артефакты, не код.
- После существенных изменений структуры обновлять этот файл и `docs/ai/*`.
