# Модель данных Humorpedia (MongoDB `humorpedia`)

Pydantic-модели — `backend/models/`. Они используются для **валидации входящих запросов**, а в БД документы пишутся как `dict`
и читаются без модели — поэтому в реальных документах бывают поля, которых нет в моделях (`old_urls`, `season_data`, `jury_cards`,
`allow_empty_modules`, `id` у KVN и т.п.), и наоборот. Истину о структуре смотреть в коде роутов + в данных.

## Коллекции

| Коллекция | Модель | Роуты | Особенности |
|---|---|---|---|
| `people` | `Person` | content_people | `full_name`, `photo`, `bio`, `facts{}`+`facts_order[]`, `primary_tag`, связи `team_ids/show_ids/article_ids` |
| `teams` | `Team` | content_teams | `team_type` (kvn/liga_smeha/improv/comedy_club/other), `name`, `logo`, `aliases[]` (для сопоставления названий), `member_ids`, `old_urls[]` |
| `kvn` | `KVN` | content_kvn | иерархия: `id` (UUID, **отдельно от `_id`**), `parent_id`, `level` 0–4, `full_path`; `season_data`, `jury_cards`, `old_urls` |
| `shows` | `Show` | content_shows | иерархия `parent_id`/`child_show_ids`; `facts` = `ShowFacts` (годы, канал, ведущие…) |
| `articles` | `Article` | content_articles | `excerpt`, `cover_image`, `author_*`, `featured`, `related_*_ids` |
| `news` | `News` | content_news | `content` (HTML), `important`, `related_*_ids` |
| `quizzes` | `Quiz` | content_quizzes | вопросы и результаты — в модулях `quiz_questions` / `quiz_results` |
| `wiki` | `Wiki` | content_wiki | `content` (HTML), `has_header`, `header_facts` |
| `sections` | `Section` | sections | иерархические разделы: `full_path` (уникален), `parent_id`, `parent_path`, `level`, `order`, `in_main_menu`, `child_types` |
| `cities` | `City` | cities | `content_type="page"`, `related_person_ids/related_team_ids` (заполняются city_linking) |
| `users` | `User` | auth, users | `username`, `email`, `password_hash` (bcrypt), `role`, `permissions[]`, `oauth{vk_id, yandex_id}`, `banned` |
| `comments` | — | comments | `resource_type`+`resource_id`, `user_id`, `parent_id`, `deleted`, модерация |
| `tags` | — | tags | `name` и `slug` уникальны, `usage_count`, `type` |
| `media` | — | media | `url`, `uploaded_at`, `status` (soft delete) |
| `templates` | `PageTemplate` | templates | `name` уникально, `content_type`, `modules[]`, `is_default` |
| `cache_meta` | — | server.py middleware | `{_id: "version", v: int}` — поколение in-memory кэша для синхронизации воркеров |
| `tournaments` | `competition.py` | competitions | турнир/лига/проект: `show`, `slug`, `participant_type` (team/person), ссылка на страницу — см. COMPETITIONS.md |
| `seasons` | `SeasonUpdate` | competitions | сезон: список участников, победители, этапы → игры → результаты (ссылки на `teams._id`) — источник истины вместо `kvn.season_data` |
| `participations` | — | competitions | производная: участие в сезоне (`kind=season`), в игре (`kind=game`), роли жюри/ведущего/редактора (`kind=role`) |
| `memberships` | — | memberships | составы команд: человек (или имя + slug старого сайта) — команда — роли — годы — статус |

Индексы создаются при каждом старте в `server.py:create_indexes` — при добавлении полей для фильтрации добавлять индекс туда.

## Общие поля контента (`BaseContent`, models/base.py)

```
_id: str (UUID)            created_at / updated_at      created_by / updated_by
title, slug, content_type  status: draft | published | archived
old_id: int (ID ресурса MODX)                          seo: {meta_title, meta_description, keywords[], og_image}
tags: [str]                views, rating, votes_count, comments_count
published_at, featured
```
Даты при записи через crud обычно сохраняются ISO-строками.
`MediaFile` = `{url, alt, caption, thumbnail}`; `SocialLinks` = `{vk, telegram, youtube, instagram, website}`.

## Модули страниц (models/modules.py)

Страница = список модулей:
```json
{ "id": "uuid", "type": "text_block", "order": 0, "title": null, "visible": true, "data": { ... } }
```
`data` — произвольный dict (схемы `*Data` в modules.py — документация, строго не валидируются).

