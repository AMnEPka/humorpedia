# R13j — восстановление внутренних ссылок: доказательства и план

Дата плана:22.10.2026; реализация и приёмка:23.10.2026. Worktree `r5-zip-operations/humorpedia`; ветка `codex/local-page-builder`; HEAD `ef2a704df959d37ca5a92695a1481809768a3737`.

## Статус

R13i с документацией опубликован отдельным `ef2a704`. [GitHub CI39847257115](https://github.com/AMnEPka/humorpedia/actions/runs/39847257115) completed/success на точном SHA, attempt1: все5 jobs и три browser-сценария success. Evidence `.cache/r13j/r13i-ci-{run,jobs}-final.json`.

R13j продолжает очередь ссылок [R13g](r13g-migration-readiness-2026-10-22.md). Прочитана окончательная копия [R13i](r13i-identity-corrections-2026-10-22.md) SHA `7439abd0b81796875960d270735d3efd1f0acea2738d84dcd61b740862e58aeb`. Подготовлен [точный proposal manifest](r13j-link-repair-proposal-2026-10-22.json). **Обе согласованные части выполнены и приняты23.10.2026.** Quiz old_url lookup исправлен, на производной копии заменены759 href в429 полях379 документов. Остальные поля25,620 записей сохранены. Full backend1200 passed/16 skipped; native API/HTTP379 source+95 target,14 browser-сценариев PASS. Пользователь поручил отдельный commit/push R13j и проверку CI. Основной main, первичная БД/media, импорт24СМИ и VPS не затрагивались. Индексация выключена.

## Что подтвердилось

- R13g содержал344 ключа с None:194 с одним кандидатом последнего slug,21 с несколькими,129 без кандидата. None по контракту превращает ссылку в текст; это не утверждение о344 HTTP404.
- Из первичного `humorbd.sql` извлечён только публичный индекс `modx_site_content`:3374 resource rows,49 columns,0 unparsed. Контроль2540=сезон2008 совпал. Пользовательские/служебные SQL-таблицы не извлекались в evidence.
- Для88 коротких ключей найден ровно один MODX resource с точным alias, и его ID совпадает с old_id опубликованной canonical страницы. Проверены все различные тексты anchor: имена/названия/географические подписи; локальные target IDs зафиксированы. Это сильнее единственного совпадения последнего slug. Примеры: `armavir`→`/city/armavir`, `anton-baryilik`→`/people/anton-baryilik`, `standup`→`/shows/standup`. Падежи, прежние названия городов и подписи вроде «Краснодарский край» сохраняются как авторский текст; пакет исправляет путь того же MODX resource, не редактирует географические факты.
- Для остальных104 из194 такого полного основания пока нет. `kvn/kivin/kivin-2024` нельзя направлять в единственную news-карточку: SQL resource1614 — фестиваль, а news имеет old_id2377. `kvn/teams/vladivostok` подписан «Сборная Владивостока», поэтому единственный city-кандидат неверен. Склеенный href `liga-gorodov/team/izhitsa.htmlhttps:/humorpedia.ru/kvn/team/macleod` подписан «Ижица»; выбор `macleod` по последнему slug неверен. Эти случаи не входят в88.
- Помощник независимо разобрал21 ambiguous keys/48 candidate docs.4 quiz-ключа имеют точный old_urls provenance; у2 ссылок об Уральской лиге подходящего кандидата нет, у15 остаются только контекстные подсказки. Это review evidence, не разрешение автоматических замен. Artifact `.cache/r13j/ambiguous-review.json`.

## Подтверждённый дефект quiz old_urls

`backend/services/link_resolver.py::OLD_URL_COLLECTIONS` исключает quizzes. При этом URL_BUILDERS знает quizzes, а `backend/routes/redirects.py::lookup_redirect` ищет old_urls в quizzes. Уточнение по коду23.10: `link_key` сохраняет имеющийся `.html`; семь найденных исходных ключей уже хранятся без суффикса. Pattern fallback требует `.html`, поэтому не восстанавливает такие ссылки. Для big-show даже вариант с `.html` не помогает: canonical slug викторины другой. Документированный контракт старых URL соблюдается не во всех путях.

Read-only probe исполнил изолированную копию того же Python-модуля с единственным добавлением quizzes в old_url lookup. Продуктовый файл не редактировался. На всех2577 текущих ключах:

- было2233 resolved, стало2240; ровно7 None→правильный quiz target;
- остальные2570 ключей не изменились;
- конкурирующих quiz old_urls с другими неархивными документами0.

| Ключ | Цель по точному old_urls |
| --- | --- |
| `quiz/big-show` | `/quizzes/bolshoe-shou` |
| `quiz/humorquiz-1` | `/quizzes/humorquiz-1` |
| `quiz/humorquiz-2` | `/quizzes/humorquiz-2` |
| `quiz/humorquiz-3` | `/quizzes/humorquiz-3` |
| `quiz/humorquiz-4` | `/quizzes/humorquiz-4` |
| `quiz/improkom` | `/quizzes/improkom` |
| `quiz/kvn-xx-veka` | `/quizzes/kvn-xx-veka` |

Особенно показателен big-show: правильный quiz имеет другой canonical slug, поэтому matching по последнему slug выбирал бы шоу. Здесь данные менять не требуется. Это статическое исполнение реального resolver с read-only in-memory adapter, не native API/browser-приёмка нового исправления.

## Выполненный пакет

1. Исправить quiz old_url lookup в коде, сохранив существующие приоритеты и фильтр archived. Без общего поиска по slug и без новых redirect rules.
2. На отдельной производной копии точно заменить только href88 подтверждённых коротких ключей на canonical URLs из manifest. **759 anchor occurrences,429 HTML fields,379 published documents**;46 occurrences находятся в скрытых модулях и включены в точный manifest для согласования.88 targets:42 city,30 shows,10 people,3 teams,2 kvn,1 news. Все targets published; исходные SQL resources published и не deleted.

HTMLParser зафиксировал exact quoted href spans и SHA256 полей. Меняются только значения href: текст/вложенные теги, quote style, target/rel и остальные атрибуты остаются; query/fragment сохраняются. Неподдержанных href в выбранном пакете0. Полный неприменённый field plan `.cache/r13j/exact-href-plan.json`, SHA `028c5f983d35c2b48f3a1eee77077ca7d22ba249663c496cc0f59123c94bfd20`. На этапе исследования данные не переписывались; после согласования применён этот точный field plan только на производной копии.

Рекомендован именно ограниченный список. Не добавлять общий slug fallback; не делать автоматическую подстановку104+21+129 оставшихся keys. После quiz-fix7 ключей уйдут из этих очередей по точному alias lookup; это не согласование остальных кандидатов.

## Выполненный согласованный план

| Шаг | Готовность / проверка | Модель |
| --- | --- | --- |
| [x] 1. Зафиксировать объём | Пользователь23.10.2026 подтвердил обе части: quiz contract +88 exact href на копии | Sol/high |
| [x] 2. Регрессия quiz | Воспроизвести потерю опубликованного quiz при совпадении slug с news/show; правка lookup. Проверить HTML/.html-normalized href, сохранение labels/query/fragment и отсутствие ссылки на archived quiz, текущие canonical/old_url приоритеты | Sol/high |
| [x] 3. Копия данных | Fresh derived copy из R13i SHA, typed IDs + field preimages/count guards; отказ при drift/повторе/неожиданном span. Применить только утверждённые href.25,620 records, никаких delete/rename/merge | Sol/high |
| [x] 4. Offline acceptance | Сравнить все документы и разрешённые spans: кроме href всё равно,7 quiz без data edits; R13i identities и104 media fields R13h неизменны. Повтор resolver исходных и итоговых keys:7 исходных None→quiz target,88 коротких keys должны исчезнуть из выбранных href после замены. Ожидаем249 unresolved вместо344 при полном покрытии (88+7), а не новый resolver fallback для88 aliases; список изменений точный. HTTP проверять отдельно | Sol/high |
| [x] 5. Native acceptance | Настоящие app/Nginx/owned Mongo без primary writes. API/HTTP всех95 targets и379 source pages; browser representative по каждому типу плюс quiz/news/show collision и hidden-module граница. Проверить canonical переходы и noindex, отсутствие JS errors; full release/roster_import ограничения сохранить | Sol/high |
| [x] 6. Доставка | Документировать counters/hashes/действительный охват/cleanup; проверить primary main и storage read-only. Commit/push нового пакета — по отдельному поручению | Sol/high |

Этот документ не разрешает full release transfer, main/dev-sync, включение индексации или VPS. Demo-policy10 IDs применяется при будущем полном переносе;8 оригинальных season posters и111 external/embed URLs остаются отдельными очередями. Исходная копия R13i неизменна; продуктовый diff ограничен quiz lookup и регрессионными тестами.

## Точный список88 href mappings

Поля, source references, raw href variants и подписи приведены в proposal JSON. Числа ниже — реальные anchor occurrences, включая повторы одного ключа внутри поля. Первоначальный R13g occurrence count считал один key на поле и мог быть меньше.
| Ключ | Цель | MODX ID | href |
| --- | --- | ---: | ---: |
| `anton-baryilik` | `/people/anton-baryilik` | 1020 | 1 |
| `armavir` | `/city/armavir` | 2082 | 7 |
| `astrakhan` | `/city/astrakhan` | 2107 | 8 |
| `big-show` | `/shows/big-show` | 1656 | 7 |
| `big-vopros` | `/shows/big-vopros` | 1651 | 2 |
| `bishkek` | `/city/bishkek` | 2114 | 1 |
| `bitva-za-vremya` | `/shows/bitva-za-vremya` | 1661 | 24 |
| `bryansk` | `/city/bryansk` | 2101 | 5 |
| `bryuxoveczkaya` | `/city/bryuxoveczkaya` | 2083 | 3 |
| `central-microphone` | `/shows/central-microphone` | 1648 | 3 |
| `chelyabinsk` | `/city/chelyabinsk` | 2090 | 19 |
| `chita` | `/city/chita` | 2113 | 2 |
| `comedywoman` | `/shows/comedywoman` | 1622 | 21 |
| `comigration` | `/shows/comigration` | 3022 | 5 |
| `comment-out` | `/shows/comment-out` | 1634 | 2 |
| `daniil-pehtelev` | `/people/daniil-pehtelev` | 972 | 3 |
| `denis-spis` | `/people/denis-spis` | 993 | 2 |
| `dgu` | `/kvn/teams/dgu` | 1078 | 1 |
| `dmitry-peshkov` | `/people/dmitry-peshkov` | 182 | 1 |
| `donetsk` | `/city/donetsk` | 2099 | 1 |
| `dvij` | `/shows/medium-quality/dvij` | 1662 | 8 |
| `ekb` | `/city/ekb` | 2089 | 22 |
| `erevan` | `/city/erevan` | 2081 | 1 |
| `gomel` | `/city/gomel` | 2102 | 3 |
| `iks` | `/shows/iks` | 2182 | 1 |
| `improv-comedy` | `/shows/improv-comedy` | 1632 | 2 |
| `irkutsk` | `/city/irkutsk` | 2088 | 9 |
| `kemerovo` | `/city/kemerovo` | 2106 | 10 |
| `khabarovsk` | `/city/khabarovsk` | 2111 | 1 |
| `kharkiv` | `/city/kharkiv` | 2085 | 4 |
| `kirov` | `/city/kirov` | 2087 | 5 |
| `kontakti` | `/shows/kontakti` | 1714 | 1 |
| `krasnodar` | `/city/krasnodar` | 2092 | 18 |
| `krivoy-rog` | `/city/krivoy-rog` | 2110 | 3 |
| `kursk` | `/city/kursk` | 2074 | 18 |
| `kyiv` | `/city/kyiv` | 2096 | 3 |
| `leningradskij-stand-up-club` | `/shows/leningradskij-stand-up-club` | 1647 | 2 |
| `liga-ploxix-shutok` | `/shows/liga-ploxix-shutok` | 1633 | 1 |
| `maria-komarova` | `/people/maria-komarova` | 511 | 1 |
| `mezhdu-nami-show` | `/shows/mezhdu-nami-show` | 1639 | 21 |
| `milan-isaev` | `/people/milan-isaev` | 988 | 2 |
| `miniatures` | `/shows/miniatures` | 1655 | 17 |
| `minsk` | `/city/minsk` | 2075 | 30 |
| `ml-2019` | `/kvn/ml-kvn/ml-2019` | 1573 | 1 |
| `ml-kvn` | `/kvn/ml-kvn` | 1490 | 1 |
| `murmansk` | `/city/murmansk` | 2094 | 6 |
| `n-novgorod` | `/city/n-novgorod` | 2091 | 17 |
| `ne-v-forme` | `/kvn/teams/ne-v-forme` | 1427 | 1 |
| `neryungri` | `/city/neryungri` | 2076 | 2 |
| `nikolaj-grigorev` | `/people/nikolaj-grigorev` | 997 | 1 |
| `novosibirsk` | `/city/novosibirsk` | 2080 | 17 |
| `nyagan` | `/city/nyagan` | 2077 | 1 |
| `odessa` | `/city/odessa` | 2095 | 2 |
| `odnazhdyi-v-rossii` | `/shows/odnazhdyi-v-rossii` | 1621 | 31 |
| `osp-studiya` | `/shows/osp-studiya` | 1645 | 4 |
| `penza` | `/city/penza` | 2086 | 2 |
| `perm` | `/city/perm` | 2108 | 9 |
| `please-ne-rasskazivai` | `/shows/please-ne-rasskazivai` | 1657 | 1 |
| `po-situaczii` | `/kvn/teams/po-situaczii` | 1416 | 1 |
| `prozharka-na-tnt` | `/shows/prozharka-na-tnt` | 1617 | 5 |
| `rassmeshi-komika` | `/shows/rassmeshi-komika` | 1646 | 18 |
| `roman-maslov` | `/people/roman-maslov` | 293 | 1 |
| `rostov-on-don` | `/city/rostov-on-don` | 2093 | 18 |
| `ryazan` | `/city/ryazan` | 2098 | 3 |
| `samara` | `/city/samara` | 2103 | 11 |
| `smex-v-bolshom-gorode` | `/shows/smex-v-bolshom-gorode` | 1641 | 11 |
| `spb` | `/city/spb` | 2070 | 41 |
| `standup` | `/shows/standup` | 1637 | 24 |
| `standup-underground` | `/shows/standup-underground` | 1640 | 4 |
| `standupwomen` | `/shows/standupwomen` | 1624 | 4 |
| `stavropol` | `/city/stavropol` | 2078 | 12 |
| `stendap-artyuhova` | `/news/stendap-artyuhova` | 2845 | 2 |
| `studiya-soyuz` | `/shows/studiya-soyuz` | 1638 | 10 |
| `superliga` | `/shows/superliga` | 1652 | 76 |
| `tambov` | `/city/tambov` | 2097 | 10 |
| `tomsk` | `/city/tomsk` | 2073 | 18 |
| `tyumen` | `/city/tyumen` | 2100 | 6 |
| `ubojnaya-liga` | `/shows/ubojnaya-liga` | 1628 | 17 |
| `ubojnoj-nochi` | `/shows/ubojnoj-nochi` | 1620 | 6 |
| `ubojnyij-vecher` | `/shows/ubojnyij-vecher` | 1623 | 1 |
| `uralskie-pelmeni-show` | `/shows/uralskie-pelmeni-show` | 1643 | 7 |
| `viktor-shhetkov` | `/people/viktor-shhetkov` | 1001 | 5 |
| `vladikavkaz` | `/city/vladikavkaz` | 2109 | 2 |
| `vladivostok` | `/city/vladivostok` | 2084 | 16 |
| `volgograd` | `/city/volgograd` | 2112 | 4 |
| `voronezh` | `/city/voronezh` | 2072 | 18 |
| `yaroslavl` | `/city/yaroslavl` | 2105 | 10 |
| `zoya-yarovitsyna` | `/people/zoya-yarovitsyna` | 189 | 1 |

## Приёмка23.10.2026

HEAD до незакоммиченных изменений `ef2a704df959d37ca5a92695a1481809768a3737`. Продуктовый diff: `backend/services/link_resolver.py` — quizzes добавлена в конец существующего old_url lookup, приоритеты других collections сохранены. `backend/tests/test_link_resolver_quizzes.py` —7 регрессионных случаев, включая отличающийся canonical slug викторины и совпадающий slug news/show.

- **RED→GREEN:** до исправления3 failed/4 passed (потеря ссылок на quiz); после исправления новые quiz tests и существующий MODX suite42 passed. Сохранены labels/вложенная разметка/attrs/query/fragment; archived/missing quiz не превращается в ссылку, прежние приоритеты old_url/direct path действуют.
- **Полный backend:**1200 passed,16 skipped,28.00s,1 известный PendingDeprecationWarning python_multipart. Evidence `native-pages/7065f5c18d86471a9f825b7f8052ce98/backend-suite.log`. Использована отдельная Mongo8.0.32 с integration flags, без доступа к main. WebP MIME/HEAD/304 regression также PASS в release image. Frontend source не менялся, используется прежний R13f build; новая frontend-сборка/Jest не требовались.
- **Подготовка копии:** `py -3.14 .cache/r13j/test-prepare-copy.py` —5 tests PASS: Unicode codepoint offsets, field drift/reapply refusal, typed IDs, boundaries/overlaps и отказ перезаписывать существующий output. `prepare-copy.py` привязан к source/plan SHA, проверяет exact counts и сохраняет HTML bytes вне разрешённых href. Применено ровно759 замен в429 полях379 published documents, включая46 hidden occurrences;25,620 records, без вставок/удалений.
- **Независимая сверка:** отдельный `audit-final.py` восстановил ожидаемые строки алгоритмом concatenation по spans и сравнил все25,620 BSON records. Изменены только379 docs; остальные25,241 projected records идентичны, все прочие поля изменённых docs равны исходнику. Типы IDs, R13i corrections и104 media fields R13h сохранены. Исходные SHA неизменны. Canonical seasons и9276 participations совпали:missing/stale/changed/duplicate0; relation findings0.
- **Resolver после копии:**249 unresolved вместо344 (7 восстановлены через quiz old_urls,88 коротких keys заменены в данных). Уникальных keys стало2498, resolved2249; уменьшение общего числа объясняется схлопыванием уже существовавших canonical keys. Остальные спорные keys, включая festival→news и team→city, не переназначены. Это offline проверка реального resolver на копии, не HTTP-утверждение о249 оставшихся URL.
- **Финальный native run:** `9b782104cb9f41f792fe85220c30bdcc`. Настоящий release app/lifespan, Nginx, owned UUID Mongo/network без host ports. Serving включён только в пилоте, indexing=false; source snapshot и основные media volumes/R13h staging — read-only.
- **API/HTTP:**379/379 исходных страниц и95/95 целей200/noindex; обычный API содержит ожидаемые canonical href.95 targets published. Ни ответы, ни маршруты production API не подменялись. Test-only state/verify routes проверяют UUID ownership и используются только на внутренней сети.
- **Browser:**14 сценариев: реальные клики из6 source types (people/articles/teams/shows/news/kvn), quiz-collision из новости на `/quizzes/bolshoe-shou`, открытие7 quiz targets. Все переходы на ожидаемые canonical paths; pageerrors0. Визуально выборочно просмотрены screenshot people и quiz-big-show. Это не browser-обход всех379 страниц и не полная UX-приёмка.
- **Hidden/HTML-границы:**46 hidden href проверены exact-span сравнением offline; обычный API проверен для всех родительских страниц на наличие ожидаемых target href, без заявления о каждом hidden поле ответа. Скрытые модули не включались принудительно в публичном интерфейсе. Поля25,620 seed records проверены native до/после запросов: отличаются только штатные views counters; контент/связи не изменялись. Проекционная копия сохраняет ограничения R13i (`roster_import` не включён); full release archive не готовился.
- **Cleanup:** writers штатно остановлены; owned DB удалена по marker, containers=[],error=null,network_removed=true,оба owned images удалены. Docker после завершения не нашёл ресурсов с label R13j.

Первый native run7065f5c18d86471a9f825b7f8052ce98 завершил full backend и API/HTTP379+95, но browser ожидал h1 на странице quiz, где текущий UI использует CardTitle/div. Исправлено только ожидание checker по реальному quiz.title; финальный run9b782104cb9f41f792fe85220c30bdcc успешен. Продуктовый код между прогонами не менялся, full backend повторно не запускался. Заголовки/UX quiz в R13j не изменялись. Cleanup обоих прогонов успешен; первый failure не выдаётся за browser success.

Final copy `.cache/r13j/copy/patched.jsonl`, SHA256 `90e38c00f870bcbf28702675097eb752b8304148f5556d61d481e8985f9e4ea7`.
Source R13i SHA256 `7439abd0b81796875960d270735d3efd1f0acea2738d84dcd61b740862e58aeb` неизменен.
Evidence `.cache/r13j/{acceptance-final.json,quiz-red.log,quiz-green.log}`, `copy/{acceptance,pages}.json`, `audits/{summary,content-audit,relations-audit}.json`, `native-pages/9b782104cb9f41f792fe85220c30bdcc/{result,cleanup,commands}.json`, `closed/links-{http,browser}.json` и screenshots. Raw data/logs в Git не добавляются.

Повтор native: `BROWSER_BUILD_DIR=.cache/r13f/frontend-build node .cache/r13j/run-native.cjs` (переменную задать синтаксисом оболочки). По умолчанию выполняется полный backend suite; флаг R13J_SKIP_VERIFIED_BACKEND применялся только для повторной browser-приёмки на том же продуктовом коде. Для новой data preparation требуется новый пустой output; исходную копию и evidence не перезаписывать. Main dev-sync из worktree не запускать.

Финальный read-only контроль: основной checkout clean main `ca46155a9640d4723c07b9fd1762a6e639563414`; прежние backend/frontend/Mongo container IDs/StartedAt, restarts0, HTTP3000 и8001/api/health200. Импорт24СМИ и VPS не изменялись. Публикация R13j с документацией разрешена пользователем; новый CI проверяется после push.

Следующий остаток очереди:249 unresolved keys. Для проанализированных prefix/path/склеенных href подготовить новые точные доказательства и mappings; не применять общий slug fallback. Поиск8 оригинальных season posters,111 external/embed URL, полный release с demo-policy и интеграция — отдельные этапы; main/VPS пока не переключать.

## Публикация и продолжение23.10.2026

R13j вместе с документацией опубликован отдельным коммитом `5ab9154c14f475ef06fe8aa3ec34aaa786e52821`, push в `origin/codex/local-page-builder`. [GitHub CI39914279710](https://github.com/AMnEPka/humorpedia/actions/runs/39914279710) completed/success, attempt1 на точном SHA: backend/frontend/windows-tools/mongodb-integration/browser-smoke — success; все3 browser-сценария success. Evidence `.cache/r13k/r13j-ci-{run,jobs}-final.json`.

Продолжение — [R13k](r13k-exact-href-plan-2026-10-23.md):102 mappings согласованы и приняты только на новой копии,782href/548fields/422docs,hidden9;unresolved147,API/HTML422+99/browser15 PASS. R13j snapshot неизменен. Публикация R13k разрешена; main/импорт24СМИ/VPS не затрагиваются.
