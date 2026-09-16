# Известные проблемы и техдолг

> Исходный список составлен при анализе `main` @ `1c65fca` (2026-09-16).
> Этап 0 (безопасность и блокирующие баги) закрыт в ветке `claude/stage0-security` — см. раздел «Исправлено».
> Исправили что-то — перенесите пункт в «Исправлено».

## 🟠 Открытые проблемы

### Переписываются в этапах 1–3 (новая модель соревнований) — отдельно не чинить
1. **Расхождение типов модулей**: фронтовый `ModuleRenderer` знает `image`, `image_gallery`, `video_embed`, `person_card`, `related_links`, `table_of_contents`, `html`, `divider`, а бэкенд `ModuleType` — нет (сохранение через API → 422); и наоборот, часть бэкенд-типов публично не рендерится.
2. **Непоследовательные идентификаторы**: у `kvn`, `teams`, `people` есть отдельное поле `id` (UUID) помимо `_id`, у импортированных `shows` поля `id` нет; `season_data.year` бывает строкой, `winners` — в двух форматах.
3. **Результаты сезонов вшиты в `kvn.season_data`**, таблица игр команды генерируется `refresh` и сохраняется в модуль; составов команд как данных нет (только текст в модуле `team_members`, `member_ids` не используется).
4. `content_teams.py` (≈1680 строк), `content_kvn.py` (≈1270), `SeasonDataEditor.jsx` (2665) — кандидаты на декомпозицию; `find_adjacent_seasons` делает десятки regex-запросов на страницу.
5. У 238 из 442 команд (дамп 12.01.2026) не заполнен `team_type` — пока API трактует отсутствие как `kvn`.

### Прочее
6. **Черновики видны публично**: GET-эндпоинты контента не фильтруют `status` для анонимов (в дампе всё `published`, поэтому не критично). Решить вместе с очередью модерации (этап 5).
7. Бинарники в git: `mongo-dump.archive` (12 МБ) дважды (корень и `migration/`), `*.docx`, `*.xlsx`, CSV-выгрузки, картинки в `uploads/`. Удаление — только с согласия владельца (дамп используется как тестовые данные).
8. Наследие Emergent: `test_result.md`, `.emergent/`, `.gitconfig` (emergent-agent), `frontend/plugins/*`, `backend_test.py` (требует `frontend/.env`), `mongo_unification_test.py`.
9. Pydantic-deprecation: class-based `Config` в `models/modules.py`, `models/section.py`; `Query(regex=...)` в `routes/tags.py`.
10. Проверки ролей внутри хендлеров `media`/`templates`/`comments` остались как второй уровень защиты — дублируют зависимости, можно убрать при рефакторинге.
11. Frontend: нет автотестов; CI проверяет только бэкенд.

## ✅ Исправлено (этап 0)

| Было | Что сделано |
|---|---|
| Write-эндпоинты контента, `/sections`, `/cities`, `/tags`, `/redirects` без авторизации | Зависимость уровня роутера `require_editor_on_write` (`backend/utils/auth.py`): чтение открыто, любая запись — admin/editor. Новые эндпоинты в этих роутерах защищены автоматически |
| `/api/mongo/*` без авторизации | `require_admin` на весь роутер |
| `media`, `templates`, `comments`, `users`, `teams/restore-logos` проверяли права после валидации тела | Зависимости в декораторах (`require_staff`/`require_editor`/`require_admin`/`require_moderator`/`require_user`) |
| `/cache/flush`, `/views/flush`, `/cache/stats` открыты | только admin |
| Админ по умолчанию `admin/admin`, пароль в логах | Удалено. Первый админ — из `ADMIN_EMAIL`/`ADMIN_PASSWORD` (≥12 символов), только если админов нет; `python init_admin.py --email … [--reset]` |
| `JWT_SECRET` случайный на процесс → 401 между воркерами и после рестарта | Читается из env; в `ENVIRONMENT=production` без секрета (≥32 символов) сервер не стартует; в dev-compose — фиксированный |
| Prod-compose: Mongo без `--auth`, порт 27017 наружу | `--auth`, порт не публикуется, backend подключается по `MONGO_USER/PASSWORD` |
| Забаненный пользователь с живым токеном проходил проверки | `get_current_user` отбрасывает `banned` и `active: false` |
| Нет лимитов на логин/регистрацию; default-лимит slowapi не работал | `SlowAPIMiddleware` подключён; `/auth/login` 20/мин, `/auth/register` 10/час; пароль при регистрации ≥8 |
| Frontend: `ProtectedRoute` пускал любого залогиненного | проверка роли admin/editor/moderator (`isStaff`) |
| 422/500 возвращали тело запроса и текст исключения | 422 без `input`, тело не логируется; в production 500 без деталей; CORS без `allow_credentials` (токен в заголовке) |
| `memory/test_credentials.md` с паролем в репо | удалён |
| `redirects.py` — свой Mongo-клиент (не работал в dev с auth) | `get_db()`; `PUT old-urls` ищет по `id` или `_id`, сбрасывает кэш редиректов |
| In-memory кэш расходился между воркерами gunicorn | «Поколение» кэша в `cache_meta`; `CacheSyncMiddleware` сверяет его перед чтением (раз в 2 с) и увеличивает после любой успешной записи |
| Просмотры не считались при попадании в кэш (`kvn/by-path`, `teams/{slug}`) | счётчик вызывается и для кэшированных ответов |
| Создание индексов прерывалось на первой ошибке (дубликаты `shows.id`) → индексы articles/news/kvn/sections/cities не создавались | каждый индекс создаётся независимо; `shows.id` — sparse |
| `/api/sections`, `/api/cities` без слэша → 404 (меню в шапке, список разделов в админке) | корневые маршруты доступны с и без слэша |
| `/media` монтировался из несуществующего в Docker пути | сначала volume `/app/media`, затем старый путь |
| `category` в `publicApi.getTeamsByCategory` игнорировался | передаётся как `team_type`; `team_type=kvn` включает команды без типа |
| `list_teams`: `search` + `letter` теряли фильтры `status/tag/team_type` | условия собираются через `$and` |
| Мёртвый код: `services/content.py`, `services/link_updater.py`, `RedirectHandler.jsx`, неполный `routes/__init__.py` | удалены / очищен |
| `requirements.txt` с лишними пакетами и дублями | только прямые зависимости; dev — `requirements-dev.txt` |
| Нет тестов и CI | `backend/tests/test_auth_guards.py` (обходит все маршруты: запись без токена → 401/403, роли), GitHub Actions `.github/workflows/tests.yml` |
| `backup/` не подключён, документация врала | сервис `backup` в `docker-compose-cloud.yml` (раз в сутки, 14 архивов), `BACKUP_SYSTEM.md` исправлен |
| Пустой README, нет шаблона env | `README.md`, `.env.example` |
