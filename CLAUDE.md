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
| [docs/ai/COMPETITIONS.md](docs/ai/COMPETITIONS.md) | **Модель соревнований и перекрёстные ссылки**: турниры, сезоны, participations, составы (memberships), синхронизация, API `/api/competitions` |
| [docs/ai/SHOW_APPEARANCES.md](docs/ai/SHOW_APPEARANCES.md) | Участие в выбранных шоу без перечисления сезонов, основной дуэт/команда, достижения, ручной выбор новых людей |
| [docs/ai/FRONTEND.md](docs/ai/FRONTEND.md) | Маршруты React, страницы, ключевые компоненты, API-клиенты |
| [docs/ai/MODULE_CONTRACT.md](docs/ai/MODULE_CONTRACT.md) | Реестр модулей, редакторы, владельцы публичного рендера и контрактные проверки |
| [docs/ai/KNOWN_ISSUES.md](docs/ai/KNOWN_ISSUES.md) | Найденные баги, дыры безопасности, техдолг |
| [docs/ai/tasks/ratings.md](docs/ai/tasks/ratings.md) | Статус восстановления рейтингов, миграция и проверки |

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
- В dev фронт ходит на `/api`, `/media`, `/images`, `/uploads` через прокси CRA (`REACT_APP_USE_API_PROXY=true`, см. `frontend/craco.config.js`). В Docker фронт не отслеживает изменения файлов вообще (`craco.config.js`: watch ignored) — после правок или `git pull`/merge нужен `docker compose restart frontend`, иначе работает старый код (как и бэкенду — `restart backend`).
- Swagger: http://localhost:8001/docs.
- При старте бэкенд создаёт индексы (каждый независимо), первого админа из `ADMIN_EMAIL`/`ADMIN_PASSWORD` (только если админов в БД нет; вручную — `python init_admin.py --email … [--reset]`) и запускает батч-счётчик просмотров. `backend/start.sh` перед стартом зовёт `scripts/restore_backup.py` (восстанавливает БД из бэкапа, если она пустая).
- Переменные окружения — шаблон `.env.example` (в корне; `.env` не коммитится). Прод (`ENVIRONMENT=production`) не стартует без `JWT_SECRET` ≥32 символов; compose-cloud требует `MONGO_INITDB_ROOT_PASSWORD`.
- Тесты: `cd backend && pytest tests` (нужны `requirements.txt` + `requirements-dev.txt`); в CI — GitHub Actions `.github/workflows/tests.yml`.

## Устройство кода (коротко)

```
backend/
  server.py           FastAPI app: lifespan (индексы, админ, views_counter), роутеры, /api/stats, /api/random, /api/cache/*, static mounts; middleware CORS → SlowAPI → CacheSync → CacheControl
  routes/             по файлу на домен; content_*.py → префикс /api/content/...
  services/crud.py    ОБЩИЙ CRUD для контента (slug, теги, primary_tag, list/get/update/delete) — использовать его, а не писать заново
  services/           cache (in-memory TTL + синхронизация между воркерами через cache_meta), views_counter (батч $inc), link_resolver, linking (связи с людьми), tags, city_linking, admin_bootstrap
  models/             Pydantic: base, content (Person/Team/Show/Article/News/Quiz/Wiki/KVN), modules (PageModule + ModuleType), section, city, user
  utils/database.py   ЕДИНСТВЕННОЕ подключение к Mongo: `db = await get_db()`. Новых клиентов не создавать
  utils/auth.py       JWT + зависимости ролей: require_user / require_staff / require_editor / require_moderator / require_admin / require_editor_on_write
  utils/rate_limit.py общий slowapi limiter
  tests/              pytest: test_auth_guards.py обходит все маршруты (запись без токена → 401/403)
  scripts/            разовые фиксы/миграции данных (запускать внутри контейнера backend)
frontend/src/
  App.js              все маршруты; публичные страницы lazy, админка lazy отдельным чанком
  public/             публичный сайт (pages, components, utils/api.js → publicApi)
  admin/              админка /admin/* (pages, components, hooks/useAuth.js, utils/api.js с refresh-интерсептором)
  components/ui/      shadcn/ui — не редактировать без нужды
migration/            импорт из MODX-дампа (people, kvn, shows), парсеры HTML, JSON-маппинги
content/              markdown-тексты страниц КВН/лиг + скрипт update_kvn_pages.py (заливка через API)
backup/               контейнер mongodump (подключён только в docker-compose-cloud.yml)
```

## Ключевые доменные правила

