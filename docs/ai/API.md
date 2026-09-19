# API Humorpedia (`/api/*`)

Все роутеры подключаются в `backend/server.py` к `APIRouter(prefix="/api")`. Swagger: `http://localhost:8001/docs`.

Обозначения авторизации: 🔓 — открыто; 👤 — любой залогиненный (не забанен); ✏️ — admin/editor; 🗂 — admin/editor/moderator; 🛡 — только admin; 🧑‍⚖️ — admin/moderator.
Авторизация — заголовок `Authorization: Bearer <jwt>`.

> Проверки прав — FastAPI-зависимости из `backend/utils/auth.py`. Роутеры контента, `/sections`, `/cities`, `/tags`, `/redirects` подключены с `require_editor_on_write`: чтение открыто, любой POST/PUT/PATCH/DELETE — ✏️. Тест `backend/tests/test_auth_guards.py` обходит все маршруты и падает, если запись доступна без токена.

Соглашения:
- Списки возвращают `{items, total, skip, limit}` (через `services/crud.list_content`; поле `modules` в списках исключено), параметры `skip`, `limit` (≤100), `status`, `tag`, `search`, иногда `letter`. Алфавитные списки дополнительно возвращают `available_letters`; значение `letter=other` объединяет названия с латинской буквы, цифры или символа.
- `GET .../{id_or_slug}` ищет по `_id` или `slug`; `PUT/DELETE .../{id}` — по `_id` (для КВН — по `id`, затем `_id`).
- Ответы с `response_model=dict` — сырые документы Mongo (`_id` — строка UUID).

## server.py (служебные)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/` | версия API (лимит 100/мин) |
| GET | `/health` | healthcheck |
| GET | `/stats` | счётчики опубликованного контента, пользователей, комментариев, тегов |
| GET | `/random/{content_type}` | случайный документ: person/team/show/article/news/quiz/wiki/city; `exclude_slug` исключает текущий slug до выборки; сохраняет full_path/show_id/url для навигации |
| GET | `/cache/stats` 🛡 | статистика кэшей и views_counter |
| POST | `/cache/flush` 🛡 | сбросить все in-memory кэши |
| POST | `/views/flush` 🛡 | принудительно записать просмотры в БД |

## auth.py — `/auth`
| Метод | Путь | Описание |
|---|---|---|
| POST | `/register` | email-регистрация → TokenResponse; пароль ≥8, лимит 10/час с IP |
| POST | `/login` | `{email, password}` → `{access_token, token_type, expires_in, user}` (JWT HS256, 7 дней); лимит 20/мин с IP |
| GET | `/me` 👤 | текущий пользователь |
| POST | `/refresh` | новый токен по старому (допускается просрочка до 30 дней); забаненным — 403 |
| GET | `/vk`, `/vk/callback` | VK OAuth |
| GET | `/yandex`, `/yandex/callback` | Yandex OAuth |
| POST | `/logout` | — |

## users.py — `/users`
| GET `` 🛡 (фильтры role/search/banned) · GET `/{user_id}` 🛡 · PUT `/me` 👤 · PUT `/{user_id}` 🛡 · POST `/{user_id}/ban` 🛡 · POST `/{user_id}/unban` 🛡 · DELETE `/{user_id}` 🛡 |
|---|

## Контент — `/content`

### Люди (`content_people.py`, коллекция `people`)
| Метод | Путь | Описание |
|---|---|---|
| POST | `/people` ✏️ | создать; если нет `primary_tag` — берётся из title с переставленными словами («Имя Фамилия» → «Фамилия Имя») |
| GET | `/people` | список, фильтры `status, tag, search, letter`, сортировка по title |
| GET | `/people/search?q=` | быстрый поиск для селекторов `[{id, name, slug}]` |
| GET | `/people/{id_or_slug}?raw=` | документ; ссылки проверяются, ссылки на людей с `foreign_agent=true` получают динамическую звёздочку и `foreign_agent_notice`; `raw=true` — как в данных (админка) |
| PUT | `/people/{id}` ✏️ | обновить (services/crud.update_content) |
| DELETE | `/people/{id}` ✏️ | удалить |

