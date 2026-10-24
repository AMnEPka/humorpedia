# Humorpedia — контекст для AI-агентов

**Отвечать пользователю на русском.**

Энциклопедия российского юмора и КВН. Переезд со старого сайта на MODX (дамп MySQL `humorbd.sql`)
на собственный стек. Репозиторий: https://github.com/AMnEPka/humorpedia, основная ветка `main`.

Подробные справочники (читать по необходимости, а не целиком):

| Файл | Что внутри |
|---|---|
| [docs/ai/ARCHITECTURE.md](docs/ai/ARCHITECTURE.md) | Дерево файлов с назначением, инфраструктура (Docker, медиа, бэкапы), потоки данных |
| [docs/ai/API.md](docs/ai/API.md) | Все эндпоинты `/api/*` по роутерам, что проверяет авторизацию |
| [docs/ai/DATA_MODEL.md](docs/ai/DATA_MODEL.md) | Коллекции MongoDB, Pydantic-модели, модули страниц, иерархия КВН, `season_data` |
| [docs/ai/COMPETITIONS.md](docs/ai/COMPETITIONS.md) | **Модель соревнований и перекрёстные ссылки**: турниры, сезоны, participations, составы (memberships), синхронизация, API `/api/competitions` |
| [docs/ai/SHOW_APPEARANCES.md](docs/ai/SHOW_APPEARANCES.md) | Участие в выбранных шоу без перечисления сезонов, основной дуэт/команда, достижения, ручной выбор новых людей |
| [docs/ai/FRONTEND.md](docs/ai/FRONTEND.md) | Маршруты React, страницы, ключевые компоненты, API-клиенты |
| [docs/ai/MODULE_CONTRACT.md](docs/ai/MODULE_CONTRACT.md) | Реестр модулей, редакторы, владельцы публичного рендера и контрактные проверки |
| [docs/ai/PAGE_BUILDER.md](docs/ai/PAGE_BUILDER.md) | Локальный конструктор через Codex CLI, редактируемые страницы и ZIP-перенос в админку |
| [docs/ai/KNOWN_ISSUES.md](docs/ai/KNOWN_ISSUES.md) | Найденные баги, дыры безопасности, техдолг |
| [docs/ai/tasks/project-refactoring-plan-2026-10-21.md](docs/ai/tasks/project-refactoring-plan-2026-10-21.md) | Аудит проекта, схема рефакторинга и план; начальный пакет исправлений F1–F3 выделен в три коммита |
| [docs/ai/tasks/initial-refactoring-fixes-2026-10-21.md](docs/ai/tasks/initial-refactoring-fixes-2026-10-21.md) | Ревью четырёх новых коммитов, исправления видимости архива / refresh / person_id, проверки и оставшиеся ограничения |
| [docs/ai/tasks/r8-canonical-seasons-2026-10-21.md](docs/ai/tasks/r8-canonical-seasons-2026-10-21.md) | R8: сверка сезонов на копии, единый путь записи, проекции и совместимость старого редактора |
| [docs/ai/tasks/r9-public-rendering-2026-10-21.md](docs/ai/tasks/r9-public-rendering-2026-10-21.md) | R9: единый выбор модулей, общий текстовый каркас, загрузка и навигация TOC в preview; приёмка 390/1120 |
| [docs/ai/tasks/r10-editor-decomposition-2026-10-21.md](docs/ai/tasks/r10-editor-decomposition-2026-10-21.md) | R10: операции и формы редакторов модулей/сезонов, сохранение JSON, браузерная приёмка; коммит 7ad0577, GitHub CI success |
| [docs/ai/tasks/r12b-pymongo-async-2026-10-22.md](docs/ai/tasks/r12b-pymongo-async-2026-10-22.md) | R12b: native PyMongo Async, async close/aggregate; коммит f97d796, GitHub CI success; 1107 backend + 2 readiness |
| [docs/ai/tasks/r12c-vite-2026-10-22.md](docs/ai/tasks/r12c-vite-2026-10-22.md) | R12c: Vite, standalone Jest, proxy/runtime config, Windows/Docker HMR; коммит 893b57e, GitHub CI success; полный dev-sync после интеграции |
| [docs/ai/tasks/r13a-search-metadata-2026-10-22.md](docs/ai/tasks/r13a-search-metadata-2026-10-22.md) | R13a: утверждённый контракт индексации/превью, origin humorpedia.ru, raw HTML baseline |
| [docs/ai/tasks/r13b-fastapi-html-pilot-plan-2026-10-22.md](docs/ai/tasks/r13b-fastapi-html-pilot-plan-2026-10-22.md) | R13b: people/articles HTML-пилот; коммит fa9342d, GitHub CI success; без production wiring |
| [docs/ai/tasks/r13c-content-readiness-2026-10-22.md](docs/ai/tasks/r13c-content-readiness-2026-10-22.md) | R13c: read-only аудит3911 документов/1107 HTML на копии; схема A HTML + React согласована, подготовлен план R13d |
| [docs/ai/tasks/r13d-html-react-pilot-plan-2026-10-22.md](docs/ai/tasks/r13d-html-react-pilot-plan-2026-10-22.md) | R13d: утверждённый и выполненный план HTML+React пилота |
| [docs/ai/tasks/r13d-html-react-pilot-acceptance-2026-10-22.md](docs/ai/tasks/r13d-html-react-pilot-acceptance-2026-10-22.md) | R13d: опубликован3b6146f + CI-fix98f37bb, GitHub39783968388 success; локальная/browsers приёмка |
| [docs/ai/tasks/r13e-html-integration-design-2026-10-22.md](docs/ai/tasks/r13e-html-integration-design-2026-10-22.md) | R13e: утверждённая схема optional native HTML + Nginx, единый release, media/crawl gates |
| [docs/ai/tasks/r13e-html-integration-plan-2026-10-22.md](docs/ai/tasks/r13e-html-integration-plan-2026-10-22.md) | R13e:7 задач выполнены; default-off, main/VPS не переключались |
| [docs/ai/tasks/r13e-html-integration-acceptance-2026-10-22.md](docs/ai/tasks/r13e-html-integration-acceptance-2026-10-22.md) | R13e: native gateway/browser/crawl приёмка и измерения; опубликован 4e94eba + CI-fix a2eeb88; повторный GitHub39826557657 completed/success, все5jobs success |
| [docs/ai/tasks/r13f-content-media-readiness-2026-10-22.md](docs/ai/tasks/r13f-content-media-readiness-2026-10-22.md) | R13f: вариант восстановления согласован; 9 оригиналов в staging, общая карточка, native HTML/JSON22 и image.decode10 PASS; опубликован02c16ca, GitHub39828202864 success |
| [docs/ai/tasks/r13g-migration-readiness-2026-10-22.md](docs/ai/tasks/r13g-migration-readiness-2026-10-22.md) | R13g: read-only25620 документов,9276 projections совпали; demo10/URL/media/связи,6 новых оригиналов в staging; опубликован467c7a6, GitHub39832700995 success; findings до исправлений данных |
| [docs/ai/tasks/r13h-media-recovery-2026-10-22.md](docs/ai/tasks/r13h-media-recovery-2026-10-22.md) | R13h:78 URL mappings/104 поля в79 docs на копии; WebP MIME fixed;1193 backend, native HTTP/React81 и media150 PASS;8 posters unresolved; опубликован7678c4b, GitHub39844032265 success |
| [docs/ai/tasks/r13i-identity-corrections-2026-10-22.md](docs/ai/tasks/r13i-identity-corrections-2026-10-22.md) | R13i:2 согласованные правки на копии приняты;25 tests,API/React4/media150 PASS,25,620 rows/остальные поля сохранены; main/VPS unchanged; опубликованef2a704, GitHub39847257115 success |
| [docs/ai/tasks/r13j-link-repair-plan-2026-10-22.md](docs/ai/tasks/r13j-link-repair-plan-2026-10-22.md) | R13j: обе части приняты на копии; quiz-fix7,88keys/759href/379docs;1200 backend,API/HTTP379+95/browser14 PASS; unresolved249; опубликован5ab9154, GitHub39914279710 success |
| [docs/ai/tasks/r13k-exact-href-plan-2026-10-23.md](docs/ai/tasks/r13k-exact-href-plan-2026-10-23.md) | R13k:102 mappings приняты на копии;782href/548fields/422docs,hidden9;unresolved147;API/HTML422+99/browser15 exact-headings PASS,cleanup/main unchanged;опубликован8ddd396,GitHub39926764123 success |
| [docs/ai/tasks/r13l-reviewed-link-plan-2026-10-23.md](docs/ai/tasks/r13l-reviewed-link-plan-2026-10-23.md) | R13l:75rules/73keys приняты на копии;319href/247fields/205docs,hidden10;resolver147→74;API/HTML205+69+2каталога/browser21 PASS,cleanup/main unchanged;опубликован1e80a34,GitHub39945508291 success |
| [docs/ai/tasks/r13m-residual-link-plan-2026-10-23.md](docs/ai/tasks/r13m-residual-link-plan-2026-10-23.md) | R13m:2href/2docs согласованы и приняты на копии;full-copy/resolver74→73/APIHTML2+2+excluded/browser2 PASS;Партизаны stored unchanged/APItext;cleanup/main unchanged,опубликованbb3221d,GitHub39966829017 success |
| [docs/ai/tasks/r13n-legacy-content-pilot-plan-2026-10-23.md](docs/ai/tasks/r13n-legacy-content-pilot-plan-2026-10-23.md) | R13n:Лампа согласована/создана на копии:1insert+parent childlist,5text/4tables/29tags;full-copy/resolver73→72/relations PASS;navigation fix согласован,367frontend+build/native4clicks PASS;принят SPA-контракт,KVN HTML/301 отдельно;опубликованaab3d5b,GitHub39974726532 success |
| [docs/ai/tasks/r13o-league-pages-plan-2026-10-23.md](docs/ai/tasks/r13o-league-pages-plan-2026-10-23.md) | R13o:9лиг реализованы на копии,12blocks/23tables/167tags/6exact ad deletes;25,630records/full-copy/resolver72→61/relations0/native27clicks PASS;final review PASS,не закоммичен |
| [docs/ai/tasks/r12a-runtime-2026-10-22.md](docs/ai/tasks/r12a-runtime-2026-10-22.md) | R12a: Node24, Gunicorn pin, signed Mongo tools; коммит 2ea75f6, GitHub CI success; полный dev-sync после интеграции |
| [docs/ai/tasks/r11-performance-2026-10-21.md](docs/ai/tasks/r11-performance-2026-10-21.md) | R11: read-only замеры на копии, соседние сезоны и индексы; коммит 857508f; приёмка p95 с контрольным разбросом, CI success после smoke fix 8aa370d |
| [docs/ai/tasks/ratings.md](docs/ai/tasks/ratings.md) | Статус восстановления рейтингов, миграция и проверки |
| [docs/ai/tasks/related-news.md](docs/ai/tasks/related-news.md) | Автоматический блок свежих связанных новостей, настройки и очистка старых вставок |
| [docs/ai/tasks/team-projects.md](docs/ai/tasks/team-projects.md) | Автоматические проекты участников команды КВН с сохранённым ручным дополнением |
| [docs/ai/tasks/correction-suggestions.md](docs/ai/tasks/correction-suggestions.md) | Публичные предложения исправлений и редакционная очередь |
| [docs/ai/tasks/editorial-research.md](docs/ai/tasks/editorial-research.md) | Ручной редакционный процесс по обновлению и созданию страниц комиков, API, админка и стартовый пакет |
| [docs/ai/tasks/source-import-24smi.md](docs/ai/tasks/source-import-24smi.md) | Импорт 24СМИ, Вокруг ТВ, GoStandup и постов ЖАБЫ: закрытая очередь, утверждение и расписание |
| [docs/ai/tasks/editorial-quotes.md](docs/ai/tasks/editorial-quotes.md) | Разовая нормализация редакционных кавычек, согласованные исключения, снимок данных и проверки |
| [docs/ai/tasks/public-user-experience-plan.md](docs/ai/tasks/public-user-experience-plan.md) | План улучшения публичного поиска, каталога команд и мобильных карточек; статус реализации |
| [docs/ai/tasks/mongodb-upgrade.md](docs/ai/tasks/mongodb-upgrade.md) | Поэтапное обновление единственного локального стенда MongoDB и проверка резервных копий |
| [docs/ai/tasks/docker-branch-sync.md](docs/ai/tasks/docker-branch-sync.md) | Автоматическая синхронизация стенда с веткой, возврат на main после PR и проверка workflow |
| [docs/ai/tasks/vps-test-deployment.md](docs/ai/tasks/vps-test-deployment.md) | Тестовый VPS с публичным HTTPS: защита, проверки и ограничения |
| [docs/deployment/vps-test-operations.md](docs/deployment/vps-test-operations.md) | Доступ к VPS, тестовый администратор, обслуживание и резервные копии |

