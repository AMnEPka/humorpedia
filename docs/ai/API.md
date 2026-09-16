# API Humorpedia (`/api/*`)

Все роутеры подключаются в `backend/server.py` к `APIRouter(prefix="/api")`. Swagger: `http://localhost:8001/docs`.

Обозначения авторизации: 🔓 — открыто; 👤 — любой залогиненный (не забанен); ✏️ — admin/editor; 🗂 — admin/editor/moderator; 🛡 — только admin; 🧑‍⚖️ — admin/moderator.
Авторизация — заголовок `Authorization: Bearer <jwt>`.

> Проверки прав — FastAPI-зависимости из `backend/utils/auth.py`. Роутеры контента, `/sections`, `/cities`, `/tags`, `/redirects` подключены с `require_editor_on_write`: чтение открыто, любой POST/PUT/PATCH/DELETE — ✏️. Тест `backend/tests/test_auth_guards.py` обходит все маршруты и падает, если запись доступна без токена.

Соглашения:
- Списки возвращают `{items, total, skip, limit}` (через `services/crud.list_content`; поле `modules` в списках исключено), параметры `skip`, `limit` (≤100), `status`, `tag`, `search`, иногда `letter`.
- `GET .../{id_or_slug}` ищет по `_id` или `slug`; `PUT/DELETE .../{id}` — по `_id` (для КВН — по `id`, затем `_id`).
- Ответы с `response_model=dict` — сырые документы Mongo (`_id` — строка UUID).

## server.py (служебные)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/` | версия API (лимит 100/мин) |
| GET | `/health` | healthcheck |
| GET | `/stats` | счётчики опубликованного контента, пользователей, комментариев, тегов |
| GET | `/random/{content_type}` | случайный документ: person/team/show/article/news/quiz/wiki |
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
| GET | `/people/{id_or_slug}/linked-content?types=news,article,show` | контент для модуля humor_chronicles |
| GET | `/people/{id_or_slug}` | документ, ссылки в модулях резолвятся |
| PUT | `/people/{id}` ✏️ | обновить (services/crud.update_content) |
| DELETE | `/people/{id}` ✏️ | удалить |

### Команды (`content_teams.py`, коллекция `teams`)
| Метод | Путь | Описание |
|---|---|---|
| POST | `/teams/bulk-check` ✏️ | проверить список названий на существование |
| POST | `/teams/bulk-create` ✏️ | массово создать команды (со scaffold модулей) |
| POST | `/teams/restore-logos` 🛡 | восстановить логотипы из старых полей |
| POST | `/teams` ✏️ | создать |
| GET | `/teams` | список (кэш 2 мин), фильтры `status, team_type, tag, search, letter`; `team_type=kvn` включает команды без `team_type` |
| GET | `/teams/{id_or_slug}` | документ (кэш 5 мин), без записи при чтении |
| POST | `/teams/{id_or_slug}/refresh` ✏️ | self-healing: scaffold фактов/модулей, авто-модуль «Список игр команды» из season_data, логотип, primary_tag |
| POST | `/teams-refresh-all` ✏️ | self-healing всех команд |
| PUT | `/teams/{id}` ✏️ | обновить; при смене slug — обновляет ссылки во всех `kvn.season_data` и пересобирает сезоны (исторические названия не меняются) |
| DELETE | `/teams/{id}` ✏️ | удалить |

### КВН (`content_kvn.py`, коллекция `kvn`)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/kvn/jury-stats?league_slug=vl-kvn&min_year&max_year` | агрегированная статистика жюри по season_data |
| POST | `/kvn` ✏️ | создать; вычисляет `level`, `full_path` от родителя (макс. уровень 4) |
| GET | `/kvn` | список |
| GET | `/kvn/by-path/{path}` | страница по `full_path` + `children` + `breadcrumbs` + prev/next сезон (кэш) |
| GET | `/kvn/{parent_slug}/children` | дочерние страницы |
| GET | `/kvn/{id_or_slug}` | документ |
| GET | `/kvn-hierarchy` | дерево |
| PUT | `/kvn/{id}` ✏️ | обновить (включая `season_data`, `jury_cards`); пересчёт full_path, очистка данных, инвалидация кэша |
| DELETE | `/kvn/{id}` ✏️ | удалить |

### Шоу (`content_shows.py`, коллекция `shows`)
POST `/shows` ✏️ · GET `/shows` · GET `/shows/by-path/{path}` · GET `/shows/{parent_slug}/children` · GET `/shows/{id_or_slug}` · GET `/shows-hierarchy` · PUT `/shows/{id}` ✏️ · DELETE `/shows/{id}` ✏️

### Статьи / Новости / Квизы / Вики
Одинаковый CRUD через `services/crud.py`:
- `articles`: POST `/articles` · GET `/articles` · GET `/articles/random` · GET `/articles/{id_or_slug}` · PUT `/articles/{id}` · DELETE `/articles/{id}`
- `news`: POST/GET `/news`, GET `/news/{id_or_slug}`, PUT/DELETE `/news/{id}`
- `quizzes`: POST/GET `/quizzes`, GET `/quizzes/{id_or_slug}`, PUT/DELETE `/quizzes/{id}`
- `wiki`: POST/GET `/wiki`, GET `/wiki/{id_or_slug}`, PUT/DELETE `/wiki/{id}`

Все write — ✏️. При сохранении `related_person_ids` обновляются связи с людьми (`services/linking.py`).

### Поиск (`content_search.py`)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/search-for-links?q=` | поиск для вставки внутренних ссылок в редакторе |
| GET | `/{content_type}/{id_or_slug}/resolve-link` | актуальный URL сущности |
| GET | `/search?q=` | полнотекстовый поиск (text-индексы, 60/мин) |
| GET | `/search/autocomplete?q=` | автокомплит (120/мин) |
| GET | `/search/by-tag/{tag}` | весь контент с тегом |
| POST | `/{content_type}/{id}/duplicate` ✏️ | дублировать документ |

## sections.py — `/sections` (коллекция `sections`)
POST `/` ✏️ · GET `/` · GET `/tree` · GET `/{id_or_slug}` · GET `/{section_id}/children` · PUT `/{id}` ✏️ (пересчёт путей детей, защита от циклов) · DELETE `/{id}?cascade=` ✏️ · GET `/path/{path}`
Корневые маршруты доступны и со слэшем, и без (`/api/sections`, `/api/sections/`).

## cities.py — `/cities` (коллекция `cities`)
POST `/` ✏️ · GET `/` · GET `/{id_or_slug}` · PUT `/{id}` ✏️ · DELETE `/{id}` ✏️ · GET `/{city_id}/related-people` · GET `/{city_id}/related-teams` · POST `/link-all` ✏️ · POST `/{city_id}/link` ✏️
(Корень — со слэшем и без.)

## tags.py — `/tags`
POST `` ✏️ · GET `` · GET `/popular` · GET `/{id_or_slug}` · PUT `/{id}` ✏️ · DELETE `/{id}` ✏️ · POST `/update-counts` ✏️

## comments.py — `/comments`
| POST `` 👤 (не забанен) · GET `?resource_type&resource_id` · GET `/recent` · PUT `/{id}` 👤 автор или admin · DELETE `/{id}` 👤 автор или admin · POST `/{id}/like` 👤 · GET `/pending` 🧑‍⚖️ · POST `/{id}/approve` 🧑‍⚖️ · POST `/{id}/reject` 🧑‍⚖️ |
|---|

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