### Команды (`content_teams.py`, коллекция `teams`)
| Метод | Путь | Описание |
|---|---|---|
| POST | `/teams/bulk-check` ✏️ | проверить список названий на существование |
| POST | `/teams/bulk-create` ✏️ | массово создать команды (со scaffold модулей) |
| POST | `/teams/restore-logos` 🛡 | восстановить логотипы из старых полей |
| POST | `/teams` ✏️ | создать; `show_id` — команда шоу (адрес и `team_type` вычисляются, заготовки КВН не добавляются) |
| GET | `/teams` | список (кэш 2 мин), фильтры `status, team_type, tag, search, letter, show_id`; `team_type=kvn` — команды КВН (в т.ч. без `team_type`), `team_type={slug шоу}` — команды шоу; у элементов `url` и `show` |
| GET | `/teams/by-path/{шоу}/teams/{slug}` | команда шоу по адресу (публичная страница `/shows/…/teams/{slug}`): + `show`, `breadcrumbs`, ссылки проверяются |
| GET | `/teams/{id_or_slug}?raw=` | документ (кэш 5 мин), без записи при чтении; slug — только команды КВН (команду шоу — по `_id`); ссылки проверяются, `raw=true` — без обработки и кэша (админка); + `show`, `url` |
| POST | `/teams/{id_or_slug}/refresh` ✏️ | self-healing: scaffold фактов/модулей, авто-модуль «Список игр команды» из season_data, логотип, primary_tag |
| POST | `/teams-refresh-all` ✏️ | self-healing всех команд |
| PUT | `/teams/{id}` ✏️ | обновить; `show_id` (`""` — сделать командой КВН) и slug пересчитывают адрес; при смене slug команды КВН — обновляет ссылки во всех `kvn.season_data` и пересобирает сезоны (исторические названия не меняются) |
| DELETE | `/teams/{id}` ✏️ | удалить |

### КВН (`content_kvn.py`, коллекция `kvn`)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/kvn/jury-stats?league_slug=vl-kvn&min_year&max_year` | агрегированная статистика жюри по season_data |
| POST | `/kvn` ✏️ | создать; вычисляет `level`, `full_path` от родителя (макс. уровень 4) |
| GET | `/kvn` | список |
| GET | `/kvn/by-path/{path}` | страница по `full_path` + `children` + `breadcrumbs` + prev/next сезон (кэш) |
| GET | `/kvn/{parent_slug}/children` | дочерние страницы |
| GET | `/kvn/{id_or_slug}?raw=` | документ; ссылки проверяются (как и в `by-path`), `raw=true` — как в данных (админка) |
| GET | `/kvn-hierarchy` | дерево |
| PUT | `/kvn/{id}` ✏️ | обновить (включая `season_data`, `jury_cards`); пересчёт full_path, очистка данных, инвалидация кэша |
| DELETE | `/kvn/{id}` ✏️ | удалить |

### Шоу (`content_shows.py`, коллекция `shows`)
POST `/shows` ✏️ (учитывает `parent_id`, считает `full_path`) · GET `/shows` (только корневые, `include_children=true` — все) · GET `/shows/by-path/{path}` (+ `children`, `breadcrumbs`, ссылки проверяются) · GET `/shows/{_id|full_path}/children` · GET `/shows/{id_or_slug}?raw=` (ссылки проверяются, `raw=true` — для админки) · GET `/shows-hierarchy` · PUT `/shows/{id}` ✏️ · DELETE `/shows/{id}` ✏️

### Статьи / Новости / Квизы / Вики
Одинаковый CRUD через `services/crud.py`:
- Список статей: `sort=-created_at` (по умолчанию) или `-rating`; `exclude_archived=true` для публичных виджетов; `featured=true` для редакционной подборки.
- `articles`: POST `/articles` · GET `/articles` · GET `/articles/random` · GET `/articles/{id_or_slug}?raw=` · PUT `/articles/{id}` · DELETE `/articles/{id}`
- `news`: POST/GET `/news`, GET `/news/{id_or_slug}?raw=`, PUT/DELETE `/news/{id}`
- `quizzes`: POST/GET `/quizzes`, GET `/quizzes/{id_or_slug}`, PUT/DELETE `/quizzes/{id}`
- `wiki`: POST/GET `/wiki`, GET `/wiki/{id_or_slug}`, PUT/DELETE `/wiki/{id}`

Все write — ✏️. Связи новости с целевыми страницами хранятся непосредственно в
`related_person_ids`, `related_team_ids`, `related_show_ids`.
Публичные GET статьи и новости проверяют внутренние ссылки и динамически добавляют пометку иностранного агента;
админка использует `raw=true`, чтобы не записывать сгенерированную разметку.

## related_news.py — `/related-news`

