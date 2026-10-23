# R13i — точечные исправления идентификаторов на копии

Дата:22.10.2026. Worktree `r5-zip-operations/humorpedia`, ветка `codex/local-page-builder`, HEAD `7678c4b8dd312e7f7d954948ee802b3a7c8e6fae`.

## Статус и границы

R13h опубликован отдельным `7678c4b`: восстановленные media и WebP MIME с документацией. [CI39844032265](https://github.com/AMnEPka/humorpedia/actions/runs/39844032265) completed/success на точном SHA; все5 jobs и три browser-сценария success. Evidence: `.cache/r13i/r13h-ci-{run,jobs}-final.json`. R13i — следующий пакет из [R13g](r13g-migration-readiness-2026-10-22.md): **Оба согласованных исправления выполнены и приняты только на изолированной копии.** Ровно2 документа изменены из25,620; API, React4 страницы и media150 PASS. Продуктовый код не менялся. R13i с документацией опубликован отдельным `ef2a704df959d37ca5a92695a1481809768a3737` в `origin/codex/local-page-builder`. [GitHub39847257115](https://github.com/AMnEPka/humorpedia/actions/runs/39847257115) completed/success на точном SHA, attempt1: все5 jobs и три browser-сценария success. Evidence `.cache/r13j/r13i-ci-{run,jobs}-final.json`.

Пользователь согласовал две конкретные операции; производная копия R13h projections подготовлена с guards и проверена. Основной checkout остаётся на main; primary Mongo/media, импорт24СМИ и VPS не изменяются. Индексация выключена. Это не полный release archive и не команда переноса.

## 1. Чужой old_id у сезона 2009

В R13g snapshot две опубликованные страницы `kvn` имеют `old_id=2540`:

| Страница | Точный `_id` | До | После на копии |
| --- | --- | --- | --- |
| `/kvn/vl-kvn/vl-2008` | string `dd6e3ba7-1234-4bd2-80a3-7e07ada543fc` | 2540 | оставить 2540 |
| `/kvn/vl-kvn/vl-2009` | ObjectId `69689b6886d41cb5cb0aa853` | 2540 | `null` |

Первичный локальный `humorbd.sql`, таблица `modx_site_content`, строка765594: resource2540 — «Сезон 2008 Высшей лиги», alias `vl-2008`, URI `kvn/vysshaya-liga/2008.html`. Это именно MODX resource ID, используемый resolver-ом, а не ID тега. [Старый сайт:2008](https://humorpedia.ru/kvn/vysshaya-liga/2008.html) вернул HTTP200, соответствующий h1 и hidden input `rid=2540`. [Путь2009](https://humorpedia.ru/kvn/vysshaya-liga/2009.html) вернул HTTP404; точного ресурса2009 Высшей лиги в проверенной таблице не найдено. Ресурс3087 — 2009 ВУЛ, к Высшей лиге не относится. Другой old_id для2009 не назначаем без первоисточника.

`backend/services/link_resolver.py:185–195` выбирает первое совпадение old_id; `load_old_id_urls:232–240` использует setdefault. При двух документах результат зависит от порядка чтения. Исправление устранило неоднозначность `[[~2540]]`, сохраняя обе страницы, UUID/ObjectId, slug/full_path, содержимое, season_data и канонические seasons. Это исправление данных, не изменение алгоритма resolver.

Evidence: `.cache/r13i/old-id-{source-rows,documents}.json`, `legacy-season-probe.json`, `legacy-{2008,2009}.html`. Только публичные content rows/HTML, исходный SQL не изменён. В существующей R13g link-review queue ключ2540 не найден; рекурсивный read-only scan всех25,620 документов производной R13h copy также не нашёл строк `[[~2540`. Это не доказательство отсутствия всех обращений извне.

## 2. Михаил Абдул-Кадыров ошибочно связан с Мадичем

Записи memberships:

- Михаил: `_id=4050fe35-5a2e-5151-9749-8a90933a44d2`, `person_name=Абдул-Кадыров Михаил`.
- Александр: `_id=93f24933-757f-5fbb-9500-1aaaf347695c`, `person_name=Александр Мадич`.
- Обе сейчас содержат `person_id=59458e72-a706-4d13-8a3e-e4f97368ed7f`; это canonical people «Александр Мадич», slug `aleksandr-madich`, old_id2409.

[Первичная страница команды](https://humorpedia.ru/kvn/team/sbornaya-vladivostoka.html) и сохранённый roster module перечисляют двух участников раздельно. [Карточка Мадича](https://humorpedia.ru/people/aleksandr-madich.html) подтверждает его собственное участие в команде. В1041 projected people отдельная карточка Михаила не найдена; новую карточку автоматически не создаём. Это ошибочное ребро, не дубликат строки состава.

Используем существующую семантику `PATCH /api/competitions/membership-links/review/{id}` action `reject`. Нового статуса `unlinked` в контракте нет.

| Поле строки Михаила | До в проекции | После на копии |
| --- | --- | --- |
| `person_id` | ID Мадича | `null` |
| `candidate_person_id` | `null` | `null` |
| `rejected_person_id` | не входит в projection | ID Мадича |
| `person_link_disabled` | false | true |
| `link_review_status` | confirmed | rejected |
| `matched_by` | manual | manual |
| `source` | manual | manual |

Строку Мадича оставить без изменений. Имя Михаила, person_slug=null, name_key, team_id, source_ref, роли, периоды и status сохранить. Запись останется в составе как текст без ссылки; ложное членство исчезнет из карьеры Мадича. Disabled=true предотвращает автоматическую привязку; редактор сохраняет возможность явно назначить правильную карточку позднее.

Проекция R13g не включает `rejected_person_id`, `reviewed_by`, `reviewed_at`, `updated_at`: их отсутствие здесь **не означает** отсутствия в полной БД. При приёмке копии используется явно помеченный тестовый редактор; audit fields записываются существующим review endpoint, не выдаются за действие реального пользователя в main. Для будущего полного переноса нужны свежие полные preimages и отдельная проверка, пользовательские audit fields нельзя молча перезаписывать.

Код: `backend/routes/memberships.py` review action, team_members и person_career; `backend/services/memberships.py` link_person/linkable_memberships_query; `frontend/src/public/components/competitions/TeamRoster.jsx` текст без person. Существующие регрессии: `backend/tests/test_membership_review.py::test_review_reject_unlinks_but_keeps_membership` и `test_person_career_uses_only_saved_person_ids`. В R13i `test_membership_review.py` и `test_memberships.py`:25 passed,0.87s,1 известный PendingDeprecationWarning python_multipart. MIME-регрессия R13h также PASS на release image. Полный backend suite1193 из R13h повторно не запускался: продуктовый код в R13i не менялся. Новые данные проверены отдельно через настоящий API, browser и offline audits.

Read-only preflight `.cache/r13i/proposal-preconditions.json`: входная копия совпала с ожидаемым SHA, все4 целевые/контрольные строки найдены по typed ID и получили hashes. Исходный SQL SHA256 `d4a2e0930ebc676aca939ad569c54bc82e7470184ca0c40ede63e9a19898cf19`. На стадии preflight поля не менялись. После согласования seed получил единственную old_id замену; далее штатный review API выполнил reject на owned Mongo.

## Выполненный согласованный план

| Шаг | Результат / проверка готовности | Модель |
| --- | --- | --- |
| [x] 1. Зафиксировать решение | Пользователь подтвердил обе точные операции на копии; выполнено, без объединений людей или глобальных remap | Sol/high |
| [x] 2. Подготовить отдельную производную копию | Вход — R13h patched SHA `3b81abc86dd255443950b37dbb2e3ff1c06171d2e319f185a31636471fa59d0b`; guards по typed ID, title/path/old_id и membership tuple. При несовпадении отказ; исходные snapshots не изменяются | Sol/high |
| [x] 3. Применить к изолированному стенду | Отдельные owned Mongo/app/network, без host ports/primary writes. `old_id=null` только у2009; reject только у строки Михаила через существующий review action | Sol/high |
| [x] 4. Проверить данные и поведение | 25,620 исходных записей сохранены; ровно2 doc changes плюс объявленные audit fields. Нулевая old_id-коллизия2540; обе season pages доступны; `[[~2540]]` ведёт только к2008. Team сохраняет обоих людей, Михаил без ссылки, Madich career без ложной строки. Прогон relation audit, релевантных API/unit и React сценария | Sol/high |
| [x] 5. Обновить приёмку | Счётчики, hashes, ограничения projected copy; подтвердить сохранение R13h media mappings, cleanup owned ресурсов и неизменность main. Commit/push R13i — по отдельному поручению | Sol/high |

Пакет не затрагивает21 неоднозначную ссылку,8 отсутствующих оригинальных season posters,111 external/embed URL и будущую demo exclude-policy. Для них остаются отдельные очереди; исходный рефакторинг R0–R12 уже реализован, текущие работы закрывают готовность данных и выпуска.

## Приёмка R13i

Утверждённая [машинная политика](r13i-identity-corrections-policy-2026-10-22.json) содержит typed IDs,4 preimage hashes, исходный SHA, разрешённые поля, границы и результат на копии. Она не является исполняемой миграцией main. Одноразовые scripts, raw copy, логи и screenshots находятся в ignored `.cache/r13i`.

- Подготовка: `node .cache/r13i/test-prepare.cjs` —4 проверки PASS: source drift, preimage drift, неверный тип ID и отказ при повторном применении. `prepare-copy.cjs` создаёт новый output, проверяет source SHA/4 preimages/25,620 rows и меняет только old_id2009. Существующий output не перезаписывается.
- Native run `c73a514dfdc44a73b5153ad320fb6dd2`: собственные UUID Mongo8.0.32/app/Nginx/network, без host ports. Serving=true только в пилоте, indexing=false. Старые media volumes и R13h recovery assets смонтированы read-only.
- Штатная авторизация тестового editor, затем `PATCH /api/competitions/membership-links/review/4050fe35-5a2e-5151-9749-8a90933a44d2` action=reject →200. Анонимный такой же запрос →401. Неверная связь воспроизведена до reject через API: обе строки указывали на Мадича, career содержал обе. После:54→54 записи команды; Михаил person=null; строка Мадича неизменна; career2→1. `linkable_memberships_query` с подходящим name_key не выбирает отклонённую строку. Все postimage fields, synthetic reviewed_by и ISO audit timestamps проверены.
- Resolver и import loader возвращают для2540 `/kvn/vl-kvn/vl-2008`. В final copy ровно одна страница с2540; обе season pages HTTP200/noindex и React h1. Прямой маршрут2009 сохраняется.
- Native export до browser/content GET сравнил все13 непустых исходных коллекций и их counts с seed (в scope15 коллекций, wiki/sections пустые в исходном snapshot): менялась только утверждённая строка reject. Итоговый independent structural diff относительно R13h копии подтвердил ровно2 изменённых документа с разрешёнными полями/audit; остальные25,618 полных projected records равны. Все104 media fields R13h сохранены. Никакие документы не удалялись, canonical seasons/9276 participations не менялись.
- Chromium:4/4 страницы200, normal React API/render без подмены ответов; раскрыт штатный collapsed roster HTML, оба разных имени сохранены, Михаил не ссылается на Мадича. На странице Мадича одна ссылка команды в блоке карьеры вместо двух. pageerrors0. Отдельно150/150 R13h media HTTP200/image MIME/SHA256/dimensions/Chromium decode, включая WebP. Frontend build R13f не менялся; новая сборка/Jest не требовались.
- **Граница team UI:** R13g projection не содержит `team.roster_import`; штатный API возвращает пустой roster_blocks, поэтому TeamDetailPage использует исходный HTML. API semantics исправленной связи проверены полностью, browser проверяет HTML fallback и карьеру. Live structured TeamRoster на полной БД не запускался; no-person branch проверен статически в TeamRoster; существующий TeamDetailPage.test.jsx содержит preview-кейс участника без target, но не заменяет live structured browser-приёмку. Supplemental fields/моки ради демонстрации не добавлялись. Перед полным переносом нужен повтор на полном release archive.
- Offline `audit-copy.py` использует существующие R13g analyzers и настоящий resolver с read-only in-memory adapter: old_id conflicts0, same-entity membership candidate groups0, findings0. Memberships4838:confirmed1440,rejected23,candidate1;9276 participations совпали с122 seasons:missing/stale/changed/duplicate0. Это не аудит всех внешних URL и не полная UX-приёмка.
- Временные writers штатно остановлены; owned DB удалена с проверкой marker; cleanup containers=[],error=null,network_removed=true,owned images удалены. Последующая проверка Docker не нашла ресурсов с label R13i.

Final copy: `.cache/r13i/copy/patched.jsonl`, SHA256 `7439abd0b81796875960d270735d3efd1f0acea2738d84dcd61b740862e58aeb`.
Исходный R13h patched SHA `3b81abc86dd255443950b37dbb2e3ff1c06171d2e319f185a31636471fa59d0b` и оба R13g source hashes неизменны.
Evidence: `.cache/r13i/copy/{prepare-acceptance,acceptance}.json`, `audits/{content-audit,relations-audit,summary}.json`, `native-pages/c73a514dfdc44a73b5153ad320fb6dd2/{result,cleanup,commands}.json`, `closed/identity-{api,browser}.json`, screenshots. Визуально выборочно просмотрены сохранённые страницы команды и карьеры; это не полный ручной UX-аудит.

Два предварительных прогона сохранены как diagnostics, не как успех: `e86e088db2a541f584a1b5935210a92f` — неверный exact locator внутри свёрнутого абзаца roster; `756591ee1368404eb25c36d129d2b2f2` —4 UI paths прошли, media404 из-за ошибочного пути recovery mount в test runner. Исправлены только harness/проверки, продуктовый код не менялся. У обоих cleanup успешен; финальная приёмка — только c73a514dfdc44a73b5153ad320fb6dd2.

Повтор: `BROWSER_BUILD_DIR=.cache/r13f/frontend-build node .cache/r13i/run-native.cjs` (переменную задать синтаксисом оболочки). Runner создаёт новый UUID, требует подготовленный seed и staging R13h, очищает только owned ресурсы. Для новой offline preparation нужен новый пустой output. `validate-final.cjs` намеренно пишет final copy exclusive-create; для повторной приёмки требуется новый output, существующие evidence не перетирать.

Финальный read-only контроль: primary clean main `ca46155a9640d4723c07b9fd1762a6e639563414`, прежние backend/frontend/Mongo container IDs и StartedAt, restarts=0; HTTP3000 и8001/api/health200. Импорт24СМИ и VPS не изменялись. R13i опубликованef2a704, GitHub39847257115 completed/success.

Следующий пункт плана: review неразрешённых внутренних ссылок R13g — сначала точный пакет194 однозначных кандидатов/21 неоднозначной ссылки с первоисточниками и проверкой на копии. Автоматическая замена по одному slug не согласована. Полный release archive, demo-policy при переносе,8 оригинальных season posters и интеграция/main/dev-sync остаются отдельными работами; VPS запрещён текущим поручением.

Продолжение: [R13j](r13j-link-repair-plan-2026-10-22.md) подготовил quiz contract diagnostic (7 корректных targets, остальные2570keys неизменны) и неприменённый88-key href proposal. Объём реализации ожидает выбора пользователя по AGENTS.md.
