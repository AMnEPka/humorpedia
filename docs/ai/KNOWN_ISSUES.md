# Известные проблемы и техдолг

> Найдено при анализе кода `main` @ `1c65fca` (2026-09-16). Ничего из списка пока не исправлено.
> Исправили что-то — удалите пункт или отметьте его.

## 🔴 Безопасность (критично)

1. **Нет авторизации на write-эндпоинтах контента.** `POST/PUT/DELETE` для `/api/content/{people,teams,kvn,shows,articles,news,quizzes,wiki}`, `/content/{type}/{id}/duplicate`, `/teams/bulk-*`, `/teams-refresh-all`, `/sections`, `/cities` (включая `link-all`), `/tags`, `/redirects/*`, `/cache/flush`, `/views/flush` не проверяют токен. Любой может менять/удалять контент. Защита есть только в `auth`, `users`, `comments`, `media`, `templates`, `teams/restore-logos`.
2. **`/api/mongo/*` без авторизации**: `export` любой коллекции (в т.ч. `users` с `password_hash`), `import` (можно вставить себе пользователя с `role: admin`), `delete`, `aggregate` (`$out`/`$merge` позволяют перезаписывать коллекции).
3. **Админ по умолчанию `admin` / `admin`** создаётся при каждом старте, если его нет (`server.py:ensure_default_admin`), и пароль пишется в лог.
4. **`JWT_SECRET` не задан в compose** → `secrets.token_hex(32)` при старте процесса. Следствия: все сессии слетают после рестарта; в проде (gunicorn, 4 воркера) у каждого воркера свой секрет → токен от одного воркера невалиден на другом → случайные 401 (вероятная первопричина жалоб «теряется авторизация»). Решение: задать постоянный `JWT_SECRET` в env.
5. **`docker-compose-cloud.yml`: MongoDB без `--auth` и с `ports: 27017:27017`** — база открыта наружу, если хост не закрыт фаерволом.
6. `ProtectedRoute` на фронте проверяет только наличие пользователя, не роль — любой зарегистрированный (`/auth/register`) видит админку; вкупе с п.1 может всё править.
7. Обработчики ошибок в `server.py` возвращают клиенту текст исключения и тело запроса (утечка деталей), CORS `*` + `allow_credentials=True`.
8. `memory/test_credentials.md` и `server.py` содержат учётные данные в репозитории.

## 🟠 Баги

9. **`routes/redirects.py` создаёт свой `AsyncIOMotorClient(MONGO_URL)`** с дефолтом `mongodb://localhost:27017` и жёстко БД `humorpedia`. В dev-compose `MONGO_URL` не задан (используются `MONGO_HOST/USER/PASSWORD`) → в Docker-dev lookup редиректов падает. Надо перейти на `get_db()`.
10. **In-memory кэш на процесс**: при 4 воркерах gunicorn инвалидация срабатывает только в воркере, обработавшем запись; остальные отдают устаревшие данные до истечения TTL (до 5 мин для КВН/команд, 30 мин для редиректов). Инвалидация есть только в `content_kvn.py` и `content_teams.py`; `PUT /redirects/.../old-urls` кэш редиректов не сбрасывает.
11. `GET /content/kvn/by-path` при попадании в кэш возвращает ответ до `views_counter.increment` → просмотры страниц КВН сильно недосчитываются. Аналогично `GET /content/teams/{slug}` (при кэше просмотры не считаются).
12. `slowapi`: `default_limits=["1000/minute"]` не работает, т.к. не подключён `SlowAPIMiddleware`; реально лимиты только на `GET /api/`, `/content/search`, `/content/search/autocomplete`.
13. `/media` монтируется из `/app/frontend/public/media`, но в dev-compose `./frontend` в backend не монтируется, а volume `imported_images_volume` смонтирован в `/app/media/imported/images` → mount `/media` в dev, скорее всего, не создаётся (папки нет) и `/media/imported/...` отдаёт 404. Проверить на живом окружении.
14. Расхождение типов модулей: фронтовый `ModuleRenderer` поддерживает `image`, `image_gallery`, `video_embed`, `person_card`, `related_links`, `table_of_contents`, `html`, `divider`, а бэкенд `ModuleType` их не знает (сохранение таких модулей через API вернёт 422); и наоборот, `hero_card`, `tags`, `gallery`, `video`, `team_members`, `tv_appearances`, `games_list`, `episodes_list`, `participants`, `best_articles`, … на публичной стороне не рендерятся `ModuleRenderer`-ом (часть обрабатывается на конкретных страницах — проверять).
15. `sections` и `cities`: корневые маршруты объявлены как `"/"` при `redirect_slashes=False` → `/api/sections` (без слэша) = 404. Фронт использует `/cities/` со слэшем, для sections — `/sections` без слэша в `publicApi.getSections` → проверить, работает ли меню в Header.
16. `publicApi.getTeamsByCategory` шлёт `category`, бэкенд такой фильтр не поддерживает.

## 🟡 Техдолг / мусор

17. Мёртвый код: `backend/services/content.py` (ContentService), `backend/services/link_updater.py`, `frontend/src/public/pages/RedirectHandler.jsx`; `backend/routes/__init__.py` импортирует не все роутеры (не используется server.py).
18. `content_teams.py` (1682 строки), `content_kvn.py` (1267), `SeasonDataEditor.jsx` (2665) — кандидаты на декомпозицию; `find_adjacent_seasons` делает до десятков запросов с regex на одну страницу.
19. Непоследовательные идентификаторы КВН (`id` vs `_id`), `season_data.year` бывает строкой, `winners` в двух форматах.
20. Бинарники в git: `mongo-dump.archive` (12 МБ) дважды (корень и `migration/`), `*.docx`, `*.xlsx`, CSV-выгрузки, картинки в `uploads/`.
21. `requirements.txt` содержит dev/лишние пакеты (black, mypy, flake8, pytest, boto3, pandas, numpy, s5cmd, jq…) и дубликат `slowapi`; `cachetools` без версии.
22. Нет автотестов и CI; `backend_test.py` требует `frontend/.env`, которого нет.
23. `README.md` пустой; `test_result.md`, `.emergent/`, `.gitconfig` (emergent-agent), `frontend/plugins/*` — наследие Emergent.
24. Авторизация реализована вручную в каждом хендлере вместо FastAPI `Depends` — легко забыть проверку (см. п.1). Рекомендуется общий `Depends(require_role(...))` и подключение на уровне роутера.
25. `backup/` не подключён ни к одному compose (сервис удалён в 09934cd), при этом `BACKUP_SYSTEM.md` описывает его как работающий «в фоне».
