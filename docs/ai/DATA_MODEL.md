# Модель данных Humorpedia (MongoDB `humorpedia`)

Pydantic-модели — `backend/models/`. Они используются для **валидации входящих запросов**, а в БД документы пишутся как `dict`
и читаются без модели — поэтому в реальных документах бывают поля, которых нет в моделях (`old_urls`, `season_data`, `jury_cards`,
`allow_empty_modules`, `id` у KVN и т.п.), и наоборот. Истину о структуре смотреть в коде роутов + в данных.

## Коллекции

| Коллекция | Модель | Роуты | Особенности |
|---|---|---|---|
| `people` | `Person` | content_people | `full_name`, `photo`, `bio`, `facts{}`+`facts_order[]`, `primary_tag`, `foreign_agent`, связи `team_ids/show_ids/article_ids` |
| `teams` | `Team` | content_teams | команды КВН и команды шоу: `show_id` (пусто у КВН), `full_path` (адрес команды шоу), `team_type` («kvn» или slug корневого шоу), `name`, `logo`, `aliases[]` (для сопоставления названий), `member_ids`, `old_urls[]` — см. «Команды шоу» |
| `kvn` | `KVN` | content_kvn | иерархия: `id` (UUID, **отдельно от `_id`**), `parent_id`, `level` 0–4, `full_path`; `season_data`, `jury_cards`, `old_urls` |
| `shows` | `Show` | content_shows | `facts{}`+`facts_order[]`, `social_links`, `poster` (MediaFile); иерархия: `parent_id` (= `_id` родителя), `full_path` (уникален), `level`, `order` — см. «Шоу» |
| `articles` | `Article` | content_articles | `excerpt`, `cover_image`, `author_*`, `featured`, `related_*_ids` |
| `news` | `News` | content_news | `content` (HTML), `important`, явные связи `related_person_ids`, `related_team_ids`, `related_show_ids`, `related_article_ids` |
| `quizzes` | `Quiz` | content_quizzes | вопросы и результаты — в модулях `quiz_questions` / `quiz_results` |
| `wiki` | `Wiki` | content_wiki | `content` (HTML), `has_header`, `header_facts` |
| `sections` | `Section` | sections | иерархические разделы: `full_path` (уникален), `parent_id`, `parent_path`, `level`, `order`, `in_main_menu`, `child_types` |
| `cities` | `City` | cities | `content_type="page"`, `aliases[]`; `related_person_ids` — редакционная подборка известных людей, `related_team_ids` — команды со страницами, `related_team_mentions` — команды из дампа без страницы |
| `users` | `User` | auth, users | `username`, `email`, `password_hash` (bcrypt), `role`, `permissions[]`, `oauth{vk_id, yandex_id}`, `banned` |
| `comments` | — | comments | `resource_type`+`resource_id`, `user_id`, `parent_id`, `deleted`, модерация |
| `rating_baselines` | — | ratings | неизменяемая взвешенная база старого рейтинга: `entity_type/entity_id`, `sum`, `count`, `legacy_average`; один документ на страницу |
| `rating_votes` | — | ratings | новые оценки 1–10; один документ на `(entity_type, entity_id, voter_hash)`, повторная оценка заменяет `score` |
| `polls` | `Poll` | polls | вопрос, 2–20 вариантов, `draft/published/archived`, анонимные `historical_votes`, политика показа результата |
| `poll_votes` | — | polls | один новый голос на `(poll_id, user_id)`; детерминированный `_id`, индекс пары unique, результаты агрегируются при чтении |
| `tags` | — | tags | `name` и `slug` уникальны, `usage_count`, `type` |
| `media` | — | media | `url`, `uploaded_at`, `status` (soft delete) |
| `templates` | `PageTemplate` | templates | `name` уникально, `content_type`, `modules[]`, `is_default` |
| `cache_meta` | — | server.py middleware | `{_id: "version", v: int}` — поколение in-memory кэша для синхронизации воркеров |
| `site_settings` | `RelatedNewsSettings` | related_news | глобальные настройки; документ `_id="related_news"` |
| `tournaments` | `competition.py` | competitions | турнир/лига/проект: `show`, `slug`, `participant_type` (team/person), ссылка на страницу — см. COMPETITIONS.md |
| `seasons` | `SeasonUpdate` | competitions | сезон: список участников, победители, этапы → игры → результаты (ссылки на `teams._id`) — источник истины вместо `kvn.season_data` |
| `participations` | — | competitions | производная: участие в сезоне (`kind=season`), в игре (`kind=game`), роли жюри/ведущего/редактора (`kind=role`) |
| `memberships` | — | memberships | составы команд: человек (или имя + slug старого сайта) — команда — роли — годы; `candidate_person_id` и `link_review_status` для проверки сомнительных связей |
| `show_appearances` | — | show_appearances | варианты участия человека в согласованных шоу: `person_id/show_id`, состав, достижение, источник и ручные решения — см. SHOW_APPEARANCES.md |

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
На публичном сайте `draft` используется наравне с `published`; статус сохраняется как редакционная метка.
Из ссылок, поиска и связанных блоков исключается только `archived`.