## Стек

- **Backend**: Python 3.11, FastAPI 0.110, PyMongo Async (MongoDB), Pydantic v2, PyJWT + bcrypt, slowapi, cachetools. Точка входа `backend/server.py`.
- **Frontend**: React 19 + Vite 8.3.5, React Router 7, Tailwind + shadcn/ui (Radix), TipTap/react-quill (редакторы), dnd-kit, axios. Алиас `@` → `frontend/src`. Пакетный менеджер — **yarn**.
- **БД**: локальный Compose с MongoDB 8.0.32 и отдельная копия на тестовом VPS (04.10.2026); Mongo не опубликована наружу. База `humorpedia`: отдельная коллекция на каждый тип контента (`people`, `teams`, `kvn`, ...), документы с UUID-строкой в `_id`. Локальная и VPS-БД не синхронизируются автоматически.
- **Инфра**: `docker-compose.yml` (локальный стенд, mongo с auth, backend reload + frontend polling/HMR), `docker-compose-cloud.yml` (неиспользуемый общий шаблон); фактический малый VPS использует `scripts/vps-test/compose.yml`: gunicorn ×1, nginx, Mongo8.0.32 с отдельным seccomp-профилем, Docker-web только на loopback. Host nginx открывает `https://77.105.139.231` без общего пароля; Let's Encrypt shortlived IP-сертификат продлевает systemd timer. Старый хостинг/DNS/почта не переключены.

