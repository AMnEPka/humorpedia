# R13o — восстановление девяти обычных лиг КВН на копии

> Исполнителю: после явного согласования использовать `superpowers:executing-plans`; до этого разрешено только read-only исследование.

**Дата:**23.10.2026. **Статус:** пакет реализован и проверен на новой изолированной копии; offline/native API/React/final review PASS;24.10.2026пользователь разрешил отдельный commit/push и проверку CI.

**Цель:** восстановить девять обычных страниц лиг под existing parent1503 по принятой схеме R13n, сохранив содержимое и навигацию в текущем SPA-контракте.

**Архитектура:** guarded offline преобразование файла R13n projection, без Mongo apply. Legacy text/table → штатные text_block; источник SQL immutable. Точная спецификация, UUID, source/output hashes и шесть разрешаемых удалений — в [JSON](r13o-league-pages-plan-2026-10-23.json).

**Стек:** существующий FastAPI/Mongo/React; чистый Python-конвертер и native API/React-приёмка в собственной UUID Mongo/internal Docker network. Никаких новых runtime-зависимостей.

Worktree `r5-zip-operations/humorpedia`, ветка `codex/local-page-builder`, HEAD до новых документов `aab3d5b0c6943f7c508649ddfa1d9a36c9d923ba`. R13n опубликован этим SHA; [GitHub39974726532](https://github.com/AMnEPka/humorpedia/actions/runs/39974726532) completed/success:5jobs/3browser-сценария. Пользователь принял R13n в текущем SPA-контракте, KVN HTML/301 вынесены отдельно.

## Почему этот пакет

Read-only инвентарь остальных37 исходных страниц обнаружил разные виды данных. Годовые/фестивальные/специальные страницы могут переключаться на SeasonDetailPage из-за вывода соседних сезонов; у8info-блоков нужен отдельный контракт, у2537 отсутствует дополнительный родитель2536. МСЛ2536 извлечён для исследования, но не включён в перенос. Общий пакет всех37+2536 сейчас потребовал бы новых решений о сезонах, info, медиа и представлении данных.

Рекомендуемый вариант — девять обычных non-year лиг. Все под existing1503, не требуют новых родителей/медиа и не входят в список TV-league renderer. Альтернатива — сначала согласовать расширенную модель всех оставшихся страниц; это больше объёма и не входит в нынешний пакет. Никакой автоматической канонизации сезонов.

## Точный состав

| SQL old_id | Страница | Новый canonical path | Блоков | HTML-таблиц | Тегов |
|---|---|---|---:|---:|---:|
|1585|Центральная Краснодарская лига КВН|`/kvn/league/krasnodarskaya-liga`|1|3|25|
|1587|Центральная Лига Старт|`/kvn/league/start`|1|3|27|
|1588|Центральная Тихоокеанская лига КВН|`/kvn/league/tikhookeanskaya`|1|3|17|
|1589|Центральная Лига Поволжье|`/kvn/league/povolzhye`|1|3|29|
|1590|Центральная Лига «Азия»|`/kvn/league/asia`|1|3|25|
|1591|Центральная Юго-Западная Лига КВН|`/kvn/league/southwest`|3|2|16|
|1592|Центральная Уральская Лига КВН|`/kvn/league/ural`|1|3|19|
|1594|Центральная лига МС КВН «НЕВА»|`/kvn/league/neva`|1|2|6|
|2333|Центральная лига МС КВН «Тремпель»|`/kvn/league/trempel`|2|1|3|

Всего:9new KVN docs,12text_block (9text+3table),23HTML-таблицы,167tag entries,121authored href attributes. Content source58,331символ → output58,097после ровно234рекламных символов; остальные символы сохраняются. Все9 SQL published=1/deleted=0. Статус published используется только на новой копии; индексация не включается.

Parent1503 UUID `febed962-e6b4-4c23-8106-a53830089b32`, full_path `kvn/league`. Разрешаемое изменение existing document — **только child_kvn_ids**: сохранить нынешний UUID Лампы `cd6d3ed7-e6f3-5be4-a0a5-2640473dc7b8` и добавить9новых UUID ровно один раз в порядке old_id. Ни одно другое поле родителя не заполняется/не нормализуется.

Каждой новой странице: UUIDv5 от source table/old_id, _id=id; level2, source alias/old_urls по точной таблице JSON. `season_data` отсутствует; `{}` скрывает модули в React, `null` противоречит KVN Dict-модели. HTML text/table сохраняются в data.content, заголовки/порядок/anchor_ids — из источника. HTML-table не превращать в native module.type=table: он требует data.rows.

## Реклама, ссылки и медиа

9 отдельных ad_250 и9 старых tags presentation widgets не переносятся; названия тегов сохраняются в page.tags. В retained HTML найдено ещё6встроенных рекламных вызовов, по одному в source text[0] у old_id1585,1587,1589,1590,1592,1594:

```text
[[$yandexAds_adder?&nbsp; &amp;num=16]]
```

Предлагается **удалить только эти6точных39-character фрагментов** по pinned source hash/offset; любые другие inline MODX-вызовы или повторные совпадения останавливают преобразование. Не удалять окружающую разметку/пустые абзацы, не применять общий regex-strip. Source/output hash каждого из12HTML-блоков и точные spans в JSON. Простое исключение9widgets не убрало бы эти рекламные строки из видимого текста.

В9страницах нет nonempty TV вне config/tags, retained HTML не содержит src/srcset/poster, script/event handlers или иных inline MODX-вызовов. Новых изображений и внешних media-загрузок нет. Read-only проверки нашли0ID/old_id/canonical/old_URL collisions, включая full_path других коллекций; это предусловия исследования, повторно проверяемые перед apply на копии.

Данные current R13n содержат17неразрешённых входящих keys к этим9целям:186occurrences. Предлагается восстановить targets, не переписывать существующие href. В новых исходных HTML107unique keys: actual resolver на **текущей** копии разрешил101; ещё6literal anchors остаются text по прежнему публичному контракту:

| Страница old_id | Исходный href | Сохраняемая подпись |
|---|---|---|
|1585|`krasnodar.html`|Краснодар|
|1587|`voronezh.html`|Воронеж|
|1588|`khabarovsk.html`|Хабаровск|
|1590|`krasnoyarsk.html`|Красноярск|
|1590|`ne-v-forme.html`|Не в форме|
|1592|`chelyabinsk.html`|Челябинск|

Эти href и подписи сохраняются в storage без подмены цели; недоступный anchor становится текстом только в публичном ответе resolver. Не утверждается, что отсутствуют6самих сущностей: проверены именно literal keys. Их ремонт не включён. Прогноз остатка:72−17+6=**61unresolved key**; новая точная проверка после преобразования обязательна, прогноз не является приёмкой.

## Предусловия и границы

Source `.cache/r13n/copy-v2/patched.jsonl`:25,621records, SHA256 `e352e7a17b8e43660a09a7b6b6397654333aed2b912a64318702c68ab6619001`. SQL SHA256 `d4a2e0930ebc676aca939ad569c54bc82e7470184ca0c40ede63e9a19898cf19`. Parent row SHA256 `19cae04e51b0df92caae0f898026cfe771fc2dad8cd2d48e532e68453ddc3219`. Изменение любого preimage требует остановки и новой сверки; выходной каталог exclusive, исходная copy не перезаписывается.

Ожидаемая новая copy:25,630records,9insert/1existingparentfield/0deletes;25,620прежних строк byte-identical. Лампа/её5HTMLхешей/все R13h–m исправления сохраняются;122canonical seasons/5tournaments/9276participations неизменны. Никаких автоматических season/tournament/participation writes.

Не затрагиваются main checkout/стенд/DB/media, импорт24СМИ, VPS, индексирование, full release/export-local/dev-sync. Не входят остальные28 original resources, finals1603, родитель2536 и сезон2537,8оригинальных posters, KVN server HTML/301.

## План реализации после согласования

| Задача | Файлы и действия | Проверка готовности | Модель |
|---|---|---|---|
|1. Guarded converter | `.cache/r13o/prepare-copy.py`, `test-prepare-copy.py`; обобщить только source-binding R13n на9IDs,12blocks и6literal spans | RED→GREEN: drift/unknown forms/snippets/path collisions/duplicate IDs/reapply/existing output fail; два запуска одного source byte-identical | Sol/high |
|2. Новая copy | `.cache/r13o/copy/patched.jsonl`, acceptance/provenance; один append9 к parent.child_kvn_ids |25,630records;25,620existing byte-identical;0delete; pinned12source/outputHTMLhashes/23tables/167tags; no season_data, parent.otherfields equal | Sol/high |
|3. Независимая сверка | `.cache/r13o/audits/` без приложения/клиента Mongo; typed IDs/all fields/model guards, actual resolver на новой copy |0relations/collisions;122/5/9276 unchanged;61exact residual-set либо остановка при расхождении;6missing anchors stored unchanged/publictext | Luna/high |
|4. Native API/React | `.cache/r13o/harness/`, `run-native.cjs`, `check-leagues.cjs`; отдельная UUID Mongo/internalnetwork/nohostports/source-mediaRO, та же frontend release |9canonical API/SPA routes;12visible blocks/23tables/tag lists,6inline markers отсутствуют;9parent→child+9breadcrumb,по одному authored incoming click на каждую страницу (17keys через API),0pageerrors | Sol/high |
|5. Invariants/cleanup/report | Native before/after, owned DB/network/containers/images; main read-only health/IDs; task docs/JSON |25,630non-view fixture rows unchanged; source copy immutable, Лампа сохранена;2source-verified id overlays parent/root явно учтены, прочие поля не подменены; clean main/IDs/start/restarts same; commit/push только по поручению | Sol/high |

В native fixture допускаются только те же2source-verified id overlays parent1503/root32, что в R13n. Они не добавляются в approved copy и не заменяют parent childlist. Ограничение unique kvn.id/null у остальных projected KVN фиксируется явно; scope не подменяется заявлением о полной базе.

Критерий SPA: React через штатный API GET показывает страницы; metadata/raw-content/HTTP301 KVN не требуются и не объявляются реализованными. Существующий noindex сохраняется. Native тесты работают на изолированной копии; localhost3000/8001 основного main проверяются только read-only.

## Проверки исследования и точка остановки

SQL и исходная R13n copy SHA проверены, остальные37payloads совпали с R13n извлечением; для parent2536 выполнено только read-only извлечение. Module inventory/flags/order/schema просмотрены независимо;6inline ads выявлены дополнительным source preflight и занесены в точную таблицу удаления. Actual resolver107keys выполнен offline `--network none` на SnapshotDB, без Mongo/app lifecycle. На момент read-only исследования copy/API/browser ещё не запускались; итоги выполненной приёмки приведены ниже.

Evidence ignored `.cache/r13o/`: `league-batch-readiness.json`, `outgoing-link-readiness.json`, `inline-ad-removal-plan.json`, `unresolved-authored-anchors.json`, `module-readiness-review.json`; source extraction `legacy-resources.json` в Git не добавляется. Статус конкретных source/output hashes — в JSON.

**Согласовано пользователем23.10.2026:** весь пакет9лиг/6точных удалений рекламы/сохранение unresolved href на новой изолированной копии. Main,24СМИ,VPS и KVN HTML/301 остаются за границами.

Проверка main после исследования: `.cache/r13o/main-after-design.json` — clean `main ca46155a9640d4723c07b9fd1762a6e639563414`, исходные3container IDs/StartedAt и restart0 сохранены, localhost3000/8001health HTTP200. Product diff после опубликованного R13n пуст; незакоммичены только результаты/контекст R13o и metadata завершившегося R13n CI.

## Ход выполнения

Пользователь23.10.2026 подтвердил весь пакет9лиг/6точных рекламных удалений/сохранение unresolved href. Ruling: для9text сохраняется source.title; первоначально derived JSON ошибочно брал служебный section_name=«Текст». Для3table без title сохраняется section_name. Это исправление привязки по принятому требованию сохранить исходные заголовки; HTML/source SHA, aliases и scope не меняются.

Контрольная точка: converter8tests RED→GREEN, exclusive новая `.cache/r13o/copy/patched.jsonl` создана:25,630records/SHA256 `7834b90269e613ed9d30c851eeb7f71aa692878a419d8d018054af739595f7b3`.9insert/1parentfield/0deletes,25,620rawrows byte-identical,6exact ad deletions. Offline audit завершён; первый native run `e615644a75184cd9bf4fb41298080e85` выявил слишком раннее чтение heading в smoke-checker, исправлено ожидание. Окончательный native run указан ниже.

## Результат приёмки R13o

- Converter8tests RED→GREEN. Проверены точные span pre/postimages, неизвестные/повторные snippets, hidden/static/copy flags, source/title/tag/SQL/payload/parent drift, ID/old_id/path/old_URL collisions, exclusive output, repeat/reapply и детерминированный результат. Это host Python проверки offline-конвертера, не API-тесты.
- Независимый offline audit `.cache/r13o/audit-final.py` в Python-контейнере `--network none`, worktree RO/own output RW, без приложения/Mongo: **9insert/1parent-only field/0deletes**,25,620existing raw rows byte-identical.12source/output HTML hashes/6exact deletions/23tables/167tags/121hrefs совпали;9KVN models валидны без stored season_data.6неразрешённых href сохранены, остальные данные и Лампа прежние. Actual resolver **72→61** и точный residual-set, canonical/old_URL conflicts0; relations0,122seasons/5tournaments/9276participations, projection changes0.
- Native **`cd83b8809e7a4169b3598d9ffe218317`**: собственная UUID Mongo/internalnetwork/nohostports, source+media RO; текущий product code/build R13n не изменялся.9canonical API/SPA routes200/noindex,12видимых блоков/23таблицы/167tag entries,6inline ad fragments отсутствуют.17incoming keys разрешены в targets;6недоступных anchors отдаются текстом, Лампа сохранила5блоков/29tags.
- **27реальных browser clicks:**9parent→child,9breadcrumb→parent,9authored incoming anchors. API/React headings/table/tag lists проверены для всех9страниц, pageerrors0. Screenshots сохранены для9страниц, вручную просмотрены Старт1587/Юго-Западная1591/Тремпель2333; остальные визуальные инварианты проверены автоматически.
- До/после **25,630non-view fixture records unchanged**. Те же2source-verified id overlays parent1503/root32 существуют только в native seed/expected fixture, не в copy. Native DB удалена после shutdown; owned containers/network/images удалены, cleanup error=null. Остаточный projection caveat прежний: отсутствующие id у прочих KVN не позволяют создать unique kvn.id index из-за повторяющегося null; приёмка не заявляет полноту DB/index readiness.

`leagues-http.json`, `leagues-browser.json`, `cleanup.json` лежат в `.cache/r13o/native-pages/cd83b8809e7a4169b3598d9ffe218317/`. Независимые итоги — `.cache/r13o/audits/summary.json`, `structural-audit.json`. В JSON задачи сохранены9точных prepared_documents и единственный parent delta; SQL/полная projection/sidecar/logs остаются ignored. Исторический `inline-ad-removal-plan.json` имеет approved=false на момент исследования; разрешение исполнения — явный ответ пользователя и утверждённая policy с теми же6edits. Исторические evidence не переписываются.

Первый native run остановился при correct destination `/kvn/league/start`, пока React ещё показывал heading родителя: checker ждал любой visible h1/networkidle. Исправлено только ожидание **конкретного expected heading**, сохранив строгую проверку URL/заголовка; продуктовый код/данные не менялись. Первый run штатно удалил owned ресурсы; принятым считается только окончательный полный run.

Main boundary `.cache/r13o/main-after-acceptance.json`: clean main `ca46155a9640d4723c07b9fd1762a6e639563414`, те же3container IDs/StartedAt/restart0; frontend3000/backend8001health HTTP200, Mongo healthy; Compose ps прочитан без sync/restart. Product/backend/frontend/scripts/migration diff пуст. Импорт24СМИ/VPS/indexing не менялись.

Новых полных suite/build не запускалось: продуктовый diff пуст, использован тот же release `1bc6820bb6cc2e3c0099106d7b1aed96ece05e21dbe6c736571c7115ba2378d6`, проверенный R13n CI39974726532. Этот CI не подменяет новую data/API/React приёмку R13o. На этапе реализации commit/push не выполнялись;24.10.2026пользователь поручил опубликовать R13o отдельным коммитом с документацией и проверить GitHub CI.

Финальный независимый review всей области R13o: **PASS,0blocking findings**, `.cache/r13o/final-scope-review.json`; повторно сверены source/final SHA, raw-delta, HTML/счётчики,27click artifacts и границы fixture/SPA. Этап R13o завершён в согласованном объёме на копии.