## Рейтинги

Рейтинг доступен для `articles`, `people`, `teams` и `shows`. Исторические поля `rating` и `votes_count` остаются
в документах контента только как источник миграции. `scripts/migrate_ratings.py` переносит их в `rating_baselines`
(dry-run по умолчанию, запись с `--apply`); для объектного `rating` поле `rating.count` считается достовернее дублирующего
`votes_count`. Итоговое среднее вычисляется при чтении как `(baseline.sum + сумма новых score) / (baseline.count + число новых голосов)`.

Анонимная cookie не хранится в БД: сервер проверяет её HMAC-подпись и сохраняет только необратимый `voter_hash`.
Детерминированный `_id` голосования и unique-индекс делают повторный или конкурентный запрос идемпотентным.
Точное итоговое количество голосов наружу не отдаётся — API возвращает только публичную веху.

## Модули страниц (models/modules.py)

Страница = список модулей:
```json
{ "id": "uuid", "type": "text_block", "order": 0, "title": null, "visible": true, "data": { ... } }
```
`data` — произвольный dict (схемы `*Data` в modules.py — документация, строго не валидируются).
Исключение: у модуля `poll` канонически требуется `data.poll_id`, ссылающийся на `polls._id`.

`ModuleType` (бэкенд enum — значения, не входящие в него, отклоняются при сохранении):
- универсальные: `hero_card`, `text_block {title, content(HTML), collapsed?}`, `timeline {title, events[{year, date, title, description}]}`, `tags`, `table {title, description?, headers[], rows[][], hasHeaders, sortable?, collapsed?}`, `gallery {images[{url, thumbnail, alt, caption}]}`, `image {url, caption?}`, `video {url}`, `quote {text, author, source}`
- системные (сайдбар): `poster_photo`, `facts_table`, `tags_cloud`, `social_links`, `rating_widget`
- команды: `team_members`, `tv_appearances`, `games_list`
- шоу: `episodes_list`, `participants`
- статьи: `best_articles`, `interesting`, `random_page`
- квизы: `quiz_questions {questions[{id, question, image, options[{id,text,correct}], explanation}]}`, `quiz_results {results[{min_score, max_score, title, description, image}]}`
- лиги КВН: `first_league_champions`, `vl_league_champions` (таблицы чемпионов строятся из дочерних сезонов)

Канонический реестр и полная таблица владельцев: [MODULE_CONTRACT.md](MODULE_CONTRACT.md).
`gallery` хранит `images[]`, `video` — `url`; aliases `image_gallery/video_embed` принимаются только на входе миграции.
Backend enum также принимает существующие `person_card`, `related_links`, `table_of_contents`, `html`, `divider`,
`text`, `cast_list`, `seasons_list`. Общий renderer обслуживает контент; специальные страницы и sidebar-маркеры
имеют явных владельцев. Неизвестный публичный тип даёт диагностический блок вместо молчаливого исчезновения.
`poll` доступен в статьях и новостях; определение и голоса не дублируются внутри документа страницы.

### Свежие связанные новости

`news.related_person_ids`, `related_team_ids` и `related_show_ids` — единственный источник блока «Свежие новости».
Он не является `PageModule` и не записывается в документы страниц: frontend вставляет блок после первого видимого
контентного блока, backend применяет `site_settings._id="related_news"`, срок свежести и лимит не выше трёх.
По общему правилу публичности участвуют `draft` и `published`; исключается только `archived`.
`scripts/migrate_related_news.py` удаляет старые HTML-хвосты `<h3|h4>Новости</...>` и маркеры
`humor_chronicles`, предварительно перенося разрешённые ссылки в структурированные связи. Скрипт идемпотентен и
по умолчанию работает как dry-run.

