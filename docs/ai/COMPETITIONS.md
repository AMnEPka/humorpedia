# Модель соревнований (этап 1)

Универсальная структура для лиг КВН и других шоу (ИГРА, Звёзды на НТВ, Импровизация. Команды, Рассмеши комика):

```
турнир (tournaments) ─┬─ сезон (seasons) ─┬─ список участников сезона (teams)   ← «состав» лиги в сезоне
                      │                   ├─ победители (winners)
                      │                   └─ этапы → игры → результаты участников
                      └─ …
participations  — производная таблица перекрёстных ссылок, пересобирается при каждом сохранении сезона
```

Код: `backend/services/competitions.py` (логика), `backend/models/competition.py` (валидация записи),
`backend/routes/competitions.py` (API), `backend/scripts/migrate_competitions.py` (миграция/отчёт),
`backend/tests/test_competitions.py`.

## Решения владельца (2026-09-16)

- «Состав» лиги в сезоне = список команд сезона (`seasons.teams`).
- Команда в разных шоу — **разные сущности** в `teams` (свой `team_type`), связь между ними — `related_team_ids`.
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
  "stages": [ { "id", "name": "1/2 финала", "code": "1/2", "order": 3 /* бывает 2.5 */, "notes",
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
Одна строка `kind: "season"` на участника сезона и по одной `kind: "game"` на каждый результат в игре.
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
```
Индексы: `(team_id, kind, season_year)`, `(person_id, kind, season_year)`, `(slug, kind)`, `season_id`.
**Никогда не редактировать напрямую** — только через сохранение сезона.

## Синхронизация (переходный период, до этапа 3)

Публичные страницы (`SeasonDetailPage`) и старый редактор (`SeasonDataEditor`) работают с `kvn.season_data`.

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

## Данные на 2026-04 (локальная БД)
119 сезонов: ВЛ 39, Премьер 23, Первая 33, Международная 12, ВУЛ 12; 454 этапа, 1016 игр, 5127 результатов;
35 результатов без команды (18 уникальных названий, в основном без slug) — список: `GET /api/competitions/unresolved`.

## Дальше
- Этап 2: страницы команд и людей показывают участия из `participations` (вместо модуля «Список игр команды»,
  собираемого `refresh`); `memberships` (человек — команда — роль — годы — сезоны); жюри/ведущие как ссылки на людей.
- Этап 3: админ-редактор сезона на новой модели, привязка непривязанных участников; отказ от `season_data`.
- Этап 4: турниры для ИГРЫ, Звёзд на НТВ, Импровизации, Рассмеши комика (`participant_type: person`).
