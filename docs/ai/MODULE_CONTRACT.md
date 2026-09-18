# Контракт модулей страниц

Проверено 2026-09-18, этап 0 `legacy-modules-gap-plan.md`, ветка `codex/module-contract`.

Канонический реестр: `backend/models/module_contract.json`. Backend выдаёт его через
`GET /api/templates/modules/types`; frontend использует копию `frontend/src/moduleContract.json`.
После изменения реестра: `node scripts/sync-module-contract.cjs`; в CI проверяется `--check`.
`ModuleType` должен точно совпадать с реестром, неизвестные типы и aliases API отклоняет.

Все записи имеют backend-схему `PageModule`. `data` намеренно остаётся расширяемым словарём:
сохранение старых импортированных полей и метаданных важнее введения несовместимой строгой валидации
в этом этапе. Документирующие схемы `GalleryData`, `TimelineData`, `TableData`, `ParticipantsData`
и `TVAppearancesData` приведены к фактическому формату форм.

## Типы и владельцы

`content` — обычный общий renderer; `dynamic` — данные API с собственными состояниями;
`system` — маркер шаблона; `special` — отдельный компонент страницы.
В таблице имена файлов без `.jsx`; публичные страницы находятся в `frontend/src/public/pages`,
общий renderer — в `frontend/src/public/components`, редакторы — в `frontend/src/admin`.
Пустой список добавления означает поддержку существующих данных без предложения создавать legacy-блок.

| Тип | Вид | Редактор | Публичный владелец | Добавление на страницах |
|---|---|---|---|---|
| `hero_card` | content | `ModuleEditor` | ModuleRenderer | person, team, show |
| `image` | content | `ModuleEditor` | ModuleRenderer | person, team, show, article, news, page, section, city, kvn, quiz |
| `text_block` | content | `ModuleEditor` | ModuleRenderer, PersonDetailPage, TeamDetailPage, ShowDetailPage | person, team, show, article, news, page, section, city, kvn, quiz |
| `timeline` | content | `ModuleEditor` | ModuleRenderer, PersonDetailPage, TeamDetailPage, ShowDetailPage | person, team, show |
| `tags` | content | `ModuleEditor` | ModuleRenderer | person, team, show, article, news, page, section, city, kvn, quiz |
| `table` | content | `ModuleEditor` | ModuleRenderer, ShowDetailPage | person, team, show, article, page, section, city, kvn, quiz |
| `gallery` | content | `ModuleEditor` | ModuleRenderer, TeamDetailPage | person, team, show, article, news, page, section, city, kvn, quiz |
| `video` | content | `ModuleEditor` | ModuleRenderer | person, team, show, article, news, kvn, quiz |
| `quote` | content | `ModuleEditor` | ModuleRenderer | person, article, kvn, quiz |
| `poster_photo` | system | `ModuleEditor` | PersonDetailPage, TeamDetailPage, ShowDetailPage | person, team, show |
| `facts_table` | system | `ModuleEditor` | PersonDetailPage, TeamDetailPage, ShowDetailPage | person, team, show |
| `tags_cloud` | system | `ModuleEditor` | PersonDetailPage, TeamDetailPage, ShowDetailPage | person, team, show |
| `social_links` | system | `ModuleEditor` | PersonDetailPage, TeamDetailPage, ShowDetailPage | person, team, show |
| `rating_widget` | system | `ModuleEditor` | PersonDetailPage, ShowDetailPage | person, show |
| `team_members` | content | `ModuleEditor` | ModuleRenderer | team |
| `tv_appearances` | content | `ModuleEditor` | ModuleRenderer | team |
| `games_list` | content | `ModuleEditor` | ModuleRenderer | team |
| `episodes_list` | content | `ModuleEditor` | ModuleRenderer | show |
| `participants` | special | `ModuleEditor` | ShowDetailPage | show |
| `best_articles` | dynamic | `ModuleEditor` | ModuleRenderer | page, section, city |
| `interesting` | dynamic | `ModuleEditor` | ModuleRenderer | page, section, city |
| `random_page` | dynamic | `ModuleEditor` | ModuleRenderer | page, section, city |
| `quiz_questions` | special | `QuizEditPage` | QuizDetailPage | quiz |
| `quiz_results` | special | `QuizEditPage` | QuizDetailPage | quiz |
| `humor_chronicles` | dynamic | `ModuleEditor` | ModuleRenderer, PersonDetailPage | person |
| `first_league_champions` | special | `ModuleEditor` | SectionDetailPage:LeagueSeasonsPage | kvn |
| `vl_league_champions` | special | `ModuleEditor` | SectionDetailPage:LeagueSeasonsPage | kvn |
| `table_of_contents` | system | `ModuleEditor` | Page-level TOC independent of marker |  |
| `person_card` | content | `ModuleEditor` | ModuleRenderer |  |
| `related_links` | content | `ModuleEditor` | ModuleRenderer |  |
| `html` | content | `ModuleEditor` | ModuleRenderer |  |
| `divider` | content | `ModuleEditor` | ModuleRenderer |  |
| `text` | special | `ModuleEditor` | PersonDetailPage |  |
| `cast_list` | special | `ModuleEditor` | ShowDetailPage |  |
| `seasons_list` | special | `ModuleEditor` | ShowDetailPage |  |