### Ссылки в контенте

**В данных** внутренние ссылки хранятся абсолютными адресами нового сайта, как их вставляет редактор админки:
`/people/{slug}`, `/kvn/teams/{slug}`, `/kvn/vl-kvn/vl-2015`, `/city/{slug}`, `/shows/…`, `/shows/{шоу}/teams/{slug}`.
Ссылка может указывать на страницу, которой ещё нет, — это нормально. Для разделов без новой структуры (`proekty/…`) хранится
старый путь (`/proekty/standup`); когда страница появится со старым адресом в `old_urls`, ссылка заработает.

**При выдаче на сайт** (`services/link_resolver.py`, публичные GET людей/команд/шоу/КВН, статей, новостей и `by-path`) все ссылки ответа
проверяются пачкой: адрес нового сайта → документ по slug/full_path; `[[~id]]` → `old_id`; старый путь → `old_urls`;
затем паттерны `routes/redirects._try_pattern_redirect`. Найдена неархивная страница — актуальный адрес; нет
(или страница архивирована) — **ссылка выводится текстом** и оживёт сама, когда страница появится (кэш сбрасывается при записи).
Обрабатываются все строки в `modules`, `facts`, `season_data`, `jury_cards`.

**Админка читает документы с `?raw=true`** (`frontend/src/admin/utils/api.js`: getPerson/getTeam/getShow/getKvn/getArticle/getNews/getCity) — иначе
при сохранении ссылки на отсутствующие страницы превратились бы в текст навсегда. Новый эндпоинт чтения документа
для редактирования — тоже с `raw`.

## Город

Импорт — `scripts/import_cities_modx.py` (`--list`, `--ids`, `--slugs`, `--all`, dry-run по умолчанию,
`--apply`, `--update`). `services/modx_cities.py` переносит описание, постер, факты с порядком, текстовые модули,
теги, рейтинг, `old_id/old_urls` и даты. `related_person_ids` не строится по месту рождения: импортёр берёт
редакционный список ссылок из блока «Известные комики» старой страницы и оставляет только существующие
неархивные страницы людей. После импорта список редактируется вручную в админке города. Повторный
`--update` сохраняет ручную подборку людей; заменить её данными дампа можно только с `--update-relations`.
Старые текстовые разделы со списками людей и команд при импорте удаляются: эти сущности показываются один
раз карточками в основном потоке городской страницы. `related_team_ids` при каждом импорте полностью
пересобирается из всех неархивных команд КВН и шоу с подходящим полем `facts["Город"]`, прямых ссылок
старой городской статьи и однозначных совпадений старого названия с `name/title/aliases`. Упомянутые в старых списках команды без страницы сохраняются в
`related_team_mentions` и показываются карточками без ссылки, поэтому при очистке текста названия не теряются.
Каждая карточка подписана «Команда КВН» или «Команда шоу «…»»; статус `draft` не мешает ссылке.

`city_linking.py` автоматически обновляет только команды. Составные значения поля «Город» разбираются на
отдельные точные названия; поиск по подстроке запрещён (`Омск` не совпадает с `Томск`, `Киров` — с
`Кирово-Чепецк`). Исторические названия задаются в `aliases[]`, например Ленинград у Санкт-Петербурга.

Перенесённый раньше контент (команды, КВН, шоу) переведён на новые адреса `scripts/fix_legacy_links.py`
(переписывает только href/src, повторный запуск безопасен).

## Человек: документ в формате админки

Эталон — то, что сохраняет `PersonEditPage` через `POST/PUT /api/content/people` (модель `Person`). Данные лежат **в полях документа**, системные модули хранят только настройки вида:

