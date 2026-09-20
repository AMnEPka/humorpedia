# Модель соревнований и перекрёстные ссылки (этапы 1–2)

Универсальная структура для лиг КВН и любых других шоу (ИГРА, Звёзды на НТВ, Импровизация. Команды, Рассмеши комика — лишь первые из многих; новое шоу = данные, а не код):

```
турнир (tournaments) ─┬─ сезон (seasons) ─┬─ список участников сезона (teams)   ← «состав» лиги в сезоне
                      │                   ├─ победители (winners)
                      │                   └─ этапы → игры → результаты участников
                      └─ …
participations  — производная таблица перекрёстных ссылок, пересобирается при каждом сохранении сезона
memberships     — составы команд: человек — команда — роли — годы (этап 2)
```

Код: `backend/services/competitions.py` (логика), `backend/models/competition.py` (валидация записи),
`backend/routes/competitions.py` (API), `backend/scripts/migrate_competitions.py` (миграция/отчёт),
`backend/tests/test_competitions.py`; составы — `backend/services/memberships.py`, `backend/routes/memberships.py`,
`backend/tests/test_memberships.py`; фронтенд — `frontend/src/public/components/competitions/*`,
`frontend/src/admin/components/TeamMembershipsEditor.jsx`.

## Решения владельца (2026-09-16)

- «Состав» лиги в сезоне = список команд сезона (`seasons.teams`).
- Команда в разных шоу — **разные сущности** в `teams` (свои `show_id`/`team_type`, адрес `/shows/{шоу}/teams/{slug}`,
  см. DATA_MODEL.md «Команды шоу»), связь между ними — `related_team_ids`. Сезоны КВН ссылаются только на команды КВН.
- Составы команд (этап 2): запись «человек — команда — роль — годы» + опциональное уточнение сезонами.
- В сезоне хранится **название участника на момент сезона**; переименование команды его не меняет
  (смена slug — меняет ссылки).
- «Звёзды» = «Звёзды на НТВ».

## Коллекции

### tournaments
```jsonc
{ "_id": "uuid5(tournament:kvn:vl-kvn)", "show": "kvn", "slug": "vl-kvn",
  "title": "Высшая лига КВН", "short_title": "…", "participant_type": "team" | "person",
  "team_type": "kvn", "page_collection": "kvn", "page_id": "…", "page_path": "kvn/vl-kvn",
  "order": 10, "status": "published" }
```
Уникальность: `(show, slug)`. Турниры лиг КВН создаются автоматически при первой синхронизации сезона (по странице `kvn/<лига>`).

### seasons
```jsonc
{ "_id": "uuid5(kvn-page:<page_id>)",           // детерминированный: 1 страница сезона = 1 сезон
  "tournament_id", "tournament_slug", "show", "participant_type",
  "title", "slug", "year": 2015, "number": 29, "status",
  "page_collection": "kvn", "page_id", "page_path": "kvn/vl-kvn/vl-2015",
  // поля старого season_data (переносятся как есть)
  "league_name", "intro_html", "description", "metadata", "host", "hosts", "editors", "jury",
  "extra_sections", "late_joined_teams",
  "teams":   [ { "team_id": "teams._id|null", "person_id": null, "slug", "name", "city", "had_city", "extra": {} } ],
  "winners": [ …то же… ],
  "stages": [ { "id", "name": "1/2 финала", "code": "1/2", "order": 3 /* бывает 2.5 */,
                "comment" /* обычный текст перед сеткой */, "notes" /* совместимый старый HTML */,
                "additional_teams": ["…"], "additional_notes",
                "games": [ { "id" /* уникален в сезоне */, "legacy_id", "had_legacy_id", "name", "order", "date", "date_raw",
                             "host", "jury": ["Имя"], "contests": ["Приветствие"], "notes", "is_cancelled",
                             "results": [ { "team_id", "person_id", "slug", "name", "city", "place", "total",
                                            "scores": {"Приветствие": 5}, "passed", "is_winner", "is_additional",
                                            "legacy_team_id", "extra": {} } ],
                             "extra": {} } ],
                "extra": {} } ],
  "legacy_keys": ["…"],   // какие ключи были в season_data — чтобы обратная конвертация была точной
  "extra": {},            // неизвестные ключи season_data
  "created_at", "updated_at" }
```
`code` этапа: `1/8`, `1/4`, `1/2`, `final`, `consolation`, `""` (нестандартный/комбинированный).
Ссылка на команду — **`teams._id`** (не поле `id`, которое у команд обычно не совпадает с `_id`).