- `GET /{entity_type}/{entity_id}` 🔓, где `entity_type=person|team|show` — максимум три новости новее настроенного порога. Команда КВН и команда шоу различаются по `teams.show_id`; отключённый тип возвращает `enabled=false, items=[]`.
- `GET /settings` 🛡 и `PUT /settings` 🛡 — глобальные настройки: `enabled`, `freshness_days`, `max_items` (1–3), `apply_to.people/kvn_teams/show_teams/shows`.

## recommendations.py — `/recommendations`
`GET /?content_type={article|news|person|team|show|city|kvn}&content_id=&limit=` 🔓 — блок «Читайте также».
Сначала возвращает опубликованные статьи из `related_article_ids` в ручном порядке, затем детерминированный fallback
по прямым связям, общим тегам, featured, рейтингу, просмотрам, дате и `_id`. Текущая статья, дубли, черновики,
архивные и отсутствующие документы исключаются; максимальный лимит задаётся политикой типа страницы.

### Поиск (`content_search.py`)
Во всех текстовых поисках `е` и `ё` эквивалентны: запрос `звезды` находит `Звёзды на НТВ` и ранжирует это совпадение как обычное совпадение по префиксу. Исходное написание данных не изменяется.

| Метод | Путь | Описание |
|---|---|---|
| GET | `/search-for-links?query=` | поиск для вставки внутренних ссылок в редакторе |
| GET | `/{content_type}/{id_or_slug}/resolve-link` | актуальный URL сущности |
| GET | `/search?q=` | поиск по подстроке от 2 символов с ранжированием совпадений (60/мин) |
| GET | `/search/autocomplete?q=` | автокомплит от 2 символов, общая сортировка по релевантности (120/мин) |
| GET | `/search/by-tag/{tag}` | весь контент с тегом |
| POST | `/{content_type}/{id}/duplicate` ✏️ | дублировать документ |

## sections.py — `/sections` (коллекция `sections`)
POST `/` ✏️ · GET `/` · GET `/tree` · GET `/{id_or_slug}` · GET `/{section_id}/children` · PUT `/{id}` ✏️ (пересчёт путей детей, защита от циклов) · DELETE `/{id}?cascade=` ✏️ · GET `/path/{path}`
Корневые маршруты доступны и со слэшем, и без (`/api/sections`, `/api/sections/`).

## cities.py — `/cities` (коллекция `cities`)
POST `/` ✏️ · GET `/` · GET `/{id_or_slug}` · PUT `/{id}` ✏️ · DELETE `/{id}` ✏️ · GET `/{city_id}/related-people` · GET `/{city_id}/related-teams` · POST `/link-all` ✏️ · POST `/{city_id}/link` ✏️
(Корень — со слэшем и без.)

`GET /{id_or_slug}?raw=true` возвращает документ без обработки ссылок и динамических пометок для админки.
`POST /link-all` и `POST /{city_id}/link` пересчитывают команды по точному значению города, сохраняя
редакционный `related_person_ids` без изменений.

## tags.py — `/tags`
POST `` ✏️ · GET `` · GET `/popular` · GET `/{id_or_slug}` · PUT `/{id}` ✏️ · DELETE `/{id}` ✏️ · POST `/update-counts` ✏️

## comments.py — `/comments`
| POST `` 👤 (не забанен) · GET `?resource_type&resource_id` · GET `/recent` · PUT `/{id}` 👤 автор или admin · DELETE `/{id}` 👤 автор или admin · POST `/{id}/like` 👤 · GET `/pending` 🧑‍⚖️ · POST `/{id}/approve` 🧑‍⚖️ · POST `/{id}/reject` 🧑‍⚖️ |
|---|

## ratings.py — `/ratings`
| Метод | Путь | Описание |
|---|---|---|
| GET | `/{entity_type}/{entity_id}` 🔓 | среднее, публичная веха числа голосов и собственная оценка посетителя |
| PUT | `/{entity_type}/{entity_id}` 🔓 | поставить или заменить собственную оценку от 1 до 10; лимит 10/мин на IP |

`entity_type` — `article`, `person`, `team` или `show`. Анонимного посетителя определяет подписанная HttpOnly-cookie
`hp_rating_voter` сроком на год; браузер отправляет её только на `/api/ratings`. Повторный голос того же посетителя заменяет
его прежнюю оценку и не увеличивает количество голосов. Ответ всегда `private, no-store`, содержит
`{average, votes_label, my_score}` и не раскрывает точное число голосов. Публичные вехи: «менее 50 голосов»,
«50+ голосов», «100+ голосов», «250+ голосов», «500+ голосов», «1000+ голосов».