```jsonc
{
  "title": "Шастун Антон", "slug": "anton-shastun", "full_name": "Антон Андреевич Шастун", "status": "published",
  "foreign_agent": false, // при true звёздочка и стандартное пояснение добавляются только в публичном ответе
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

`foreign_agent` — центральный признак статуса. В сохранённых `title`, `full_name` и HTML звёздочку не добавляют.
`services/foreign_agent_notices.py` помечает ссылки `/people/{slug}` при публичной выдаче человека, статьи или новости и
возвращает `foreign_agent_notice=true`; фронтенд выводит одно стандартное пояснение. `?raw=true` возвращает исходные данные
без маркеров, поэтому админка не сохраняет сгенерированную разметку обратно.
- Публичная страница берёт фото из `photo.url` (затем устаревшие `cover_image`/`image`/`poster` — хелпер `frontend/src/utils/media.js`), факты — в порядке `facts_order`; возраст к дате рождения не добавляется, если есть факт «Дата смерти».
- Все люди старого сайта (1039 опубликованных) перенесены 2026-09-16 этим форматом; при `--update` у существующих записей удаляются поля вне модели `Person` и дописываются её значения по умолчанию.
- Базовый тег — «Имя Фамилия»; если занят тёзкой — полное имя, затем «Имя Фамилия (slug)» (так у двух тёзок).

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
| `popular_articles`, `related_articles` | не создают модули: общий `/api/recommendations` строит «Читайте также» динамически по `site_settings._id=recommendations` |
| `voting` | преобразуется в `poll` с детерминированным `legacy-poll-{old_id}`; определения импортирует отдельный dry-run/apply-скрипт |

`pagetitle` → `title`, `longtitle` → `full_name`, `alias` → `slug`, `description` → `seo.meta_description`, `keywords` → `seo.keywords`, `rating`/`votes` → рейтинг.
HTML: сущности раскрываются (кроме `&lt; &gt; &amp; &quot;`), пустые абзацы в конце убираются, ссылки переводятся на новый сайт (`services/modx_content.LinkMapper`): ресурс MODX по uri/`[[~id]]` → адрес уже перенесённой страницы по `old_id` (любая коллекция), иначе `/people/{alias}` (шаблон 20), `/kvn/teams/{alias}` (21); иначе паттерны `routes/redirects._try_pattern_redirect`; иначе абсолютный старый путь (его разрешит поиск редиректов, когда страница появится). Картинки `images/...` → `/media/imported/images/...`.

## Статьи и новости

Источник — прямые дочерние ресурсы разделов MODX: статьи `parent=29`, `template=13`; новости `parent=14`, `template=7`.
Импорт выполняет `backend/scripts/import_articles_news_modx.py` через обычные `create_*` / `update_*` роуты. По умолчанию
берутся только опубликованные записи; `--include-unpublished` включает черновики, `--update` повторно синхронизирует уже
перенесённые записи. `old_id` имеет sparse unique index, старые адреса сохраняются в `old_urls`.

- `pagetitle` → `title`, `longtitle` → `seo.meta_title`, `description` → `excerpt` и `seo.meta_description`, `popular` →
  `featured` у статьи / `important` у новости, `rating` и `votes` сохраняются.
- MIGX-секции `text`/`table` → `text_block`, `quote` → `quote`; служебные рекламные, навигационные и автоматически
  строящиеся блоки не переносятся. У новости поле `content` собирается из текстовых модулей для совместимости с текущей моделью.
- У статьи `preview` — обложка карточки, `img` — верхнее изображение материала; если они различаются, `img` становится
  первым модулем `image`. Детальная страница использует этот первый модуль как шапку и не выводит его повторно; карточка читает
  `cover_image.url`. Значение без расширения изображения не считается путём к файлу.
- Ссылки переводятся на новые адреса; ссылки `/people/{slug}` и однозначные теги заполняют `related_person_ids`.
  `createdby` — технический пользователь MODX, а не публичное авторство, поэтому `author_name` по нему не заполняется.

На 2026-09-17 перенесены все опубликованные материалы: 66 статей и 1008 новостей. Два черновика статей (`old_id` 2634,
2963) и один черновик новости (`old_id` 3750) оставлены в дампе. Старые комментарии не переносились: 195 комментариев к
опубликованным статьям и 859 к новостям требуют отдельного решения по пользователям, приватности и цепочкам ответов.
Все 25 отсутствовавших файлов статей и новостей восстановлены 2026-09-17 скриптом
`backend/scripts/restore_article_media_modx.py`: 12 загружены со старого сайта, 12 скопированы из media-volume под исправленными
кириллическими именами, один phpThumb-кэш заменён на уже имевшийся исходный JPEG. Повторная проверка article+news даёт 0
отсутствующих файлов. Четыре старых внутренних адреса без целевой страницы импорт сообщает в dry-run и не подменяет.

## Квизы

Источник — прямые дочерние ресурсы раздела MODX `parent=31`, `template=16`. Импорт выполняет
`backend/scripts/import_quizzes_modx.py` через обычные `create_quiz` / `update_quiz`; по умолчанию команда является dry-run,
`--all --apply` переносит опубликованные ресурсы, `--update` повторно синхронизирует существующие.

- TV `quiz_questions` содержит MIGX-вопросы; поле `answers` каждого вопроса — вложенный MIGX JSON. Оно преобразуется в
  `quiz_questions {questions[{id, type, question, image, options[{id,text,correct}], success_explanation, error_explanation}]}`.
- TV `quiz_final` берётся у квиза, а при отсутствии — у родительского раздела; диапазоны результата ограничиваются фактическим
  числом вопросов и сохраняются в `quiz_results`.
- `questions_count` материализуется в документе для списка, но при создании и изменении всегда вычисляется из модуля вопросов.
- Старый URI сохраняется в `old_urls`; `/quiz/{slug}.html` разрешается в `/quizzes/{slug}`. Ссылки в пояснениях переводятся на
  страницы нового сайта, включая старые относительные ссылки на города.
- Обложка из TV `img` хранится как `cover_image`; отсутствующие файлы восстанавливает
  `backend/scripts/restore_quiz_media_modx.py`, который допускает запись только внутрь `media/imported` и проверяет изображение.

На 2026-09-17 перенесены 11 опубликованных квизов и 160 вопросов. Незавершённый черновик `Humorquiz #5` (`old_id=3150`,
6 вопросов) оставлен в дампе. Публичная карточка и стартовая страница читают `cover_image` и вписывают изображение в контейнер;
при отсутствии обложки используется стабильная заглушка.