## Запуск

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev-hooks.ps1  # один раз в основной папке
powershell -ExecutionPolicy Bypass -File .\scripts\dev-status.ps1 # папка/ветка и состояние стенда
powershell -ExecutionPolicy Bypass -File .\scripts\dev-finish.ps1 -PullRequest <номер> # после merge PR
docker compose up -d               # повторный запуск уже синхронизированного dev-стека
```
- **Local-first обязателен**: hooks в основной папке после переключения/локального merge вызывают `scripts/dev-sync.ps1 -Auto`; при отсутствии/ошибке hooks основной агент выполняет полный sync до редактирования. После удалённого merge PR обязательно вызвать `scripts/dev-finish.ps1`. Синхронизация проверяет реальные mounts и :8001/:3000, а образы и `frontend_node_modules` обновляет при изменении входных файлов. Дополнительные worktree не управляют стендом. Подробные правила — [AGENTS.md](AGENTS.md), команды — [DOCKER_DEV.md](DOCKER_DEV.md).
- В dev фронт ходит на `/api`, `/media`, `/images`, `/uploads` через прокси Vite (`REACT_APP_USE_API_PROXY=true`, см. `frontend/vite.config.mjs`). Python-код автоматически перезапускает Uvicorn, изменения `frontend/src` пересобираются polling-наблюдателем с HMR. После правок зависимостей, Dockerfile или Compose повторить полный `dev-sync.ps1`.
- Swagger: http://localhost:8001/docs.
- При старте бэкенд создаёт индексы (каждый независимо), первого админа из `ADMIN_EMAIL`/`ADMIN_PASSWORD` (только если админов в БД нет; вручную — `python init_admin.py --email … [--reset]`) и запускает батч-счётчик просмотров. `backend/start.sh` перед стартом зовёт `scripts/restore_backup.py` (восстанавливает БД из бэкапа, если она пустая).
- Переменные окружения — шаблон `.env.example` (в корне; `.env` не коммитится). Прод (`ENVIRONMENT=production`) не стартует без `JWT_SECRET` ≥32 символов; compose-cloud требует `MONGO_INITDB_ROOT_PASSWORD`.
- Тесты локального стека: `docker compose exec -T backend pytest -q tests` и `docker compose exec -T frontend yarn test --watchAll=false --runInBand`; dev-образ backend включает `requirements-dev.txt`, production — нет. В CI — GitHub Actions `.github/workflows/tests.yml`.

## Устройство кода (коротко)

```
backend/
  server.py           FastAPI app: lifespan (индексы, админ, views_counter), роутеры, /api/stats, /api/random, /api/cache/*, static mounts; middleware CORS → SlowAPI → CacheSync → CacheControl
  routes/             по файлу на домен; content_*.py → префикс /api/content/...
  services/crud.py    ОБЩИЙ CRUD для контента (slug, теги, primary_tag, list/get/update/delete) — использовать его, а не писать заново
  services/           cache (in-memory TTL + синхронизация между воркерами через cache_meta), views_counter (батч $inc), link_resolver, related_news, tags, city_linking, admin_bootstrap
  models/             Pydantic: base, content (Person/Team/Show/Article/News/Quiz/Wiki/KVN), modules (PageModule + ModuleType), section, city, user
  utils/database.py   ЕДИНСТВЕННОЕ подключение к Mongo: `db = await get_db()`. Новых клиентов не создавать
  utils/auth.py       JWT + зависимости ролей: require_user / require_staff / require_editor / require_moderator / require_admin / require_editor_on_write
  utils/rate_limit.py общий slowapi limiter
  tests/              pytest: test_auth_guards.py обходит все маршруты (запись без токена → 401/403)
  scripts/            разовые фиксы/миграции данных (запускать внутри контейнера backend)
frontend/src/
  App.jsx              все маршруты; публичные страницы lazy, админка lazy отдельным чанком
  public/             публичный сайт (pages, components, utils/api.js → publicApi)
  admin/              админка /admin/* (pages, components, hooks/useAuth.jsx, utils/api.js с refresh-интерсептором)
  components/ui/      shadcn/ui — не редактировать без нужды
migration/            импорт из MODX-дампа (people, kvn, shows), парсеры HTML, JSON-маппинги
content/              markdown-тексты страниц КВН/лиг + скрипт update_kvn_pages.py (заливка через API)
backup/               контейнер mongodump/mongorestore (подключён только в docker-compose-cloud.yml)
```

## Ключевые доменные правила

- **КВН — иерархия в коллекции `kvn`**: `full_path` вида `kvn/vl-kvn/vl-2009`, `parent_id` ссылается на поле **`id`** (UUID) родителя, а не всегда на `_id` — в коде везде ищут `find_one({"id": x})`, затем `{"_id": x}`. До 4 уровней вложенности.
- Лиги (slug): `vl-kvn` (Высшая), `premier-liga`, `1l-kvn` (Первая), `ml-kvn` (Международная, с 2014), `vul`. Страница сезона хранит структурированные результаты в `season_data` (стадии → игры → команды/баллы).
- **Модель соревнований** (`services/competitions.py`, см. docs/ai/COMPETITIONS.md): `tournaments` → `seasons` → `participations`. Источник истины — `seasons`; `season_data` страниц синхронизируется в обе стороны автоматически. `participations` не редактировать напрямую. Ссылка на команду — `teams._id`; в сезоне хранится название на момент сезона (переименование команды его не меняет). Команда в разных шоу — разные сущности. Шоу будет много — всё делать универсально (новое шоу = данные, не код).
- **Составы** (`services/memberships.py`): записи «человек — команда — роли — годы» импортируются из текстовых блоков «Состав команды»; человек может не иметь страницы (хранятся имя и slug старого сайта). Явный slug подтверждает `person_id` автоматически, а совпадение только по имени становится кандидатом для `/admin/membership-links`; отклонение снимает ссылку, но сохраняет строку состава. Правка записи делает её ручной. Страница команды показывает «Телевизионные лиги КВН» из participations и «Участие членов команды в других проектах» обратным проходом через `show_appearances`; ручной проектный `text_block` остаётся дополнением в той же карточке. Страница человека — «Команды КВН» без сезонных плашек и «В турнирах»; команды шоу относятся в «Участие в других проектах».
- **Импорт со старого сайта** — документы должны быть такими же, как сохранённые админкой (данные в полях документа, системные модули — только настройки вида, ссылки — абсолютные адреса нового сайта). Люди: `scripts/import_people_modx.py` читает SQL-дамп MODX (`backups/idemsku8_modx2.sql`) и сохраняет через `create_person`/`update_person`; все 1039 людей перенесены. Шоу — `scripts/import_shows_modx.py`, команды шоу — `scripts/import_show_teams_modx.py`, всё перенесено (DATA_MODEL.md «Шоу», «Команды шоу»): сезоны и подпроекты — дочерние шоу `/shows/<шоу>/<сезон>`. Города — `scripts/import_cities_modx.py`; список известных людей берётся только из редакционной подборки старой городской страницы и затем правится вручную, место рождения не добавляет человека автоматически. Команды КВН и шоу добавляются все по точному совпадению города и прямым ссылкам старой статьи; названия без собственной страницы остаются карточками без ссылки. Старые текстовые списки людей и команд не сохраняются. Статьи и новости — `scripts/import_articles_news_modx.py`; 66 статей и 1008 новостей перенесены, черновики и старые комментарии намеренно не импортированы. Формат и соответствие полей — DATA_MODEL.md.
- **Квизы из MODX** — `scripts/import_quizzes_modx.py` переносит опубликованные ресурсы раздела `parent=31`, `template=16`; перенесены 11 квизов и 160 вопросов, незавершённый черновик оставлен в дампе. Вложенный MIGX `answers` становится вариантами ответа, `text_success` / `text_error` сохраняются раздельно, общие `quiz_final` берутся у родительского раздела. Медиа восстанавливает `scripts/restore_quiz_media_modx.py`. Подробно — DATA_MODEL.md «Квизы».
- **Статус контента** — `draft` не ограничивает публичное использование страницы: такие документы участвуют в ссылках, поиске и связанных блоках наравне с `published`. Скрывается только `archived`.
- **Ссылки в контенте** хранятся адресами нового сайта (даже на ещё не созданные страницы); при выдаче `services/link_resolver.py` показывает ссылки на отсутствующие/архивные страницы текстом. Админка читает документы с `?raw=true` — иначе сохранение уничтожит такие ссылки. Подробно — DATA_MODEL.md «Ссылки в контенте». Картинки старого сайта (`images/...`) лежат в volume `imported_images_volume` → URL `/media/imported/images/...`.
- **«Читайте также»** строится единым `/api/recommendations`: при включённом типе «Статьи» ручной порядок `related_article_ids` у статей/новостей имеет приоритет. Автоматическая часть исключает внутренние URL, уже присутствующие в данных страницы; для команд также учитываются структурированные составы, проекты участников и турниры. Затем случайно выбираются связанные карточки по прямым связям/общим тегам, а одно место резервируется под находку из остального пула; порядок стабилен в течение московских суток. Глобальные настройки лежат в `site_settings._id=recommendations` и доступны admin на `/admin/related-content`: лимит, типы результатов и типы страниц показа. По умолчанию участвуют статьи, люди, команды КВН/шоу, шоу, города, KVN-страницы и квизы; новости доступны, но выключены. Скрывается только `archived`; текущая страница, дубли и битые ID исключаются.
- **«Свежие новости»** — отдельный динамический блок после первого контентного блока людей, команд КВН, команд шоу и шоу. Источник — только явные `news.related_person_ids/related_team_ids/related_show_ids`; глобальные настройки лежат в `site_settings._id=related_news`, доступны admin на `/admin/related-news`, максимум — 3 записи. Старый `humor_chronicles` удалён.
- **Опросы**: определения в `polls`, новые голоса в `poll_votes` (детерминированный `_id=poll:user`, один голос). Модуль страницы `poll` хранит только `poll_id`; публичный результат складывает новые записи и анонимные `historical_votes`. Голос требует существующий JWT и permission `vote`; публичные login/register пока в бэклоге. Старый дамп проверяется/импортируется `scripts/import_polls_modx.py`, по умолчанию это dry-run.
- **Рейтинги**: для статьи, человека, команды и шоу работают независимо от `rating_widget`. Старые агрегаты перенесены в `rating_baselines`, новые анонимные оценки — в `rating_votes`; один подписанный cookie-посетитель имеет один изменяемый голос на страницу. Публичный API отдаёт среднее и только веху количества, без точного счётчика.
- **Изображения-заглушки** — четыре исходника `backups/images/pattern/{1..4}.jpg` при старте backend копируются в `imported_images_volume`. `frontend/src/utils/media.js` выбирает вариант стабильно по slug/id и использует его для отсутствующих или недоступных изображений карточек и страниц. Не сохранять букву/иконку как отдельную заглушку и не возвращать старые URL `pattern-N.jpeg`.
- **Страницы команд** — `/kvn/teams/:slug`, коллекция `teams`. Команды шоу — там же, с `show_id`, адрес `/shows/{шоу}/teams/{slug}` (`services/show_teams.py`: адрес только через `team_url`, поиск по одному slug — только команды КВН). Модуль «Список игр команды» генерируется автоматически из `season_data` всех сезонов (`/content/teams/{slug}/refresh`, `teams-refresh-all`), вручную его не править.
- Публичный catch-all `/*` → `SectionDetailPage`: пробует `kvn/by-path`, затем `sections/path`, затем `redirects/lookup` (старые URL MODX в поле `old_urls`).
- Контент страниц собирается из **модулей** (`modules: [{id, type, order, title, visible, data}]`). Системные модули (sidebar): `poster_photo`, `facts_table`, `tags_cloud`, `social_links`, `rating_widget`. Шаблоны модулей — коллекция `templates`.
- `primary_tag` — основной тег сущности; автоматически добавляется в `tags`, должен быть уникален.
- Кэш: любая успешная запись в `/api` (кроме auth/comments/views/cache/polls/ratings) сбрасывает кэш во всех воркерах (middleware `CacheSyncMiddleware`); после правок напрямую в БД — `POST /api/cache/flush` (admin).

## Правила работы

- Весь UI, комментарии и сообщения об ошибках в коде — на русском (так принято в проекте).
- Новые роуты: брать `get_db()` из `utils.database`, CRUD — через `services/crud.py`, регистрировать роутер в `server.py` (порядок важен: специфичные пути раньше общих). Корневой маршрут роутера объявлять и как `""`, и как `"/"` (`redirect_slashes=False`).
- Создание людей, команд и шоу — `services/content_commands.py` с явным `db`; routes сохраняют совместимые обёртки. ZIP и редакционные предложения вызывают доменные операции напрямую. В новых workflow передавать `db` также в CRUD/tag helpers; их необязательный параметр сохраняет старые вызовы.
- **Авторизация — только через зависимости из `utils/auth.py`**: роутер с открытым чтением и защищённой записью — `APIRouter(..., dependencies=[Depends(require_editor_on_write)])`; отдельный эндпоинт — `@router.post(..., dependencies=[Depends(require_admin)])` или параметр `user: dict = Depends(require_user)`. Проверки внутри тела хендлера срабатывают ПОСЛЕ валидации тела — не использовать. Новый публичный write-эндпоинт добавить в `PUBLIC_WRITE_ROUTES` теста осознанно.
- Роли: `admin` (всё), `editor` (контент), `moderator` (комментарии), `user` (комментарии/лайки). Доступ в админку — admin/editor/moderator.
- После существенных изменений структуры обновлять этот файл и `docs/ai/*`.