## polls.py — `/polls`
| Метод | Путь | Описание |
|---|---|---|
| GET | `` / `/` ✏️ | список определений для редактора |
| POST | `` / `/` ✏️ | создать определение опроса |
| GET | `/{poll_id}` 🔓 | опубликованный опрос; с JWT возвращает свой выбор, результаты до голоса скрыты по политике опроса; `private, no-store` |
| GET | `/{poll_id}/edit` ✏️ | полное определение для редактора |
| PUT | `/{poll_id}` ✏️ | изменить; нельзя удалить вариант с историческими или новыми голосами |
| DELETE | `/{poll_id}` ✏️ | перевести в `archived` |
| POST | `/{poll_id}/vote` 👤 | один вариант; требуется permission `vote`, повтор → 409 |

Голос записывается в `poll_votes` через детерминированный `_id={poll_id}:{user_id}`. Эта коллекция — источник истины;
публичный результат складывает её агрегат с анонимными `historical_votes` в вариантах.

## media.py — `/media` (коллекция `media` + файлы)
| Метод | Путь | Описание |
|---|---|---|
| POST | `/upload` 🗂 | загрузка в `UPLOAD_DIR/YYYY/MM` (≤10 МБ) |
| POST | `/upload-to-source` 🗂 | загрузка в папку volume (images / imported) |
| GET | `` 🗂 | список медиа из БД |
| GET | `/browse` 🗂 | браузер файлов volume (папки, поиск) |
| DELETE | `/source/delete` 🗂 | удалить файл из volume |
| PUT | `/source/rename` 🗂 | переименовать файл в volume |
| GET | `/{media_id}` 🔓 | метаданные |
| PUT | `/{media_id}` 🗂 | alt/caption |
| DELETE | `/{media_id}` 🛡 | soft delete |

## templates.py — `/templates` (коллекция `templates`)
POST `` ✏️(admin/editor) · GET `?content_type` · GET `/default/{content_type}` · GET `/{template_id}` · PUT `/{template_id}` ✏️ · POST `/{template_id}/set-default` 🛡 · DELETE `/{template_id}` 🛡 · POST `/{template_id}/apply-to-teams` 🛡 (мёрж модулей шаблона в существующие модули команд) · GET `/modules/types`

## redirects.py — `/redirects`
| GET `/lookup?path=` — ищет `old_urls` в kvn/teams/people/shows/articles/news + паттерны старых URL MODX; кэш 30 мин · PUT `/{collection}/{doc_id}/old-urls` ✏️ · POST `/auto-populate` ✏️ |
|---|
Кэш редиректов сбрасывается при изменении `old_urls`.

## mongo_admin.py — `/mongo` 🛡 (страница админки «База данных»)
GET `/collections` · POST `/export` (query/projection/sort/limit) · POST `/import` (insert/upsert/replace) · POST `/delete` (непустой query) · POST `/aggregate` · GET `/stats`

## competitions.py — `/competitions` (турниры, сезоны, перекрёстные ссылки)
GET `/tournaments?show=` · GET `/tournaments/{show}/{slug}` (турнир + сезоны) · GET `/seasons/{id}` · GET `/seasons/by-page/{page_id}` · PUT `/seasons/{id}` ✏️ (пишет и в `season_data` страницы) · GET `/unresolved` · POST `/sync` 🛡 · GET `/teams/{id_or_slug}/participations?games=`
Подробно — [COMPETITIONS.md](COMPETITIONS.md).

## memberships.py — `/competitions` (составы, карьера человека)
GET `/teams/{id_or_slug}/members` · POST `/memberships` ✏️ · PUT `/memberships/{id}` ✏️ · DELETE `/memberships/{id}` ✏️ · POST `/memberships/import-rosters?team=` 🛡 · GET `/people/{id_or_slug}/career`

## show_appearances.py — `/show-appearances` (участие людей в шоу)
GET `/people/{person_id}` 🔓 · GET `/review` ✏️ · POST `/sync` ✏️ · PATCH `/review/{id}` ✏️ · POST `/review/{id}/create-person` ✏️.
Публичный метод отдаёт участие для страницы человека: `show_url` ведёт на проект, а `link_url` — на проект для индивидуальной записи и на команду для командной. В существующие карточки участников шоу проверенные ссылки добавляет `content_shows.py`. Проверка, ручная привязка и создание одного черновика доступны редактору. Подробно — [SHOW_APPEARANCES.md](SHOW_APPEARANCES.md).