`ModuleType` (бэкенд enum — значения, не входящие в него, отклоняются при сохранении):
- универсальные: `hero_card`, `text_block {title, content(HTML)}`, `timeline {title, items[{year, month, title, description, image, link, type}]}`, `tags`, `table {columns[], rows[]}`, `gallery {items[{url, thumbnail, alt, caption}]}`, `video {url}`, `quote {text, author, source}`
- системные (сайдбар): `poster_photo`, `facts_table`, `tags_cloud`, `social_links`, `rating_widget`
- команды: `team_members`, `tv_appearances`, `games_list`
- шоу: `episodes_list`, `participants`
- статьи: `best_articles`, `interesting`, `random_page`
- квизы: `quiz_questions {questions[{id, question, image, options[{id,text,correct}], explanation}]}`, `quiz_results {results[{min_score, max_score, title, description, image}]}`
- люди: `humor_chronicles` (данные подтягиваются динамически из `/people/{id}/linked-content`)
- лиги КВН: `first_league_champions`, `vl_league_champions` (таблицы чемпионов строятся из дочерних сезонов)

Публичный `ModuleRenderer.jsx` дополнительно умеет `image`, `image_gallery`, `video_embed`, `person_card`, `related_links`, `table_of_contents`, `html`, `divider` — часть этих типов бэкенд enum не знает (расхождение). Системные модули рендерит `components/SystemModules.jsx`.

Внутренние ссылки в HTML модулей при выдаче переписываются `services/link_resolver.py` (актуальные slug/пути).

## Человек: документ в формате админки

Эталон — то, что сохраняет `PersonEditPage` через `POST/PUT /api/content/people` (модель `Person`). Данные лежат **в полях документа**, системные модули хранят только настройки вида:

```jsonc
{
  "title": "Шастун Антон", "slug": "anton-shastun", "full_name": "Антон Андреевич Шастун", "status": "published",
  "photo": {"url": "/media/imported/images/people/…jpg", "alt": "…", "caption": "", "thumbnail": "…тот же url"},
  "facts": {"Полное имя": "…", "Дата рождения": "19 апреля 1991 года", "Дата смерти": "… (82 года)"}, "facts_order": ["Полное имя", …],
  "social_links": {"vk", "telegram", "youtube", "instagram", "website"},
  "tags": [...], "primary_tag": "Антон Шастун",            // базовый тег по умолчанию — «Имя Фамилия»
  "rating": {"average": 8.94, "count": 17}, "votes_count": 17,  // как у команд (модель BaseContent.rating: float — не соответствует данным)
  "seo": {"meta_title", "meta_description", "keywords": []},
  "old_id": 116, "old_urls": ["/people/anton-shastun.html"],  // импорт: ресурс MODX и старый URL для редиректа
  "modules": [
    poster_photo {size, shape} · facts_table {title, style} · rating_widget {title, style} · tags_cloud {title, style, max_tags} · social_links {title, style},
    text_block «Биография» {title, content} · text_block «Личная жизнь» · timeline «Хронология» {title, events[{year, date, title, description}]} · text_block без заголовка (сноски)
  ]
}
```
- Публичная страница берёт фото из `photo.url` (затем устаревшие `cover_image`/`image`/`poster` — хелпер `frontend/src/utils/media.js`), факты — в порядке `facts_order`; возраст к дате рождения не добавляется, если есть факт «Дата смерти».
- **Три человека, заведённых до сентября 2026** (Дроботенко, Шастун, «Шастун и Макар»), хранятся в старом формате: `image`/`poster` строками, данные продублированы внутри `data` системных модулей, ссылки в HTML — относительные старые (`people/x.html`), в хронологии хвосты `\"`. Пересоздаются из дампа: `import_people_modx.py --ids 109 115 116 --apply --update`.

### Импорт со старого сайта (MODX)

`backend/scripts/import_people_modx.py` читает SQL-дамп MODX (`backups/idemsku8_modx2.sql`, в контейнере `/app/backups/…`) через `services/modx_dump.py` и создаёт людей **тем же кодом, что админка** (`create_person` / `update_person`), затем дописывает `old_id`, `old_urls`, рейтинг и даты.

Страница человека в MODX — шаблон 20, данные в TV: `img` (фото, `images/...`), `img_alt`, `tags` (id тегов Tagger через `||`), `config` (MIGX-секции):
| Секция MIGX | → |
|---|---|
| `info.subtitle` / `info.content` | text_block «Биография» / «Личная жизнь» |
| `info.table` | `facts` + `facts_order` |
| `info.list_social` (`vk`, `telegram`, `instagram`, `youtube`, `global`) | `social_links` (`global` → `website`) |
| `timeline.list_triple` (`title`, `subtitle` = годы, `content`) | timeline |
| `text` | text_block без заголовка |
| `tags`, `table_of_contents`, `popular_articles`, `ad_*` | не переносятся (выводятся автоматически / не нужны) |

`pagetitle` → `title`, `longtitle` → `full_name`, `alias` → `slug`, `description` → `seo.meta_description`, `keywords` → `seo.keywords`, `rating`/`votes` → рейтинг.
HTML: сущности раскрываются (кроме `&lt; &gt; &amp; &quot;`), пустые абзацы в конце убираются, ссылки переводятся на новый сайт (`services/modx_content.LinkMapper`): ресурс MODX по uri/`[[~id]]` → `/people/{alias}` (шаблон 20), `/kvn/teams/{alias}` (21); иначе паттерны `routes/redirects._try_pattern_redirect`; иначе абсолютный старый путь (его разрешит поиск редиректов, когда страница появится). Картинки `images/...` → `/media/imported/images/...`.