## Шоу

Документ — как сохраняет `ShowEditPage` (модель `Show`): `title`, `name`, `slug`, `poster` {url, alt, caption, thumbnail},
`facts` (свободные «Статус шоу», «Дата премьеры», … — HTML в значениях допустим) + `facts_order`, `social_links`,
`description`, `tags`, `seo`, модули: 5 системных (как у людей) + `text_block` / `timeline` / `participants`.
Поля импорта: `old_id`, `old_urls`, `rating {average, count}`, `votes_count`, даты.

**Иерархия**: сезон, подпроект или раздел — дочернее шоу. `parent_id` = `_id` родителя, `full_path` = путь родителя + "/" + slug,
адрес `/shows/{full_path}`, `order` — порядок среди соседей. slug уникален среди соседей (у разных шоу бывает `season1`),
уникален `full_path` (индекс). При смене slug/родителя пути потомков пересчитываются; шоу с дочерними страницами не удаляется.
`GET /content/shows/by-path/{path}` отдаёт шоу с `children` (неархивные, по `order`) и `breadcrumbs`.

Модуль `participants`: `{title, items: [{name, person_slug, photo (URL), facts: [{title, value}]}]}` — карточки участников
(на старом сайте `people_cards`), редактор в админке, рендер на странице шоу.

Связи «человек ↔ шоу» не записываются в модули страниц. Их строит коллекция
`show_appearances`: автоматический вариант хранит источник и доказательство, редактор может
связать существующего человека, выбрать основной состав, исправить достижение или исключить
вариант. При публичной выдаче на странице человека остаётся одна подпись на шоу без перечисления
сезонов; на странице шоу ссылка встраивается только в уже существующую карточку участника.
Для команды КВН отдельные данные проектов не материализуются: публичная выдача проходит от
`memberships.person_id` к индивидуальным `show_appearances` без `team_id` и группирует результат
по шоу; командные участия остаются в отдельном блоке «Команда в других шоу». Текстовый модуль
«Участие членов команды в других проектах» хранит только ручное редакционное дополнение и
показывается вместе с вычисленными связями, не заменяя их.

### Импорт шоу со старого сайта

