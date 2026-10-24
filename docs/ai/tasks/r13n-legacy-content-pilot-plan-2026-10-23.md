# R13n — готовность legacy-контента и пилот «Лампы»

Дата:23.10.2026. Статус: **R13n принят пользователем в действующем SPA-контракте; данные копии и navigation fix проверены, опубликован отдельным aab3d5b; GitHub CI39974726532 success**.

Ветка `codex/local-page-builder`, тот же worktree `r5-zip-operations/humorpedia`. HEAD до незакоммиченных изменений `bb3221dee5810871a00e117473167ad4f47e6273`. R13m опубликован этим SHA; [GitHub CI39966829017](https://github.com/AMnEPka/humorpedia/actions/runs/39966829017) completed/success на точном SHA:5jobs/3browser-сценария success. Serving/indexing основного стенда не переключаются, main/24СМИ/VPS не затрагиваются.

## Что проверено сейчас

Все38 SQL ID найдены в локальном дампе; SHA256 `d4a2e0930ebc676aca939ad569c54bc82e7470184ca0c40ede63e9a19898cf19` совпал с прежней проверкой. Существующий `backend/services/modx_dump.py` прочитал3374resources без MySQL; retained payload ограничен38 ID. Title/ID/URI сопоставлены с независимым SQL-index; расхождений названий0.

У всех38 template19 и пустой `content`; содержимое находится в TV `config`: **198 MIGX секций**. Простой перенос поля content создал бы пустые страницы.

| Тип исходного блока | Количество |
|---|---:|
| text |88|
| table |26|
| info |8|
| ad_250 / ad_block_120 |43 / 4|
| tags |23|
| popular_articles |5|
| post_footer |1|

HTML-инвентарь распакованного MIGX:1163 href-атрибута во всех строках секций, из них776 именно в полях content. Остальные строки включают editor metadata, например ссылки MODX manager; их нельзя переносить в публичный HTML. Атрибутов src/poster/srcset в этих разобранных HTML-строках0; это не полная проверка всех возможных TV media-полей. В18ресурсах найдены только inline YandexAds chunks; произвольное исполнение MODX не требуется и не запускалось.

Родители38ресурсов:36 уже находятся в принятой KVN projection,1 входит в эти38,1 отсутствует за пределами списка: **old_id2536 «Лига Молодёжь Москвы (МСЛ)»**, родитель2537. Полное восстановление всех38 потребует отдельно согласовать эту дополнительную страницу; автоматического расширения до39 нет. Текущих old_id collisions для38 в projection0. Отсутствие в projection не доказывает отсутствие в полной main DB.

Универсальный legacy importer не запускался: read-only review выявил случайные UUID, автоматический published, усечение description и пропуск неизвестных модулей. Штатный create_kvn не принимает old_id и теряет объявленный old_urls; эти API-проблемы не исправляются в данном пилоте. Предлагается отдельное guarded преобразование файла копии, а не вызов API-create и не запись в основную Mongo.

Evidence в ignored `.cache/r13n/`: `legacy-resources.json`, `sql-content-readiness.json`, `parsed-content-inventory.json`, `parent-identity-review.json`, `import-readiness-review.json`, `lampa-pilot-contract-review.json`. SQL/HTML/raw logs в Git не добавляются. Анализаторы: `analyze-sql.py`, `inventory-content.py`, `analyze-links.py`; приложение/Mongo для исследования не запускались, последний resolver — networknone на SnapshotDB, без подключения к БД.

## Согласованный scope пилота

[Точная спецификация и хеши](r13n-legacy-content-pilot-proposal-2026-10-23.json). Пользователь подтвердил ровно этот пилот. Новая projection создана в ignored `.cache/r13n/copy-v2/patched.jsonl`; JSON спецификации хранит контракт, проверяемые результаты, точный prepared_document с пятью HTML-блоками и единственный prepared_parent_change. Полная DB/SQL-выгрузка в Git не включается.

| Объект | Изменение только на новой изолированной копии |
|---|---|
| Новая страница | old_id1586, «Центральная Лига Москвы и Подмосковья», slug lampa, путь `/kvn/league/lampa`; status published только в копии, как в SQL; indexing=false |
| Идентичность | UUID `cd6d3ed7-e6f3-5be4-a0a5-2640473dc7b8`; UUIDv5 от стабильного source table/ID, не случайный UUID и не hash текущего HTML. _id/id согласованы; проверка collisions до применения |
| Родитель | old_id1503, UUID `febed962-e6b4-4c23-8106-a53830089b32`, slug league, full_path kvn/league; только однократное добавление нового UUID в child_kvn_ids, сейчас поле отсутствует. Все прочие поля родителя сохраняются |
| Материал |5text_block,11261символ исходного HTML,4HTML-таблицы; заголовки/порядок/разметка без усечения, content SHA проверяется по каждому блоку |
| Теги |29 исходных названий в штатном page.tags; старый tags-widget не копируется |
| Не переносится |4 рекламных блока и1 старый tags-widget; editor metadata/_this.value/file_name_vis не попадают в публичный документ; source provenance сохранена отдельно |
| Старые адреса | old_urls: `/kvn/league/lampa/`, `/kvn/lampa`, `/kvn/lampa.html`; только per-document lookup, без глобального alias/slug fallback |
| Сезоны | season_data отсутствует; parent slug league не входит в TV auto-season список. Канонические seasons/tournaments/participations не меняются |

Содержимое5text блоков:

| Источник | Заголовок | Символов | SHA256 HTML |
|---|---|---:|---|
| config[0] `text-lampa` | Центральная Лига Москвы и Подмосковья | 1922 | `3b7d99de2761355d17a6c74593a1f6609271ad4b68453a5af4fbce316c514aae` |
| config[2] `text-lampa2` | Чемпионы лиги (нулевые) | 2562 | `1270ef48e0e960e7b7738800bc117ba73a943662a643d30cfe593199f3dd26e5` |
| config[4] `text-lampa3` | Чемпионы лиги (десятые) | 3552 | `d9b0843747c81542963b495bb7ba7fb328fa90619bfe68c127b03762aa5e8476` |
| config[6] `text-lampa4` | Чемпионы лиги (двадцатые) | 1870 | `6c19dee8e11f11c70780071ea4173a3593e56a1c6ccf199b58a4cdb491e91131` |
| config[7] `text-lampa5` | Чемпионы спецпроекта | 1355 | `224cd2db117a56d98d2e4da98c53f5996b33a0c4b85cf0ffd2da0e62a38d27a1` |

Первая часть текста не дублируется целиком в description. SEO description формируется из исходного текста существующим helper в рамках принятого контракта humorpedia.ru. Новых внешних изображений/загрузок нет: у пяти блоков media refs0 и inline MODX snippets0; при отсутствии собственного image действует уже существующая общая карточка.

Parent row SHA256 `842ec97cb18ec7ce29bc0a17e0da6bc06215edd99cc40b2c9e7e031a75d28540`. Source copy `.cache/r13m/copy/patched.jsonl`,25,620records, SHA256 `9c63bb45d3a18d66b0798bd81db27308546322db3996cb0cdc12673c379cc308`. Before/after предусловия запрещают source/parent drift и переиспользование выходного каталога.

## Ссылки и предел обещанного результата

Два текущих входящих ключа `kvn/lampa` и `kvn/league/lampa` встречаются в199буквальных href. Предлагается восстановить target, **не переписывать эти199 href в существующих документах**. API resolver находит новую карточку через full_path/old_urls; React-переходы проверены в native-пилоте. HTTP301 для KVN не входит в принятую границу.

В пяти исходных текстах22href. Реальный resolver на принятой R13m projection разрешил21 в существующие published цели; ссылка `kvn/lampa/finals.html` ведёт на пока отсутствующую страницу финалов, old_id1603. Её **не заменяем родительской страницей** и не импортируем1603. В публичном ответе она остаётся текстом по прежнему контракту; исходный href хранится.

Базовый остаток73keys. Прогноз после пилота — **72 буквальных unresolved keys**, а не71: два входящих ключа оживут, но появится raw .html-вариант уже известного неразрешённого `kvn/lampa/finals`. Это не новая отсутствующая сущность. Новый offline actual resolver подтвердил этот residual-set; результаты ниже. Неожиданные новые keys/targets — остановка, без автоматического ремонта.

## План выполнения и результаты

| Шаг | Проверка готовности | Модель |
|---|---|---|
|1. Offline converter | Только1586; source SQL/copy/parent/module SHA; детерминированные IDs/metadata и результат. Не использовать apply legacy importer/API-create | Sol/high |
|2. Защитные проверки | Повторный transform одного source даёт одинаковый результат; drift/duplicate/path collision/unknown module/повторное применение к готовой копии отклоняются без повреждения output | Sol/high |
|3. Новая projection |25,621records:1insert+1изменённый parent,25,619 прежних строк byte-identical,0deletes; exact old_id1586/old_urls/parent_id/full_path/level; HTML5block hashes и29tags сохранены; только parent.child_kvn_ids delta | Sol/high |
|4. Независимый аудит | Все typed IDs/прочие поля/медиа/R13i прежние;122canonicalseasons/9276participations совпали,нет новых tournaments/seasons; новый resolver фактически измерен | Luna/high |
|5. Native API/SPA | UUID DB/internalnetwork/nohostports/source/mediaRO;canonical+3старых URL в текущем SPA-контракте/noindex; parent→child, canonical page, существующие страницы с обоими входящими keys; KVN HTML/301 отдельно | Sol/high |
|6. React/cleanup | Реальные клики из обоих alias-контекстов и parent/child, заголовки/5блоков/4таблицы/21target; finals остаётся текстом;before/after25,621вне views;owned resources удалены/main unchanged | Sol/high |
|7. Отчёт | Подтверждённые цифры/границы, без заявлений о полной БД или готовой выкладке. Commit/push отдельным поручением | Sol/high |

Это отдельная проверка новых данных; успешный R13m CI не заменяет её. Новые полные suite/build нужны только при изменении соответствующего продуктового кода; сам перенос данных не разрешает менять API, Mongo topology или runtime.

## Что остаётся за границей

Остальные37 выбранных ресурсов, финалы1603 и дополнительный родитель МСЛ2536 не создаются. Не запускается full export-local: он останавливает основной стенд. Не затрагиваются main DB/storage, импорт24СМИ,8оригинальных постеров,111external/embed URLs, VPS, serving/indexing и интеграционный dev-sync. Полный release archive/интеграция остаются отдельными этапами.

Пилот ограничен одной legacy-страницей Лампы с явным parent delta; общий пакет остальных ресурсов и дополнительного родителя потребует отдельного плана. Пользователь подтвердил этот ограниченный scope; остальные ресурсы требуют отдельного согласования.

## Проверки исследования

SQL SHA,38точных ресурсов и родительские зависимости проверены. Штатный resolver протестирован offline только на22 исходящих ключах против текущих данных; это не HTTP/UI-приёмка новой страницы. JSON/локальные ссылки проверены; независимый final scope review **PASS_WITH_BOUNDARIES**, evidence `.cache/r13n/proposal-review.json`, SHA256 `b267d104ca25cbe291c49b3b5b8bdcccaea564f0b4f4a362b0c7efeb546b2d9e`. Перед будущим apply отдельно проверяются exact old_id/old_urls/parent/path и единственный parent.child_kvn_ids delta; штатный API-create не используется. Внешняя доступность old site/media и full release не заявляются; отдельные native API/React-проверки выполнены ниже.

## Контрольная точка реализации

Пользователь подтвердил пилот «Лампы» на копии. Converter `.cache/r13n/prepare-copy.py` проверяет exact SQL/source/payload/parent SHA и отказывается от существующего output.7защитных тестов RED→GREEN, включая воспроизводимость двух результатов и отказ при drift/collision/повторном apply. Отдельная проверка обнаружила ошибочный `season_data:{}`: JS трактует его как сезон и скрывает legacy modules. Итоговый документ **не содержит season_data** (как обычная legacy KVN-страница); `KVN.model_validate` проходит без изменения модели или renderer. Первая диагностическая copy сохранена отдельно и не принимается.

Принятая для дальнейшей приёмки copy-v2:25,621records, SHA256 `e352e7a17b8e43660a09a7b6b6397654333aed2b912a64318702c68ab6619001`;1insert/1existingparentfield/0deletes,25,619прежних строк byte-identical. Независимый structural audit PASS;5HTML-хешей/29tags/old_urls/identity точны. Offline actual resolver73→72 с точным разрешённым residual-set; relations findings0/warnings0,122seasons/5tournaments/9276participations сохранены. Evidence `.cache/r13n/independent-copy-audit.json`, `.cache/r13n/audits/{summary,content-audit,relations-audit}.json`. Это не HTTP/UI-приёмка.

Native fixture дополнительно использует **только два `id`** parent1503/root32, отсутствующие в R13g projection. Два узких read-only `find` подтвердили `_id==id` и parent/path/old_id; sidecar `.cache/r13n/navigation-sidecar-readonly.json`, SHA256 `5156e14ab50f7d78494d9e196c8b6c1080e1927a47bd5e5883ac18da06f65bd6`. Harness проверяет SHA/identity, добавляет только id при seed и ожидаемой сверке, не подменяет child_kvn_ids/level. Copy-v2 остаётся неизменной; основная БД не записывалась. Проверка native navigation относится к этой явно дополненной fixture, не к полной DB.

## Native API/React и согласованный navigation fix

Первый native запуск показал расхождение с первоначальным планом: текущий HTML-router и legacy HTTP-dispatch поддерживают **только people/articles** (`backend/routes/public_html.py`, `services/public_html_dispatch.py`). KVN отдаёт SPA-shell: HTTP200/noindex, исходный HTML не содержит заголовок/контент/canonical страницы; три старых URL также HTTP200 без HTTP301. Это существующая граница реализации, а требование KVN raw HTML/301 в данном плане было ошибочным. Расширение на KVN не выполнено. **Решение пользователя23.10.2026:** принять R13n в действующем SPA-контракте; HTML/301 для КВН — отдельная задача. R13n accepted в этих границах, расширения backend HTML-router не выполнено.

Diagnostic run `07f8e22fd86949348b9dcd0c7bf37081` воспроизвёл относительные пути SectionDetailPage: parent child card открыла `/kvn/league/kvn/league/lampa`, breadcrumb в следующем diagnostic run `8057f735b63144d98c018bad57fd2c5a` открыла `/kvn/league/lampa/kvn/league`. Пользователь **отдельно разрешил** минимальное исправление двух точек навигации в этом worktree. Добавлен общий `sectionPath`: один ведущий `/`, нормализация уже абсолютного пути; child slug fallback сохранён. Изменены только `frontend/src/public/pages/SectionDetailPage.jsx` и `.test.jsx`, без исправления API/данных/HTML-dispatch.

Regression tests: RED ровно2navigation failures → GREEN9tests; покрыты relative/absolute full_path у cards/breadcrumbs и child slug fallback. Полный frontend suite **59suites/367tests PASS**. Текущий `yarn build` в отдельном disposable контейнере с readonly frontend source, `CI=true`, `BUILD_PATH=/out`, `--network none` прошёл lint и production build; dependency image `humorpedia-r12c-frontend-dev` не изменяет основной node_modules. Jest/setup/Vite config SHA совпали с текущими файлами. Source release `1bc6820bb6cc2e3c0099106d7b1aed96ece05e21dbe6c736571c7115ba2378d6`. Evidence `.cache/r13n/navigation-tests-{red,green}.log`, `frontend-tests.log`, `frontend-build.log`, `navigation-review.json` (без блокирующих замечаний).

Повторный native run **`bfd630734d024d0b8848320c0c13dd97`** на новой сборке: API5modules/4tables/29tags/21существующая outgoing цель; finals href unwrap → текст, новый final не создан; parent.children и child.breadcrumbs корректны. Входящие authored anchors `/people/maksim-antosyak` (key kvn/lampa) и `/kvn/teams/mma-sechenova` (key kvn/league/lampa) реально нажаты. Затем parent→child и breadcrumb→parent реально нажаты с точными canonical destinations; **4клика PASS, pageerrors0**. Screenshot `closed/lampa.png` и parent.png визуально проверены. До/после25,621fixture rows совпали вне views;2sidecar ID учитываются явно. Owned DB удалена при native shutdown, containers/network/images удалены, cleanup error=null. Файлы `closed/links-http.json`, `closed/links-browser.json`, `cleanup.json` лежат в `.cache/r13n/native-pages/<run>/`. Историческая пометка diagnostic-only относится к ещё не согласованной на момент запуска HTML-границе; assertions API/React/navigation пройдены. Позднее пользователь явно принял эту SPA-границу; исторические artifacts не переписываются. Старый баннер runner «Product unchanged» после UI-fix неточен: frontend изменён, GitHub CI прежнего HEAD не покрывает новые незакоммиченные строки.

В ходе одного промежуточного syntax-failure checker завершился до startup-ready; shutdown guard сообщил incomplete shutdown. После удаления owned ephemeral Mongo/tmpfs все его ресурсы удалены. Этот прогон не принят; финальный приведённый выше прошёл shutdown и cleanup без ошибок. Остаточное fixture-ограничение: экспорт не содержит id у прочих legacy KVN, поэтому штатный startup предупреждает о unique kvn.id/null; это не новая ошибка main и не полная DB-приёмка.

Проверка primary после пилота: `.cache/r13n/main-after-pilot.json` — clean main `ca46155a9640d4723c07b9fd1762a6e639563414`, те же3container IDs/StartedAt, restart counts0; frontend3000 и backend8001/api/health HTTP200, Mongo healthy. `docker compose ps` прочитан без sync/restart. Импорт24СМИ, backend/scripts/migration не изменены; VPS и indexing не затронуты. Пользователь поручил отдельный commit/push R13n с документацией и проверкой GitHub CI; публикация выполняется после проверки staged diff. Следом — read-only план восстановления оставшихся legacy-страниц; изменение их данных требует отдельного согласования.

## Окончательное согласование и доставка

23.10.2026 пользователь явно принял текущий SPA-контракт: R13n не обещает серверный HTML-контент/canonical/301 для KVN. Отдельная задача KVN HTML/301 внесена в общий план; она не блокирует принятую копию и исправленную навигацию. В JSON сохранён точный документ1586 (Extended JSON) и guarded parent delta: это reviewable пакет, а не автоматическая запись в основную БД. SQL, полная projection, sidecar и логи остаются ignored.

## Публикация R13n

Отдельный коммит `aab3d5b0c6943f7c508649ddfa1d9a36c9d923ba`, `fix(content): accept Lampa pilot and root section navigation (R13n)`:8файлов,647insertions/6deletions. Push выполнен только в `refs/heads/codex/local-page-builder`, remote SHA проверен. [GitHub39974726532](https://github.com/AMnEPka/humorpedia/actions/runs/39974726532) запущен на точном SHA; completed/success:5jobs,3browser-сценария success. Product code включает минимальный navigation fix, поэтому прежний R13m CI не заменяет этот запуск.