- **КВН — иерархия в коллекции `kvn`**: `full_path` вида `kvn/vl-kvn/vl-2009`, `parent_id` ссылается на поле **`id`** (UUID) родителя, а не всегда на `_id` — в коде везде ищут `find_one({"id": x})`, затем `{"_id": x}`. До 4 уровней вложенности.
- Лиги (slug): `vl-kvn` (Высшая), `premier-liga`, `1l-kvn` (Первая), `ml-kvn` (Международная, с 2014), `vul`. Страница сезона хранит структурированные результаты в `season_data` (стадии → игры → команды/баллы).
- **Модель соревнований** (`services/competitions.py`, см. docs/ai/COMPETITIONS.md): `tournaments` → `seasons` → `participations`. Источник истины — `seasons`; `season_data` страниц синхронизируется в обе стороны автоматически. `participations` не редактировать напрямую. Ссылка на команду — `teams._id`; в сезоне хранится название на момент сезона (переименование команды его не меняет). Команда в разных шоу — разные сущности. Шоу будет много — всё делать универсально (новое шоу = данные, не код).
- **Составы** (`services/memberships.py`): записи «человек — команда — роли — годы» импортируются из текстовых блоков «Состав команды»; человек может не иметь страницы (хранятся имя и slug старого сайта), `person_id` проставляется автоматически при создании человека. Правка записи делает её ручной. Страница команды показывает «Участие в турнирах» из participations (старый модуль «Список игр команды» больше не генерируется), страница человека — «Команды» и «В турнирах».
- **Импорт со старого сайта** — документы должны быть такими же, как сохранённые админкой (данные в полях документа, системные модули — только настройки вида, ссылки — абсолютные адреса нового сайта). Люди: `scripts/import_people_modx.py` читает SQL-дамп MODX (`backups/idemsku8_modx2.sql`) и сохраняет через `create_person`/`update_person`; все 1039 людей перенесены. Шоу — `scripts/import_shows_modx.py`, команды шоу — `scripts/import_show_teams_modx.py`, всё перенесено (DATA_MODEL.md «Шоу», «Команды шоу»): сезоны и подпроекты — дочерние шоу `/shows/<шоу>/<сезон>`. Города — `scripts/import_cities_modx.py`; список известных людей берётся только из редакционной подборки старой городской страницы и затем правится вручную, место рождения не добавляет человека автоматически. Команды КВН и шоу добавляются все по точному совпадению города и прямым ссылкам старой статьи; названия без собственной страницы остаются карточками без ссылки. Старые текстовые списки людей и команд не сохраняются. Статьи и новости — `scripts/import_articles_news_modx.py`; 66 статей и 1008 новостей перенесены, черновики и старые комментарии намеренно не импортированы. Формат и соответствие полей — DATA_MODEL.md.
- **Квизы из MODX** — `scripts/import_quizzes_modx.py` переносит опубликованные ресурсы раздела `parent=31`, `template=16`; перенесены 11 квизов и 160 вопросов, незавершённый черновик оставлен в дампе. Вложенный MIGX `answers` становится вариантами ответа, `text_success` / `text_error` сохраняются раздельно, общие `quiz_final` берутся у родительского раздела. Медиа восстанавливает `scripts/restore_quiz_media_modx.py`. Подробно — DATA_MODEL.md «Квизы».
- **Статус контента** — `draft` не ограничивает публичное использование страницы: такие документы участвуют в ссылках, поиске и связанных блоках наравне с `published`. Скрывается только `archived`.
- **Ссылки в контенте** хранятся адресами нового сайта (даже на ещё не созданные страницы); при выдаче `services/link_resolver.py` показывает ссылки на отсутствующие/архивные страницы текстом. Админка читает документы с `?raw=true` — иначе сохранение уничтожит такие ссылки. Подробно — DATA_MODEL.md «Ссылки в контенте». Картинки старого сайта (`images/...`) лежат в volume `imported_images_volume` → URL `/media/imported/images/...`.
- **«Читайте также»** строится единым `/api/recommendations`: ручной порядок `related_article_ids` у статей/новостей имеет приоритет, затем идёт детерминированный fallback по связям/тегам/популярности. Цели — только опубликованные статьи; текущая страница, дубли и битые ID исключаются.
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
- **Авторизация — только через зависимости из `utils/auth.py`**: роутер с открытым чтением и защищённой записью — `APIRouter(..., dependencies=[Depends(require_editor_on_write)])`; отдельный эндпоинт — `@router.post(..., dependencies=[Depends(require_admin)])` или параметр `user: dict = Depends(require_user)`. Проверки внутри тела хендлера срабатывают ПОСЛЕ валидации тела — не использовать. Новый публичный write-эндпоинт добавить в `PUBLIC_WRITE_ROUTES` теста осознанно.
- Роли: `admin` (всё), `editor` (контент), `moderator` (комментарии), `user` (комментарии/лайки). Доступ в админку — admin/editor/moderator.
- `backend_test.py` / `mongo_unification_test.py` — старые смоук-скрипты Emergent против живого API; `test_result.md` — служебный файл Emergent.
- Крупные бинарники в корне (`mongo-dump.archive`, `1l_kvn_games_analysis*.csv/xlsx`) — артефакты, не код.
- После существенных изменений структуры обновлять этот файл и `docs/ai/*`.