`scripts/import_shows_modx.py` (+ `services/modx_shows.py`): раздел «Шоу» MODX (uri `show/`, 439 страниц) — шаблоны «Шоу» и «Вики»,
в т.ч. вики-страницы верхнего уровня («Большое шоу», «Что было дальше?», Comedy Баттл, Medium Quality). Команды шоу
(шаблон «Команда» и страницы внутри «Команды …») — не шоу, переносятся в `teams` (см. «Команды шоу»); страница-список
«Команды …» получает slug `teams` (`/shows/liga-gorodov/teams`).
- slug = последний сегмент **старого адреса** (не alias: `improv-teams/` при alias `improv-kom`); путь — по цепочке родителей.
- заголовок = `longtitle` или `pagetitle` («ИК» → «Импровизация. Команды»).
- **команды шоу не импортируются как шоу**: шаблон «Команда», страницы внутри «Команды …», вики-страницы с фактом «Капитан» или «Город» + «Год основания» (команды Лиги Смеха, Импровизации).
- текст каждой секции разбирается как у Убойной лиги (`modx_shows.text_blocks`): спойлеры `<details>` на своих местах → свёрнутые блоки (одна таблица `table_sort` → сортируемая таблица), длинный текст без заголовка с ≥2 h3 → блоки по разделам, таблицы очищаются от оформления Excel/Word (победители `green_table` подсвечены), подсветка поиска MODX `<span class="highlight">` снимается. Сворачивается только то, что было спойлером на старом сайте.
- секции: `info` (факты, соцсети, subtitle/content), `text` (заголовок = название страницы не повторяется; блок «Заголовок + ...»
  отдаёт заголовок следующему блоку), `table` → text_block, `timeline`, `people_cards` → `participants`;
  строка навигации «< пред. сезон … след. >» в начале текста убирается.
- существующее шоу находится по `old_id`, затем по адресу, у корневых — по slug/alias старого импорта; `--update` пересоздаёт с тем же `_id`.
- `--tree` — вместе с подстраницами (родитель раньше детей), `--all` — весь раздел, `--publish ID` — опубликовать неопубликованное на старом сайте.
- 2026-09-16 перенесён весь раздел: 257 страниц шоу (все с `old_id`), черновиками — 4 неопубликованные на старом сайте («Плохие песни» ч. 9, «Зона комфорта», Roast Battle и его сезон); «Лига Смеха» и «Русские не смеются» опубликованы по решению владельца.

Статус переноса и решения владельца — память проекта / KNOWN_ISSUES.

### Команды шоу

Команда в разных шоу — разные сущности (у «Союза» есть страница КВН и страница «Звёзд»). Код — `services/show_teams.py`.
- **Команда КВН**: `show_id` пустой, адрес `/kvn/teams/{slug}`, slug уникален среди команд КВН.
- **Команда шоу**: `show_id` = `_id` шоу, `full_path` = `{full_path шоу}/teams/{slug}`, адрес `/shows/{full_path}`,
  `team_type` = slug корневого шоу (фильтр списка); slug уникален в пределах шоу (индекс `(show_id, slug)`), адрес
  не может совпадать со страницей шоу. При смене адреса шоу адреса его команд пересчитываются; шоу с командами не удаляется.
- Адрес строит `team_url(doc)` (нужны `slug`, `show_id`, `full_path`; бэкенд отдаёт готовые `url` и `show: {id, title, full_path}`
  в списках, поиске, карьере человека, командах города), на фронте — `utils/teams.js` (`teamUrl`, `teamSubtitle`).
- Поиск по одному slug (`GET /teams/{slug}`, составы, участия, сезоны КВН, массовые операции) — **только среди команд КВН**
  (`kvn_team_query`); команду шоу ищут по `_id` или по адресу (`GET /teams/by-path/{шоу}/teams/{slug}`).
- Страница (`TeamDetailPage` из `ShowDetailPage` по адресу `…/teams/{slug}`): под названием подпись «Команда шоу «…»»,
  хлебные крошки «Шоу → шоу → Команды …», заголовок вкладки «Имя — команда шоу «…»»; в поиске — та же подпись.
- У команд шоу при создании/сохранении **не** добавляются заготовки КВН (факты «Год основания»/«Капитан», вступление,
  пустые «Состав»/«История», таймлайн) и не удаляются таблицы игр — только системные модули.
- Основной тег — название; если занят другой командой или человеком — «Название (Шоу)» (импорт).

**Импорт** — `scripts/import_show_teams_modx.py` (+ `services/modx_show_teams.py`), шоу должно быть перенесено раньше:
- страницы команд: внутри раздела «Шоу», не шоу; «Шаблон команды …» пропускается. slug — последний сегмент старого адреса.
- название без пометки шоу в скобках («Это они (ЛГ)» → «Это они»: пометки — название шоу и «Команды X» родителя).
- факт «Состав» (Импровизация. Команды) и секция «Состав» (Звёзды) → текстовый блок «Состав команды» (из него строятся составы
  `memberships`); строки с одними именами в начале текста (ИГРА) → «Состав команды».