## Форматы и совместимость

- `gallery`: `images[{url, caption, alt}]`; `video`: `url,title,caption`. Имена `image_gallery/video_embed`
  преобразуются только миграцией (`migration/parsers/base.py`), форма, API и public используют canonical имена.
  GalleryParser выдаёт `gallery`; старый ключ настройки импортёра `image_gallery` остаётся допустимым входом.
- `timeline`: `events[{year/date,title,description}]`, год может быть строкой-периодом; старые person/team
  особенности и якоря оглавлений сохранены. `table`: `headers[],rows[][],hasHeaders,sortable,description`.
- `hero_card`: `image,caption` (старое `photo` также читается); `tags`: `tags[]`.
  `team_members`: `members[{name,role,...}]`; `tv_appearances`: `items[{show,date,description,video_url}]`
  (старое `appearances` читается как fallback); `games_list`: `games[{date,opponent,league,result,video_url}]`;
  `episodes_list`: `episodes[{season,episode,title,air_date,guests[],description,video_url}]`.
- `participants`: `items[{name,person_slug,person_url,photo,facts[{title,value}]}]`, владелец — шоу.
- `best_articles`: статьи по убыванию рейтинга; `interesting`: статьи с `featured=true`;
  оба используют `title,limit` (1–20). Архив исключён сервером до пагинации, текущий URL и дубли — виджетом.
  По действующему правилу проекта draft также публичен. Это самостоятельные виджеты, не полная система
  ручных рекомендаций `related_article_ids` этапа 3.
- `random_page`: `title,content_type`; API `/random/{type}` исключает текущий slug до `$sample` и сохраняет
  поля путей вложенных шоу/команд. Поддержаны person/team/show/article/news/quiz/city.
  Если в одной коллекции есть одинаковые slug, исключаются все совпадения.
- YouTube watch/short URLs преобразуются в embed; VK embed поддерживается. Для прочих http(s) URL показывается
  внешняя ссылка на видео. Небезопасная/пустая ссылка не становится iframe.

## Специальные правила

- Sidebar-маркеры включают блок основных полей person/team/show. Данные, расположение и оформление задаёт
  шаблон страницы; старые `data.size/style/max_tags` сохраняются, но не предлагаются как работающие настройки.
  Рейтинг есть у людей и шоу; у команды пока нет такого sidebar-компонента.
- `table_of_contents` — совместимость старого маркера, не переключатель оглавления. Оглавления людей,
  команд и корня КВН создаёт шаблон независимо от маркера. Новое добавление маркера не предлагается;
  оглавление статей остаётся этапом 2. Существующие записи редактируются/сохраняются без потери data.
- Чемпионы — только страницы лиг. В KVNEditor добавление исключено на других страницах.
  `visible=false` подавляет и сам блок, и автоматическую подстановку таблицы чемпионов.
- Квизы используют полноценный QuizEditPage; q/r также имеют формы в редакторе шаблонов.
  Дополнительные контентные блоки сохраняются и показываются до начала прохождения.
- Для wiki нет публичной страницы: её шаблоны не предлагают добавлять модули до реализации публичного владельца.
- Страницы с `season_data` используют специальный SeasonDetailPage и не читают старые modules. На 2026-09-18
  в локальной БД 95 таких страниц / 1097 модулей, дублирующих структурированный сезон. Эти modules сохранены
  и показаны в KVNEditor только архивным read-only списком; `extra_modules` не вводятся. Новый текст для стадии
  хранится в `season_data.stages[].comment` и выводится перед играми; старый HTML остаётся в `notes`.
- `ModuleRenderer` не скрывает неизвестный тип: показывает диагностический блок `role=alert`.
  `null` допустим только для `visible=false`, отсутствующего модуля, явных system/special и пустых динамических хроник.

## Проверка

- `node scripts/sync-module-contract.cjs --check` — совпадение копий реестра.
- `cd backend && pytest -q tests` — enum/registry, API create/read/update, aliases, фильтры виджетов и регрессии проекта.
- `cd frontend && yarn test --watchAll=false --runInBand` — DOM редакторов и динамических виджетов,
  SSR общего/page-specific рендера, сохранность квизов и якорей, скрытые чемпионы,
  plain-text комментарий стадии и read-only архивные модули сезона.
- `cd frontend && yarn build` — production-сборка.
