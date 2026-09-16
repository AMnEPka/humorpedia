# Архитектура Humorpedia

> Снимок состояния: `main` @ `1c65fca` (PR #27, 2026-04-21). ~335 файлов в git, ~800 коммитов.
> Бэкенд ≈ 15k строк Python, фронтенд ≈ 30k строк JSX.

## 1. Общая схема

```
Браузер
  │  SPA (React 19, CRA/CRACO)
  │  dev: :3000 → прокси /api /media /images /uploads → backend:8001
  │  prod: nginx (статика билда) :3000→80; API по REACT_APP_BACKEND_URL (вшит в билд)
  ▼
FastAPI (backend/server.py) :8001
  ├── /api/*          роутеры из backend/routes/
  ├── /uploads/*      StaticFiles  ← UPLOAD_DIR (/app/uploads), загрузки через админку
  ├── /media/*        StaticFiles  ← /app/frontend/public/media (импортированные картинки MODX; монтируется только если папка есть)
  └── /images/*       StaticFiles  ← /app/images (docker volume images_volume, картинки сайта, напр. /images/kvn-team/x.jpg)
  │
  ▼
MongoDB 6 (база humorpedia), один Motor-клиент из utils/database.py
```

Middleware (порядок добавления в server.py): slowapi limiter (default 1000/мин по IP; явный лимит только на `GET /api/` — 100/мин; middleware SlowAPI не подключён, поэтому default-лимит фактически не применяется к остальным эндпоинтам) → CORS (`CORS_ORIGINS`, по умолчанию `*`) → `CacheControlMiddleware` (GET 200 вне `/auth/`, `/admin/`, `/cache/` → `public, max-age=60, stale-while-revalidate=300`).
Обработчики ошибок: `RequestValidationError` → 422 с телом запроса в ответе; любое `Exception` → 500 с текстом исключения.

### Жизненный цикл бэкенда (lifespan)
1. `get_db()` → `app.state.db`
2. `create_indexes(db)` — все индексы (уникальные `slug`/`id`, text-индексы, `kvn.full_path`, `season_data.league_slug+year` и т.д.)
3. `ensure_default_admin(db)` — `admin` / `admin@humorpedia.local` / `admin`
4. `views_counter.start(db)` — фоновая задача, раз в 30 с сбрасывает накопленные просмотры `$inc` в БД
5. на shutdown — flush счётчика, `close_db()`

## 2. Дерево репозитория

```
/
├── CLAUDE.md                     контекст для агентов (точка входа)
├── docs/ai/                      подробные справочники (этот файл и соседние)
├── README.md                     пустой шаблон
├── DOCKER_DEV.md                 запуск в Docker (dev)
├── DOCKER_VOLUME_SETUP.md        volume images_volume для /images
├── BACKUP_SYSTEM.md, RESTORE_BACKUP.md   бэкап/восстановление Mongo
├── PERFORMANCE_OPTIMIZATIONS.md  что сделано для нагрузки (lazy, text-индексы, rate limit, pool)
├── docker-compose.yml            dev: mongodb(--auth) + backend(uvicorn, без reload) + frontend(yarn start)
├── docker-compose-cloud.yml      prod: mongodb(без auth, порт 27017 наружу!) + backend(gunicorn 4×UvicornWorker) + frontend(nginx)
├── .emergent/                    метаданные платформы Emergent (прежний AI-агент), summary.txt — отчёт о рефакторинге
├── .cursor/plans/                план из Cursor (линковка контента к людям / humor_chronicles)
├── .gitconfig                    user emergent-agent-e1 (артефакт Emergent)
├── memory/test_credentials.md    admin@humorpedia.local / admin123 (данные Emergent; реальный дефолт в server.py — "admin")
├── test_result.md                протокол тестирования Emergent (служебный)
├── backend_test.py               смоук-тест живого API (берёт URL из frontend/.env)
├── mongo_unification_test.py     смоук-тест единого подключения к Mongo
├── mongo-dump.archive            12 МБ дамп Mongo (дубликат лежит в migration/)
├── 1l_kvn_games_analysis*.csv/.xlsx   выгрузка анализа игр Первой лиги
├── uploads/2025/12, 2026/01      несколько загруженных картинок
├── tests/__init__.py             пусто
│
├── backend/
│   ├── server.py                 приложение, индексы, админ по умолчанию, /api/stats, /api/random/{type}, /api/cache/stats|flush, /api/views/flush
│   ├── start.sh                  entrypoint: restore_backup.py → exec CMD
│   ├── Dockerfile                python:3.11-slim + mongodb-database-tools + mongosh; ENTRYPOINT чинит CRLF
│   ├── Dockerfile-cloud          без mongo tools, gunicorn
│   ├── requirements.txt          (много лишнего: boto3, pandas, numpy, mypy, black…)
│   ├── init_admin.py             ручное создание админа (свой MONGO_URL)
│   ├── link_cities.py            cron-скрипт: связать города с людьми/командами
│   ├── models/
│   │   ├── base.py               ContentType, TeamType, ContentStatus, SEOData, MediaFile, SocialLinks, BaseDocument, BaseContent
│   │   ├── content.py            Person, Team, Show, Article, News, Quiz, Wiki, KVN (+ *Create / *Update)
│   │   ├── modules.py            ModuleType (enum), схемы data модулей, PageModule, PageTemplate
│   │   ├── section.py            Section, SectionCreate/Update, SectionTree
│   │   ├── city.py               City (+Create/Update)
│   │   ├── user.py               User, UserRole, AuthProvider, OAuthData, TokenResponse…
│   │   └── media_browser.py      модели ответа /media/browse
│   ├── routes/
│   │   ├── auth.py               JWT (7 дней, refresh с grace 30 дней), email login/register, VK и Yandex OAuth, get_current_user()
│   │   ├── users.py              управление пользователями (require_admin / require_moderator)
│   │   ├── content_people.py     люди + /people/search + linked-content (humor_chronicles)
│   │   ├── content_teams.py      команды (1682 строки): bulk-check/create, restore-logos, refresh (self-healing), переименование slug во всех сезонах
│   │   ├── content_kvn.py        КВН (1267 строк): иерархия, by-path, children, jury-stats, соседние сезоны, update с season_data
│   │   ├── content_shows.py      шоу с иерархией (by-path, children, hierarchy)
│   │   ├── content_articles.py / content_news.py / content_quizzes.py / content_wiki.py   простой CRUD через services/crud.py
│   │   ├── content_search.py     поиск, автокомплит, по тегу, search-for-links, resolve-link, duplicate
│   │   ├── sections.py           иерархические разделы (full_path, дерево, каскадное удаление)
│   │   ├── cities.py             города + авто-связывание
│   │   ├── tags.py               теги, популярные, пересчёт usage_count
│   │   ├── comments.py           комментарии, лайки, модерация
│   │   ├── media.py              загрузка файлов, браузер volume-папок, rename/delete в источнике
│   │   ├── templates.py          шаблоны модулей, default на тип, apply-to-teams (merge модулей)
│   │   ├── redirects.py          старые URL MODX → новые (old_urls + паттерны), auto-populate
│   │   └── mongo_admin.py        сырой доступ к коллекциям: export/import/delete/aggregate/stats
│   ├── services/
│   │   ├── crud.py               check_slug_unique, generate_unique_slug, sync/check primary_tag, update_tags_everywhere, build_query, create/update/delete/get_by_id_or_slug/list_content
│   │   ├── cache.py              CacheService на cachetools.TTLCache: kvn_pages, kvn_children, teams, team_lists, redirects, search, resolved_html, breadcrumbs
│   │   ├── views_counter.py      батч-счётчик просмотров
│   │   ├── link_resolver.py      резолв внутренних ссылок в HTML модулей при выдаче
│   │   ├── linking.py            related_person_ids → страницы людей, модуль humor_chronicles
│   │   ├── tags.py               TagService.sync_tags / get_all / search
│   │   ├── city_linking.py       сопоставление городов по фактам людей/команд
│   │   ├── content.py            ContentService — НЕ используется (мёртвый код после рефакторинга)
│   │   └── link_updater.py       LinkUpdater — НЕ используется
│   ├── utils/
│   │   ├── database.py           get_db()/close_db(): MONGO_URL или MONGO_HOST/PORT/USER/PASSWORD/AUTH_SOURCE, pool 10–50
│   │   ├── slugify.py            транслитерация и slug
│   │   └── team_matcher.py       нормализация названий команд
│   └── scripts/                  разовые скрипты данных (запуск: docker compose exec backend python scripts/<file>.py)
│       ├── restore_backup.py / restore_specific_backup.py   восстановление из backups/*.tar.gz
│       ├── migrate_urls.py            обновление старых URL в контенте, поиск битых ссылок
│       ├── auto_linker.py             автопроставление ссылок по текстовым совпадениям
│       ├── migrate_images_to_volume.py  перенос картинок в imported_images_volume
│       ├── fix_kvn_2011.py, fix_kvn_seasons_league_slug.py, fix_ml_kvn_before_2014.py, check_season_2011.py   починка season_data
│       ├── fix_duplicate_modules.py, remove_manual_games_tables.py, fix_team_types.py, restore_team_logos.py   починка команд
│       ├── export_season_team_results.py, analyze_1l_kvn_games.py   выгрузки/анализ
│       └── fix_mongo_user.py          пересоздание пользователя Mongo
│
├── frontend/                     см. FRONTEND.md
│   ├── craco.config.js           алиас @, прокси dev-сервера, отключение watch в Docker, health-check плагин (ENABLE_HEALTH_CHECK)
│   ├── nginx.conf                SPA fallback, кэш статики 1y, no-store для index.html и config.js
│   ├── public/config.js          window.__BACKEND_URL__ = http://localhost:8001 для localhost
│   ├── plugins/                  health-check и visual-edits (от Emergent)
│   └── src/ …
│
├── migration/                    импорт из MODX (MySQL-дамп humorbd.sql, сам дамп не в репо)
│   ├── README.md, UNIVERSAL_IMPORTER.md
│   ├── import_people_from_sql.py основной импорт людей (--from-list --limit N --apply)
│   ├── universal_importer.py     импорт по описанию последовательности модулей
│   ├── parsers/                  парсеры HTML MODX: text, facts, timeline, gallery, members, photo, quiz, rating, social, tags, kvn_season
│   ├── kvn/                      списки страниц/команд КВН, process_seasons.py (HTML сезона → season_data), team_matcher.py, README_SEASONS.md (схема season_data)
│   ├── shows/                    импорт шоу и дочерних страниц
│   ├── *.json                    people_list, image_mapping, tag_mapping, tv_map, ratings…
│   └── прочее                    одноразовые extract_* / import_* скрипты и примеры
│
├── content/                      авторские тексты страниц КВН
│   ├── kvn-main.md, kvn-central-leagues.md, leagues/*.md   markdown с frontmatter (title, slug, full_path, meta_description, h1)
│   ├── kvn-pages-schema.json     JSON-schema страницы КВН
│   ├── OPEN_QUESTIONS.md         недостающие данные по лигам
│   └── update_kvn_pages.py       md → HTML → PUT /api/content/kvn (сохраняет системные модули, заменяет text_block); dry-run по умолчанию, --apply
│
└── backup/                       Dockerfile + backup.sh (mongodump → tar.gz, хранит 10 последних) + run-loop.sh (BACKUP_INTERVAL, по умолч. 3600 с)
                                  сервис убран из docker-compose.yml (коммит 09934cd)
```

## 3. Переменные окружения

| Переменная | Где | Назначение |
|---|---|---|
| `MONGO_URL` | backend | полный URI; если нет — собирается из `MONGO_HOST/PORT/USER/PASSWORD/AUTH_SOURCE` |
| `DB_NAME` | backend | имя БД (по умолч. `humorpedia`) |
| `JWT_SECRET` | backend | секрет JWT. **Не задан ни в одном compose** → генерируется случайно при старте процесса |
| `VK_CLIENT_ID/SECRET/REDIRECT_URI`, `YANDEX_*` | backend | OAuth |
| `CORS_ORIGINS` | backend | через запятую или `*` |
| `UPLOAD_DIR` | backend | по умолч. `/app/uploads` |
| `BACKUP_DIR` | backend | `/app/backups` |
| `MONGO_INITDB_ROOT_USERNAME/PASSWORD` | compose | учётка Mongo (дефолт `humorpedia` / `change_me_in_prod`) |
| `REACT_APP_BACKEND_URL` | frontend | URL бэкенда (в prod вшивается build-arg) |
| `REACT_APP_USE_API_PROXY` | frontend | `true` → запросы на относительный `/api` |
| `DOCKER_ENV` | frontend | `true` → отключает watch/HMR |
| `CACHEBUST` | frontend build | сброс кэша слоёв Docker |

## 4. Docker volumes

- `mongo_data` — данные Mongo
- `images_volume` → `/app/images` → URL `/images/*`
- `imported_images_volume` → `/app/media/imported/images` (в dev). ⚠ `/media` в server.py монтируется из `/app/frontend/public/media`, а не из этого пути — см. KNOWN_ISSUES
- `frontend_node_modules`, `frontend_media` (пустой, чтобы webpack не сканировал 3000+ картинок)
- prod: `uploads_data`, `backups_data`

## 5. Типовые потоки

**Открытие публичной страницы КВН** `/kvn/vl-kvn/vl-2009`:
`SectionDetailPage` (catch-all `/*`) → путь начинается с `kvn` (и не `kvn/teams`) → `GET /api/content/kvn/by-path/kvn/vl-kvn/vl-2009` (кэш 5 мин; ответ содержит `breadcrumbs` и `children`, в `season_data` дописываются `prev_season`/`next_season`); при ошибке — `GET /api/sections/path/...`. Прочие пути — сразу `sections/path`. Если у документа есть `season_data` — рендерится `SeasonDetailPage`, иначе модули + список детей. Если ничего не найдено — `GET /api/redirects/lookup?path=...` → `navigate(new_path)`.

**Редактирование сезона в админке**: `/admin/kvn/:id` → `KVNEditPage` + `SeasonDataEditor` (2665 строк, dnd-kit, ввод баллов) → `PUT /api/content/kvn/{id}` с `season_data` → очистка данных, инвалидация кэша. Обновление таблиц игр у команд — через `POST /api/content/teams/{slug}/refresh` или `/api/content/teams-refresh-all`.

**Авторизация админки**: `POST /api/auth/login` → `access_token` в `localStorage.admin_token`, пользователь в `admin_user` → axios-интерсептор добавляет `Bearer`; на 401 один раз пробует `POST /api/auth/refresh` (принимает токены, просроченные до 30 дней) → `useAuth` ещё и тихо обновляет токен каждые 6 ч. Токен удаляется только при подтверждённом 401/403, не при сетевых ошибках.

## 6. История проекта (важно для понимания кода)

- Изначально разработка шла через AI-платформу **Emergent** (коммиты `emergent-agent-e1`, `test_result.md`, `.emergent/`), частично через Cursor.
- Апрель 2026: рефакторинг Emergent — монолитный `routes/content.py` (~4300 строк) разбит на `content_*.py`, общий CRUD вынесен в `services/crud.py`, единое подключение к БД, refresh-токены, code splitting, text-индексы, rate limiting, in-memory кэш и батч-счётчик просмотров.
- В `.emergent/summary.txt` упомянуты 5 md-файлов для агентов в корне — **в репозитории их нет**; их роль теперь выполняют `CLAUDE.md` + `docs/ai/`.
- Все локальные и удалённые ветки (`debugs`, `geography`, `jury_stats`, `kvn_leagues`, `new_media`, `emergent_*`, `conflict_160426_1510`) полностью влиты в `main`.