## Иерархия КВН

```
kvn                                   level 0, full_path "kvn"
├── vl-kvn        Высшая лига          full_path "kvn/vl-kvn"
│   ├── vl-2009   сезон (season_data)  "kvn/vl-kvn/vl-2009"
│   └── (публичный маршрут /kvn/vl-kvn/vl-jury → JuryStatsPage, данные из /content/kvn/jury-stats)
├── premier-liga  Премьер-лига         сезоны pl-YYYY
├── 1l-kvn        Первая лига
├── ml-kvn        Международная (с 2014; сезоны ранее — ошибка данных, фильтруются)
├── vul
└── league        обзор центральных лиг "kvn/league"
    └── lampa, asia, povolzhye, neva, ural, msl, start, trempel, southwest, tikhookeanskaya, krasnodarskaya-liga
                  "kvn/league/lampa" … — тексты в content/leagues/*.md
```
- `parent_id` в новых документах = `id` родителя (UUID); у старых может совпадать с `_id`. Всегда искать обоими способами.
- `full_path` — **источник истины для лиги** (в коде `season_data.league_slug` перепроверяется по `full_path`).
- Команды КВН живут в отдельной коллекции `teams`, публичный URL `/kvn/teams/{slug}`.

## `season_data` (документ сезона в `kvn`)

> С этапа 1 источник истины — коллекция `seasons` (docs/ai/COMPETITIONS.md); `season_data` синхронизируется с ней автоматически и остаётся форматом для публичной страницы и старого редактора.

Формируется `migration/kvn/process_seasons.py` (парсинг HTML MODX) и редактируется в `SeasonDataEditor.jsx`.
Подробная схема парсера — `migration/kvn/README_SEASONS.md`.

```jsonc
{
  "league_slug": "vl-kvn",          // может отсутствовать у старых сезонов → берётся из full_path
  "league_name": "Высшая лига",
  "year": 2009,                     // бывает строкой — приводить int()
  "season_number": 0,
  "intro_html": "", "description": "",
  "winners":   [{ "slug": "...", "name": "...", "city": "..." }],   // или старый формат: ["slug"]
  "all_teams": [ ... ],
  "prev_season": "vl-2008", "next_season": "vl-2010",              // дописываются при выдаче by-path
  "metadata": { ... },              // редакторы, ведущий и т.п.
  "stages": [
    {
      "name": "1/8 финала", "order": 1,
      "additional_teams": ["slug"], "additional_notes": "", "notes": "",
      "games": [
        {
          "id": "...", "name": "Первая 1/8 финала", "order": 1,
          "date": "2009-02-15", "host": "...", "jury": ["Имя", ...],
          "contests": ["Приветствие", "Разминка", "СТЭМ"],
          "teams": [
            { "team_slug": "...", "team_name": "...", "place": 1,
              "scores": { "Приветствие": 5.0, ... }, "total": 14.5,
              "passed": true, "is_winner": false, "is_additional": false }
          ]
        }
      ]
    }
  ]
}
```
Кто читает `season_data`:
- `content_teams._get_team_league_results / _get_team_all_results` → авто-модуль «Список игр команды» (и таблица результатов в Высшей лиге);
- `content_kvn.get_kvn_jury_stats` → статистика жюри;
- `content_kvn.find_adjacent_seasons` → навигация prev/next;
- `update_team_slug_in_seasons / update_team_name_in_seasons` → при переименовании команды правят `team_slug`/`team_name` во всех сезонах;
- `routes/redirects.auto_populate_old_urls`.

`jury_cards` (на странице сезона/лиги): `{ "<Имя члена жюри>": { "photo": MediaFile, "text": "..." } }`.

## Пользователи и роли

`UserRole`: `user`, `editor`, `moderator`, `admin` (см. models/user.py). `AuthProvider`: `email`, `vk`, `yandex`. Права: `admin` — всё; `editor` — запись контента, шаблоны, медиа; `moderator` — модерация комментариев, медиа; `user` — комментарии и лайки.
Проверки ролей — зависимости `backend/utils/auth.py` (см. API.md). Первый админ — из `ADMIN_EMAIL`/`ADMIN_PASSWORD` или `init_admin.py`. Забаненные (`banned`) и неактивные (`active: false`) считаются неавторизованными.

## Кэш и счётчики (in-memory, на процесс)

`services/cache.py` — TTL: kvn_pages 5 мин (500), kvn_children 5 мин, teams 5 мин, team_lists 2 мин, redirects 30 мин (2000), search 1 мин, плюс resolved_html и breadcrumbs.
`services/views_counter.py` — просмотры копятся в памяти и раз в 30 с пишутся `$inc views`.