### participations
Одна строка `kind: "season"` на участника сезона, по одной `kind: "game"` на каждый результат в игре
и по одной `kind: "role"` на человека в роли жюри/ведущего/редактора сезона.
```jsonc
// общие поля
{ "_id": "uuid5(...)", "kind", "participant_key": "team:<id>" | "person:<id>" | "slug:<slug>" | "name:<name>",
  "team_id", "person_id", "slug", "name" /* на момент сезона */, "city",
  "tournament_id", "tournament_slug", "show", "season_id", "season_year", "season_title", "season_path", "season_status" }
// kind=season
{ "in_season_list", "is_champion", "games_played", "wins",
  "best_stage_order", "best_stage_name", "best_stage_code", "last_stage_passed" }
// kind=game
{ "stage_id", "stage_order", "stage_name", "stage_code", "game_id", "game_order", "game_name", "date",
  "place", "total", "scores", "passed", "is_winner", "is_additional", "participants_count" }
// kind=role (жюри/ведущие/редакторы: season.jury/hosts/host/editors + game.jury/host)
{ "role": "jury" | "host" | "editor", "name", "name_key", "person_id" /* если имя однозначно найдено */, "matched_by",
  "games_count", "game_ids" }
```
Индексы: `(team_id, kind, season_year)`, `(person_id, kind, season_year)`, `(slug, kind)`, `(name_key, kind)`, `season_id`.
**Никогда не редактировать напрямую** — только через сохранение сезона.

## Синхронизация (переходный период, до этапа 3)

Публичные страницы (`SeasonDetailPage`) и старый редактор (`SeasonDataEditor`) работают с `kvn.season_data`.
Обычные `kvn.modules` у таких страниц считаются архивными: публично не выводятся и в KVNEditor доступны read-only.
`extra_modules` для сезонов не используются. Для редакционного текста конкретной стадии служит `stages[].comment`.

| Событие | Что происходит |
|---|---|
| Старт сервера, коллекция `seasons` пуста | `ensure_competitions_synced` → синхронизация всех страниц с `season_data` |
| `PUT /content/kvn/{id}` (season_data, путь, slug, title, status) | `sync_from_kvn_page` → сезон + participations |
| `POST /content/kvn` с автосозданным season_data | то же |
| `DELETE /content/kvn/{id}` | сезон и participations удаляются |
| `PUT /competitions/seasons/{id}` | сезон + participations + `season_data` записывается обратно в страницу (prev/next сохраняются) |
| Смена slug команды | ссылки в season_data обновляются, затронутые сезоны пересобираются |
| Удаление команды | затронутые сезоны пересобираются (ссылки становятся непривязанными) |
| `POST /competitions/sync` (admin) / `python scripts/migrate_competitions.py --apply` | полная пересинхронизация |

Свойства конвертации (проверены на 119 реальных сезонах, 5127 результатах):
`season_data → сезон → season_data` без потерь (кроме восстановления отсутствующего `year` из slug).

⚠ Пока жив старый путь, данные, которых нет в `season_data` (например, `person_id` у результатов для шоу с людьми),
будут затираться при сохранении страницы старым редактором. Такие шоу (этап 4) делать только через новый API.

## Составы команд — `memberships` (этап 2)

```jsonc
{ "_id", "team_id": "teams._id", "person_id": "people._id|null", "candidate_person_id": "people._id|null",
  "rejected_person_id": "people._id|null", "matched_by": "slug|name|manual|null",
  "link_review_status": "candidate|confirmed|rejected|null", "reviewed_by", "reviewed_at",
  "person_link_disabled": false /* ручной запрет автопривязки однофамильца */,
  "person_name": "Дмитрий Шпеньков", "person_slug": "dmitry-shpenkov" /* slug старого сайта из ссылки */,
  "name_key": "дмитрий шпеньков" /* без регистра, ё и порядка слов */,
  "roles": ["капитан"], "from_year": 2010, "to_year": 2012, "status": "current" | "former", "season_ids": [],
  "note", "source": "roster_text" | "manual", "source_ref": "<id модуля>", "order", "created_at", "updated_at" }
```

- **Импорт из текста.** Блоки `text_block` с заголовком «Состав команды» / «Состав команды КВН» / «Состав участников»
  разбираются `parse_roster_html`: `<li>`/`<div>`/`<p>`/`<br>`-строки, ссылки `people/<slug>.html`, роли после тире,
  годы в скобках («с 2022», «2017–2019», «до 2021»), разделы «Бывшие участники:», «Присоединившиеся … в сезоне 2025:».
  Повествовательные строки не превращаются в записи — блок считается разобранным не полностью.
- **Когда импортируется:** при старте, если коллекция пуста; при сохранении модулей команды; вручную —
  `POST /api/competitions/memberships/import-rosters[?team=]` (admin). Импорт перезаписывает только `source=roster_text`;
  человек, уже заведённый вручную, из текста не дублируется; один человек из двух блоков объединяется.
- **Правка** импортированной записи делает её ручной (`source=manual`) — повторный импорт её не трогает.
- Если редактор отклоняет ошибочную выбранную страницу человека, запись получает `person_link_disabled=true`: имя остаётся
  в составе без ссылки, а отвергнутый `person_id` сохраняется в `rejected_person_id` для истории. Выбор правильной страницы
  вручную снимает запрет.
- **Связь с людьми.** Явный slug (включая `old_urls` вида `/people/<slug>.html`) записывается в `person_id`. Если текст имени
  в составе не совпадает с именем/псевдонимом целевой страницы, связь остаётся публичной, но попадает в очередь проверки.
  Совпадение только по однозначному имени или конфликт slug сохраняются кандидатом в `candidate_person_id`, но публичной
  ссылки не создают до подтверждения редактором. Удаление человека сбрасывает `person_id`.
