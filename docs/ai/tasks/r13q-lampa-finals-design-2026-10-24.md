# R13q — финалы «Лампы»: схема восстановления на копии

**Дата:** 24.10.2026. **Статус:** весь согласованный пакет реализован и принят на новой изолированной копии; offline/API/SPA/React PASS. R13q не закоммичен.

Worktree `r5-zip-operations/humorpedia`, ветка `codex/local-page-builder`, HEAD `5a22906ee64bf7b03bc2c5215180508fdfb99560`. R13p опубликован этим SHA; [GitHub CI40066682049](https://github.com/AMnEPka/humorpedia/actions/runs/40066682049) completed/success: все5jobs и3browser-сценария. Точные ID, предусловия и ожидаемые изменения — в [JSON](r13q-lampa-finals-design-2026-10-24.json).

## Результат и выбор

Следующий ограниченный пакет после R13p — восстановить одну существовавшую страницу «Финалы Центральной Лиги Москвы и Подмосковья» (SQL old_id1603) под уже восстановленной «Лампой»1586. Её два старых href встречаются в трёх документах текущей копии. Новые сведения о командах/сезонах не создаются: сохраняется исходный обзор с таблицами.

Рекомендуемая схема — один published документ только на новой изолированной копии и одно поле у родителя. Альтернатива — оставить страницу отсутствующей до общей миграции остальных27ресурсов. Объединение с годовым/фестивальным пакетом добавит вопросы о сезонном рендере и info-модулях; для1603 они не требуются.

Нужно явно закрепить canonical slug. В SQL `alias=lampa-finals`, но `uri_override=1` задаёт старый `kvn/lampa/finals.html`. Рекомендация — сохранить source alias: **`/kvn/league/lampa/lampa-finals`**, оба реально используемых старых href сохранить в `old_urls`. Альтернативный canonical `/kvn/league/lampa/finals` повторял бы окончание overridden URI, но менял бы source alias; автоматический выбор по одной части URI не делается.

## Точная спецификация

| Поле/область | Предлагаемое значение |
|---|---|
| SQL source | `modx_site_content`,1603, published1/deleted0, parent1586 |
| Новый ID | `82b3fd71-c3f6-5866-aac1-37e390a0ba9e`, UUIDv5 от `https://humorpedia.ru/legacy/modx/site_content/1603`; `_id=id` |
| Заголовок/name | «Финалы Центральной Лиги Москвы и Подмосковья» из source pagetitle |
| Description | «Статистика всех финалов Центральной лиги Москвы и Подмосковья («Лампа») МС КВН.» из source description |
| Parent | Лампа1586, `cd6d3ed7-e6f3-5be4-a0a5-2640473dc7b8`, full_path `kvn/league/lampa` |
| Slug/full_path/level | `lampa-finals` / `kvn/league/lampa/lampa-finals` /3 |
| Status | published только в новой изолированной копии; индексирование выключено |
| Старые href | `/kvn/lampa/finals.html`, `/kvn/lampa/finals` |
| Модуль | один `text_block`, id `modx-1603-text-52972`, order0/visibletrue; title из source.title, anchor_id `text-52972` |
| Содержимое |44,099символов,19HTML-таблиц,19href attributes; исходная строка целиком без правок |
| Теги/медиа/реклама |0tags,0media refs,0inline MODX,0ad widgets,0event handlers |
| season_data | Поле отсутствует. Не `{}` и не `null`; seasons/tournaments/participations не создаются |
| Existing parent mutation | Только `child_kvn_ids`: `[]` → `[82b3fd71-c3f6-5866-aac1-37e390a0ba9e]`, остальные поля неизменны |

Source section content SHA256 `595a66b589d7868eb46b07eccf6d61cb9c2ac1e7dd2ba8fde04551b2a34a3cf1`. Это HTML-table внутри text_block, не native table-модуль с другим data contract. Source section_name «Текст» — служебное имя формы; видимый заголовок берётся из source.title, как в R13o.

JSON описывает спецификацию, а не готовый KVN payload: служебные scope/content_policy/omitted_fields не записываются в документ. Persisted status строго `published`; `season_data` не записывается, включая default модели.

## Проверенные факты

Source `.cache/r13p/copy/patched.jsonl`:25,630records, SHA256 `44d72ff221401637ebaf561a97d3ec019903b66faf5ba8fff13a51ed63b33993`. Parent row SHA256 `ffaaf12f6620e13eac2a6927125f51953aae4f7e9e8a7b3810119d67c544bb2a`; родитель published, `_id=id`, level2, child_kvn_ids пуст.

Проверен immutable SQL `humorbd.sql`, SHA256 `d4a2e0930ebc676aca939ad569c54bc82e7470184ca0c40ede63e9a19898cf19`: pure parser индексировал3374resources, source resource/единственная MIGX section/tags точно совпали с pinned extraction. SQL/исходный сайт не исполнялись. В retained content нет media, info, hidden/static/copy flags и MODX-вызовов. Коллизий предлагаемых UUID/old_id/full_path/canonical/старых href с текущей копией не найдено.

Независимый static contract review: `get_kvn_by_path` обслуживает полный путь; `find_adjacent_seasons` извлекает год из slug/path, у выбранного пути года нет. React `SectionDetailPage` переключается на SeasonDetailPage при truthy season_data, поэтому отсутствие этого поля — обязательная граница. Новый документ должен иметь `id==_id` и `parent_id==parent.id`: API получает children запросом по parent_id, breadcrumbs — по id, а не только из child_kvn_ids. Это статическая совместимость; новый API/React путь пока не запускался.

## Ссылки: прогноз, не приёмка

Два входящих keys сейчас не разрешаются. Их точные контексты:

- статья `/articles/a-vy-znali-chto-2`: href `/kvn/lampa/finals`, подпись ««Лампы»,»;
- команда `/kvn/teams/barricadnaya`: href `/kvn/lampa/finals`, подпись ««Лампы»»;
- Лампа `/kvn/league/lampa`, module0: href `kvn/lampa/finals.html`, подпись «отдельной странице».

Так что extensionless alias подтверждён существующими authored href, а не выведен автоматически из `.html`. Все3existing поля сохраняются без переписывания ссылок; resolver должен разрешить их через новый target/old_urls в текущем SPA-контракте. Server301 не добавляется.

Actual resolver на **неизменённой** R13p copy проверил18unique outgoing keys будущего текста:17разрешаются на существующие цели,1нет. Это `kvn/team/omskaya.html`, подпись **«Омская сборная»**. Рекомендация — сохранить исходный href и подпись; штатный публичный resolver оставит подпись текстом. Не угадывать другую команду, не создавать карточку, не менять href и не добавлять global aliases.

Прогноз остатка:55−2входящих keys+1новый literal key=**54unresolved**. Точный ожидаемый residual-set записан в JSON. Само появление нового literal не доказывает отсутствие сущности: это результат разрешения данного ключа. На этапе исследования новой copy не было; это был прогноз. Приёмка ниже подтвердила точный54-key residual-set.

## Границы и критерии реализации после согласования

Новая copy:25,631records,1insert/1existing parent field/0delete;25,629прежних raw rows byte-identical. Вставленный документ сохраняет весь44,099-character HTML,19таблиц/19href; parent сохраняет всё, кроме childlist. Предыдущие R13h–p исправления,122seasons/5tournaments/9276participations неизменны. Converter обязан проверять source/SQL/payload/parent/content SHA и typed IDs, коллизии, drift, duplicate/reapply/existing output; второй exclusive output должен совпасть побайтно.

| Проверка | Критерий готовности | Рекомендуемая модель |
|---|---|---|
| Guarded converter | RED→GREEN guards; exact1insert+parentfield, source immutable, season_data omitted | Sol/high |
| Независимая сверка |25,631rows/25,629unchanged raw;1module/19tables/19href/44,099chars;exact54residual-set;0collisions/relations | Luna/high |
| Native API/SPA/React | parent+new page+3incoming sources и17existingtargets доступны; новый canonical200/noindex, заголовок/таблицы видимы, season_data отсутствует; unresolved anchor хранится без изменения и публично остаётся текстом | Sol/high |
| Реальные клики |3authored входящих+parent-child+breadcrumb; исходящие к Лампе и одной existingteam; правильные target h1,0pageerrors | Sol/high |
| Сохранность и cleanup |before/after25,631non-view domain fields равны seeded expected fixture; owned DB/containers/network/images удалены;main baseline/health unchanged | Sol/high |

Допустимы только прежние2source-verified fixture id overlays root32/league1503 при seed/expected checks. JSONL не дополняется этими полями; известная проблема projection unique kvn.id/null не подменяется заявлением о полной DB/index readiness. Native stack — отдельные UUID resources/internal network/no host ports, source/media read-only, тот же frontend release. Main checkout/стенд/DB/media, импорт24СМИ, VPS, индексирование и dev-sync/export-local не затрагиваются. Остальные27legacy resources,8posters, исправление «Омской сборной», KVN HTML/301 вне пакета.

Evidence `.cache/r13q/finals-content-readiness.json`, `finals-link-readiness.json`, `finals-contract-review.json`; hashes в task JSON. Полный source dump/HTML/copy и сырые журналы в Git не добавляются.

**Согласовано24.10.2026:** создание страницы1603 на новой копии с canonical slug `lampa-finals`, единственную parent childlist mutation и сохранение всех исходных href Подтверждены canonical slug `lampa-finals` и сохранение href «Омская сборная» без подмены. Основание исполнения — явный ответ пользователя; границы main/24СМИ/VPS сохраняются.


## Детальный план исполнения после согласования

> Исполнителю: использовать `superpowers:executing-plans`; утверждённая схема выше — binding spec. HEAD до реализации `5a22906ee64bf7b03bc2c5215180508fdfb99560`.

- [x] Task1 — Sol/high. Создать `.cache/r13q/test-prepare-copy.py`: golden source/resource→1exact module, no season_data,1parentfield; drift source/SQL/payload/policy/parent/content; typedBSON IDs,duplicate/reapply/existingoutput/collisions; RED. Затем `.cache/r13q/prepare-copy.py`: frozen-policy/source/SQL/payload pins,resource1603/sourcealias,exclusive output,exact parent delta, deterministic timestamps из SQL; GREEN. Blueprint служебные fields не сериализовать в KVN. Никакого create_kvn/DB apply.
- [x] Task2 — Sol/high. Создать только новые `.cache/r13q/copy` и `copy-repeat`; output SHA identical,25,631rows/25,629unchangedexistingraw. Provenance source field/full HTML SHA, новые document/parentdelta/acceptance сохранить рядом; source immutable.
- [x] Task3 — Luna/high. Независимый `.cache/r13q/independent-copy-audit.py/json`: whole-copy typed/raw/deepdiff; model validation без dump defaults; offline actual resolver54exactset/collisions0/relationfindings0/122+5+9276unchanged. Root запускает runtime mode в backend image `--network none`, без app/Mongo.
- [x] Task4 — Sol/high. Адаптировать native owned harness текущего release: `.cache/r13q/harness`, `run-native.cjs`, `check-finals.cjs`. Seed25,631bounded batches, mediaRO,uniqueUUID/nohostports; HTTP/API/SPA/model/19table render,3authored incoming+parent-child+breadcrumb+2outgoing real clicks, expected h1,0pageerrors; Omskaya storedhref unchanged/APItext. Before/after25,631nonview fields unchanged;2прежних fixture overlays явно учесть.
- [x] Task5 — Sol/high, независимый review Luna/high. Штатный shutdown/owned DB отсутствует/cleanup контейнеров-сети-образов; read-only main status/health/baseline. Обновить task MD/JSON/индекс,проверить evidence hashes/links/diff и независимый finalreview. R13q commit/push только по отдельному поручению.

Pre-flight: converter→audit→native используют один frozen source и один exclusive copy, rowcount25,631;2fixture id overlays только в seed/expected. Не использовать SQL HTML для переписывания существующих R13p страниц. Default KVN.season_data не должен попасть в output. Expected residual-set — ровно предложенные54keys, любое отличие остановит приёмку.

Identity note: у исходного SQL resource1603 есть отдельное legacy custom поле old_id=1660. Modern old_id=1603 берётся из modx_site_content.id по существующему import contract; custom1660 в новую identity не переносится.


## Приёмка R13q —24.10.2026

HEAD до незакоммиченных изменений `5a22906ee64bf7b03bc2c5215180508fdfb99560`, ветка `codex/local-page-builder`. R13p опубликован/CI success; R13q остаётся локальным незакоммиченным результатом.

- Guarded converter:8tests RED26failures→GREEN8pass. Сверены source/SQL/payload/frozen-policy/parent fingerprints,approval/status/identity,неизвестные/hidden/changed sections,ID/old_id/path/old_URL collisions,reapply/existingoutput/typedBSON rows. Frozen apply-policy SHA `b5c262988af189095f9fd6624bcea0f20fb50fb26861136c358731a8ac6ed3f7`.
- Copy `.cache/r13q/copy/patched.jsonl`, SHA `89dbf5066ef9f8f73a9384a5d647a83be33a6a1426c5112b4238ea9cdd23d6ca`; второй exclusive output идентичен.25,630→25,631rows,ровно1insert+1parent childlist field,25,629existingrawrows byte-identical,0delete. Source/payload/SQL неизменны.
- Независимые structural/actual offline resolver/model/relation audits PASS: **55→54exact residual-set**,0collisions/old_url conflicts/relation findings,122seasons/5tournaments/9276participations неизменны. New KVN model valid; season_data не записан. HTML44099chars/19tables/19href полностью равен источнику; customlegacyold_id1660 не использован вместо SQL resource ID1603.
- Native accepted run `b4fe978858994eabb8acffa56943a9d6`: candidate+parent/3incoming sources/17existing outgoing targets API/SPA200/noindex;19таблиц в React DOM. **7реальных кликов** с правильными target headings:parent-child,breadcrumb,3authored incoming (включая popup статьи),2authored outgoing.0pageerrors; «Омская сборная» storedhref unchanged/APIplainlabel,битую цель не кликали. Before/after всех25,631records non-view domain fields равны expected seed.
- Cleanup PASS: штатный backend shutdown,owned DB отсутствует,UUID containers/network/images удалены. Main чистый `ca46155a9640d4723c07b9fd1762a6e639563414`,3container IDs/StartedAt/restarts прежние;localhost3000 и8001health200.24СМИ/VPS не затрагивались.

Первый native run `5a82ee46a193458abd42884000c8a240` остановился в checker на parent-child selector: карточка SectionDetailPage имеет onClick, не role=link. Изменён только checker на exact CardTitle text; полный повтор выше PASS. Failed run не принят,его cleanup также PASS. Данные/приложение/конвертер после создания copy не менялись.

Использован тот же frontend release `1bc6820bb6cc2e3c0099106d7b1aed96ece05e21dbe6c736571c7115ba2378d6`; новый frontend build/full suites для data-only пакета не запускались. Скриншоты верхней части страницы и последней таблицы сохранены и вручную просмотрены. Приёмка проекции использует ровно2прежних source-verified ID overlays только при seed/expected; известный startup error unique kvn.id/null на других projected rows сохраняется,полная DB/index readiness не заявляется. Raw JSONL не дополнена overlays. Server KVN HTML/301 и индексирование не расширялись.

Команды из этого worktree (output должен быть новым):

```powershell
py -3.14 .cache/r13q/test-prepare-copy.py
py -3.14 .cache/r13q/prepare-copy.py --source .cache/r13p/copy/patched.jsonl --policy .cache/r13q/apply-policy.json --legacy .cache/r13n/legacy-resources.json --sql C:/Users/rdp6126443.gmail.com/humorpedia/humorbd.sql --output-dir .cache/r13q/copy-new
py -3.14 .cache/r13q/independent-copy-audit.py
$env:BROWSER_BUILD_DIR=(Resolve-Path .cache/r13n/frontend-build).Path
node .cache/r13q/run-native.cjs
node .cache/r13q/check-main-acceptance.cjs
```

Actual offline runtime выполнялся в backend image с `--network none`, `/work` read-only,own `/out`; `independent-copy-audit.py --root /work --runtime --output /out/offline-runtime-audit.json`. Hashes входов/скриптов/приёмки/native evidence перечислены в task JSON; полный dump/HTML/copy/сырые журналы остаются в ignored staging.

Финальный независимый scope/acceptance review R13q: **PASS,0blocking findings**, `.cache/r13q/final-scope-review.json`. Прямо сверены source/output/repeat SHA,raw delta/parentfield,source-exact HTML и offline/native evidence; границы projection/fixture/SPA сохранены. Все5задач согласованного плана завершены. R13q не коммитился/не публиковался.

## Публикация24.10.2026

Пользователь поручил отдельный commit/push R13q с документацией и проверку GitHub CI. Source/output SHA и22evidence hashes перепроверены перед публикацией; новая приёмка не подменяется прежним CI. Назначение `origin`, точный ref `refs/heads/codex/local-page-builder`. Main/24СМИ/VPS не затрагиваются.