- секция без заголовка (или с заголовком-названием команды/города), начинающаяся с подзаголовка, делится по подзаголовкам,
  если это не продолжение предыдущего раздела (в нём уже есть подзаголовки того же уровня); остальной текст без заголовка
  (таблицы игр, «Второй сезон») дописывается в предыдущий раздел; скрытые секции (пустые таймлайны) не переносятся.
- ссылки: адреса команд шоу строятся для любых ссылок (`modx_show_teams.link_builders` — используют и импорт людей/шоу,
  и `fix_legacy_links`); переехавшие страницы (`igra/team/soyuz.html` → «Звёзды») находятся по последнему сегменту.
- в фактах перенос строки `<br>`/абзац → запятая («Победа (2019в), Победа (2019о)»), внутри фразы («19 апреля<br>1991 года») — пробел.
- 2026-09-17 перенесены все 181 команда: Импровизация. Команды 56, Лига Городов 89, Звёзды 15, ИГРА 11, Лига Смеха 10
  (на старом сайте черновики, опубликованы по решению владельца); из «Состава команды» — 951 запись составов (452 со страницей человека).

**Свёрнутые блоки и сортируемые таблицы** (для длинных страниц): `text_block.collapsed` и `table.collapsed` — блок свёрнут,
раскрывается по клику на заголовок (содержимое монтируется при первом раскрытии); `table.sortable` — сортировка по клику
на заголовок столбца (числа как числа, крупные целые выводятся с разрядами); `table.description` — пояснение над таблицей.
Переключатели — в редакторе модуля в админке; рендер — `ShowDetailPage` и общий `ModuleRenderer` (`public/components/ContentTable.jsx`).

**Страницы с уникальной структурой** — обработчики в `modx_shows.SPECIAL_PAGES` (id ресурса MODX → функция над модулями после
общего разбора). Помощники для длинных страниц — `modx_content`: `split_by_headings` (разделы h3), `extract_details` (спойлеры),
`table_rows` (HTML-таблица → заголовки и строки), `clean_office_tables` (таблицы из Excel: убрать оформление, оставить colspan/rowspan,
клетки-победители `id="green_table"` → `<mark>` зелёного цвета — редактор админки его поддерживает).
- **Убойная лига** (1628): текст разделён по h3 на 7 блоков; спойлеры «Подробная статистика участников» (48 строк) и
  «Статистика смешанных дуэтов» (45) → свёрнутые сортируемые таблицы; 125 таблиц выпусков → три свёрнутых блока по сезонам
  (выпуски 1–14, 15–86, 87–125, границы — из раздела «Деление на сезоны»); сноска — отдельным блоком.

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
- Команды КВН живут в отдельной коллекции `teams`, публичный URL `/kvn/teams/{slug}` (команды шоу — там же, см. «Команды шоу»).

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
      "comment": "Обычный текст перед сеткой игр", // без HTML, необязательно
      "additional_teams": ["slug"], "additional_notes": "", "notes": "", // notes — совместимый старый HTML
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

Страница с `season_data` — специальный шаблон: её старые `modules` не рендерятся публично и доступны в админке
только как архивный список. Полноценные `extra_modules` не используются. Новый редакционный комментарий стадии
хранится в `stages[].comment`; `stages[].notes` сохраняет прежнюю семантику HTML и не переиспользуется.

`jury_cards` (на странице сезона/лиги): `{ "<Имя члена жюри>": { "photo": MediaFile, "text": "..." } }`.

## Пользователи и роли

`UserRole`: `user`, `editor`, `moderator`, `admin` (см. models/user.py). `AuthProvider`: `email`, `vk`, `yandex`. Права: `admin` — всё; `editor` — запись контента, шаблоны, медиа; `moderator` — модерация комментариев, медиа; `user` — комментарии и лайки.
Проверки ролей — зависимости `backend/utils/auth.py` (см. API.md). Первый админ — из `ADMIN_EMAIL`/`ADMIN_PASSWORD` или `init_admin.py`. Забаненные (`banned`) и неактивные (`active: false`) считаются неавторизованными.

## Кэш и счётчики (in-memory, на процесс)

`services/cache.py` — TTL: kvn_pages 5 мин (500), kvn_children 5 мин, teams 5 мин, team_lists 2 мин, redirects 30 мин (2000), search 1 мин, плюс resolved_html и breadcrumbs.
`services/views_counter.py` — просмотры копятся в памяти и раз в 30 с пишутся `$inc views`.