- **Переход существующих данных.** 88 ранее созданных сомнительных связей остаются публичными со статусом `candidate`,
  пока редактор не обработает их на `/admin/membership-links`. Повторный импорт состава сохраняет это состояние. Только
  действие «Некорректная связь — отвязать» удаляет публичную связь; запись участника и его имя не удаляются.
- **На сайте** текстовый блок состава заменяется структурой, только если **все** непустые блоки состава разобраны полностью
  (`teams.roster_import[].complete`), иначе показывается исходный текст.

Данные (локальная БД 2026-04): 1048 команд с блоками состава, 3754 записи, ~95% непустых блоков разобраны полностью,
950 записей со slug человека старого сайта.

## Синхронизация составов и людей

| Событие | Что происходит |
|---|---|
| Старт сервера, `memberships` пуста | `ensure_rosters_imported` → импорт всех составов |
| `PUT /content/teams/{id}` с `modules` | состав команды переразбирается |
| `DELETE /content/teams/{id}` | записи состава удаляются |
| `POST/PUT /content/people` | `link_person` — связь записей составов с человеком |
| `DELETE /content/people/{id}` | `unlink_person` — `person_id` сбрасывается |
| Роли жюри/ведущих | `person_id` в participations ставится при сохранении сезона; публичная карьера использует только сохранённый `person_id` |

## API — `/api/competitions`
| Метод | Путь | Доступ | Описание |
|---|---|---|---|
| GET | `/tournaments?show=` | 🔓 | турниры |
| GET | `/tournaments/{show}/{slug}` | 🔓 | турнир + сезоны (без игр, со счётчиками) |
| GET | `/seasons/{id}` | 🔓 | сезон целиком + `unresolved` |
| GET | `/seasons/by-page/{page_id}` | 🔓 | сезон по странице |
| PUT | `/seasons/{id}` | ✏️ | правка (`SeasonUpdate`: year, number, teams, winners, stages, jury, …); ссылки на команды проверяются |
| GET | `/unresolved?show=&tournament=` | 🔓 | участники без привязки к команде/человеку |
| POST | `/sync` | 🛡 | пересинхронизировать все сезоны из страниц |
| GET | `/teams/{id_or_slug}/participations?games=` | 🔓 | участие команды во всех сезонах (черновики скрыты) |
| GET | `/teams/{id_or_slug}/members` | 🔓 | состав: `current`, `former`, `roster_blocks` (полнота разбора) |
| POST | `/memberships` | ✏️ | добавить запись состава |
| PUT | `/memberships/{id}` | ✏️ | правка (запись становится ручной) |
| DELETE | `/memberships/{id}` | ✏️ | удалить |
| POST | `/memberships/import-rosters?team=` | 🛡 | разобрать текст состава (одной команды или всех) |
| GET | `/membership-links/review?q=&status=&reason=&skip=&limit=` | ✏️ | очередь проверки связей состава и счётчики |
| PATCH | `/membership-links/review/{id}` | ✏️ | `confirm`, `reject` или `link` с выбранным `person_id` |
| GET | `/people/{id_or_slug}/career` | 🔓 | команды человека, сезоны и роли в турнирах; публичная карточка человека показывает из них только команды КВН и роли состава |

## Фронтенд
- `public/components/competitions/TeamParticipations.jsx` — «Участие в турнирах» на странице команды (группировка по турнирам,
  итог сезона, раскрываемая таблица игр; название «как «…»», если в сезоне команда называлась иначе).
- `TeamRoster.jsx` — структурированный состав; `PersonCareer.jsx` — «Команды КВН» без сезонных плашек
  (название, ссылка, роли из состава) и «В турнирах» на странице человека;
  `labels.js` — общие подписи (итог сезона, роли, годы, ссылки).
- Старый модуль «Список игр команды» скрыт на странице и удаляется самовосстановлением команды (`/content/teams/{slug}/refresh`).
- Админка: вкладка «Состав» в редактировании команды (`TeamMembershipsEditor.jsx`) и отдельная очередь
  `/admin/membership-links` (`MembershipLinksPage.jsx`) для подтверждения, замены или отклонения кандидатов.

## Данные на 2026-04 (локальная БД)
119 сезонов: ВЛ 39, Премьер 23, Первая 33, Международная 12, ВУЛ 12; 454 этапа, 1016 игр, 5127 результатов;
35 результатов без команды (18 уникальных названий, в основном без slug) — список: `GET /api/competitions/unresolved`.
В ролях: 495 разных членов жюри.

## Дальше
- Страницы людей: перенесены все 1039 опубликованных людей старого сайта (scripts/import_people_modx.py); составы связаны с людьми по slug старого сайта (991 из 3754 записей), роли жюри/ведущих — 602 из 1570.
  Как только люди будут заведены, составы и роли свяжутся автоматически.
- Этап 3: админ-редактор сезона на новой модели, привязка непривязанных участников; отказ от `season_data`.
- Этап 4: турниры для других шоу (`participant_type: person` для шоу с людьми).
