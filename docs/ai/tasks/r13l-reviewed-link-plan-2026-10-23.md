# R13l — контекстные исправления оставшихся ссылок

Дата:23.10.2026. Статус: **весь пакет согласован и принят на изолированной копии; публикация разрешена пользователем**.

Ветка `codex/local-page-builder`, тот же worktree `r5-zip-operations/humorpedia`, HEAD `8ddd3964633700be03e4a1245ab3cfc79d18b1a8`.

## Результат исследования

После R13k осталось147 unresolved keys/955 literal anchor occurrences на616 source documents. Подготовлено **75 точных правил для73 keys:319 href в247 полях205 published документов, включая10 hidden href в8полях**. Цели:69 существующих published документов и2 существующих каталога. Новых документов, публикаций или изменений приложения не предлагается.

Пользователь23.10.2026 согласовал весь пакет. Исходник R13k неизменен; новая content copy подготовлена. Offline аудит реального resolver подтвердил147→74 unresolved; API/HTML и21 браузерный переход прошли приёмку.74 отложенных keys перечислены в JSON; отсутствие надёжного соответствия не означает автоматически отсутствие самой страницы.

[Машиночитаемые правила и74 holdouts](r13l-reviewed-link-proposal-2026-10-23.json). Source `.cache/r13k/copy/patched.jsonl`,25,620 projected records, SHA256 `2512f09db268aa68fa59248dca8c8078ab4f33084ce0f4f6edadfaa5464df678`. Span plan `.cache/r13l/exact-href-plan.json`, SHA256 `f7fa3352d5e2454d4df048864575eb5bbfdc8ac39e273bbe39a36cfaa157020a`;unsupported0. Raw data/logs в Git не добавляются.

## Существенные решения предлагаемого пакета

- **Одно старое имя — разные цели.** `kvnteam/soyuz`: подписи команды/КВН-контекст ведут на `/kvn/teams/soyuz`, а «Студии Союз» на страницах текстов «Плохих песен» — на `/shows/studiya-soyuz`. `kvn/team`: «команду Флэш-Рояль» в биографии Дениса Гвоздёва — на `/kvn/teams/royalflush`; «команд КВН» на странице отбивок — на каталог `/kvn/teams`. В плане закреплены конкретные поля/spans и точные labels; глобальных alias нет.
- **Город, команда и раунд различаются.** Москва/Казань/Красноярск/Саратов выбраны как города по контекстам рождения, города команды или колонке «Город». Шесть kvnteam-путей не переназначаются на одноимённые команды шоу; show team «Сборная Дагестана» остаётся внутри «Звёзд». `improv-teams/kino` с подписью «Кинопремия» ведёт на раунд шоу, а не на команду КВН «Кино».
- **Имена людей.**38 mappings подтверждены текущим full_name/facts, уникальным published UUID и old_id/публичным MODX-ресурсом. Существующие склонения, фамилии без имени и Катя/Екатерина сохраняются; источник key и остальной контекст проверяются вместе. Не вводится словарь автоматической транслитерации.
- **Два каталога.** `/kvn/teams` и `/quizzes` уже существуют в `frontend/src/App.jsx:173,184` и `STATIC_PATHS` resolver. Им не придумывается Mongo ID и статус published: при приёмке нужны HTTP/React проверки каталогов, а не несуществующий detail GET.
- **Смысл повреждённого URL.** Три `/proekty/` с явной подписью «Stand Up» на ТНТ в биографии/новости Алексея Стаховича предлагается связать с `/shows/standup`; это не alias всего бывшего раздела. Новость «Оцени команду Мастер Муси», сезоны Премьер-лиги2023/2025 и другие ошибочные префиксы сверены с существующими точными документами.

## Что не включено

- Фестивальные и многие league/year URL не заменяются родительскими страницами или новостями. В частности, festival KiViN-2024 не подменяется news KiViN-2024.
- Draft targets (`Мифы Древней Греции`, Roast Battle и др.) не переводятся в published и не добавляются в пакет как опубликованные цели. Существующие правила доступности draft/noindex не меняются.
- `shastun` и `chekhovikukota` остаются holdout: первый сопоставляется как с человеком, так и с fact-name записи дуэта; второй содержит контексты дуэта и «Партизан», где другой кандидат draft. Нужна отдельная проверка идентичности, а не выбор по похожему slug.
- Служебные profile/tag/embed URLs и остальные неподтверждённые имена оставлены как есть. Не выполняются новые импорты или поиск с записью в основную БД.

## План после согласования

| Шаг | Критерий готовности | Модель |
|---|---|---|
|1. Новая копия | Проверить SHA source/plan и247 field preimages; применить319 href/75 правил в новом output, typed IDs и query/fragment сохранены | Sol/high |
|2. Независимая сверка | Все25,620 records: ровно205 docs, только319 spans, hidden10; R13i/media/сезоны и9276 participations сохранены | Luna/high |
|3. Реальный resolver | Измерить остаток; expected147→74, без новых unresolved и без глобальных aliases | Sol/high |
|4. Native API/HTML |205 sources+69 document targets через реальные API/detail HTML;2 каталога через HTTP/React; noindex,UUID DB/network,no host ports,source/media RO | Sol/high |
|5. Browser | Реальные клики по обоим вариантам смешанных keys, городу при коллизии, раунду, show team и новым каталогам; exact target heading,visible anchor,popup handling; hidden не раскрывать | Sol/high |
|6. Приёмка и cleanup | Проверить seeded records до/после кроме views, убрать owned resources, подтвердить чистый main/HTTP/Docker; обновить отчёт | Sol/high |

Код приложения не запланирован к изменению; новые полные unit/build прогоны без причины не требуются. R13k GitHub CI39926764123 на точном8ddd396 прошёл все5jobs и3browser-сценария. Новая native-проверка данных R13l описана в приёмке ниже; прежний CI не подменяет её.

## Точная таблица

| Key | Условие подписи | Canonical target | href |
|---|---|---|---:|
| `igra-na-tnt` | все occurrences этого key | `/shows/igra` | 15 |
| `improv-kom` | все occurrences этого key | `/shows/improv-teams` | 1 |
| `improv-kom/league/hard/2023v` | все occurrences этого key | `/shows/improv-teams/league/hard/2023v` | 1 |
| `improv-teams/beshenniye` | все occurrences этого key | `/shows/improv-teams/teams/besheniye` | 1 |
| `improv-teams/kino` | все occurrences этого key | `/shows/improv-teams/rounds/kino` | 3 |
| `improvkom-tajnyie` | все occurrences этого key | `/shows/improv-teams/teams/tainyie` | 1 |
| `kazan` | все occurrences этого key | `/city/kazan` | 4 |
| `krasnoyarsk` | все occurrences этого key | `/city/krasnoyarsk` | 11 |
| `moscow` | все occurrences этого key | `/city/moscow` | 53 |
| `saratov` | все occurrences этого key | `/city/saratov` | 3 |
| `kvn/premier-liga/2023` | все occurrences этого key | `/kvn/premier-liga/pl-2023` | 38 |
| `kvn/premier-liga/sezon-2025-premer-ligi-kvn` | все occurrences этого key | `/kvn/premier-liga/pl-2025` | 2 |
| `kvn/zvolki` | все occurrences этого key | `/kvn/teams/zlye-volki` | 7 |
| `kvnteam/bortsy` | все occurrences этого key | `/kvn/teams/bortsy` | 3 |
| `kvnteam/kamyzyaki` | все occurrences этого key | `/kvn/teams/kamyzyaki` | 3 |
| `kvnteam/raisy` | все occurrences этого key | `/kvn/teams/raisy` | 3 |
| `kvnteam/severyane` | все occurrences этого key | `/kvn/teams/severyane` | 1 |
| `kvnteam/sssr` | все occurrences этого key | `/kvn/teams/sssr` | 1 |
| `novosti/kvn/team/soyuz` | все occurrences этого key | `/kvn/teams/soyuz` | 2 |
| `oshuitelnoe-xou` | все occurrences этого key | `/shows/medium-quality/ox` | 1 |
| `news/kopiya-otseni-komandu-master-musi` | все occurrences этого key | `/news/otseni-komandu-master-musi` | 2 |
| `proekty` | все occurrences этого key | `/shows/standup` | 3 |
| `proekty/medium-quality/improkom` | все occurrences этого key | `/shows/medium-quality/improkom` | 1 |
| `proekty/medium-quality/money-mic/money-mic-1-y-sezon` | все occurrences этого key | `/shows/money-mic/season1` | 1 |
| `proekty/medium-quality/oshuitelnoe-xou` | все occurrences этого key | `/shows/medium-quality/ox` | 1 |
| `proekty/zvezdy-ntv/team/sbornaya-dagestana` | все occurrences этого key | `/shows/zvezdy-ntv/teams/sbornaya-dagestana` | 1 |
| `shows/igra/team` | все occurrences этого key | `/shows/igra/teams` | 1 |
| `shows/liga-gorodov/team` | все occurrences этого key | `/shows/liga-gorodov/teams` | 1 |
| `shows/zvezdy-ntv/team` | все occurrences этого key | `/shows/zvezdy-ntv/teams` | 1 |
| `smeh` | все occurrences этого key | `/shows/smeh-bez-pravil` | 1 |
| `smeh-sezon-9` | все occurrences этого key | `/shows/smeh-bez-pravil/season9` | 1 |
| `kvnteam/soyuz` | Союз (2014); «СОЮЗ»; «Союз» | `/kvn/teams/soyuz` | 3 |
| `kvnteam/soyuz` | «Студии Союз» | `/shows/studiya-soyuz` | 8 |
| `kvn/team` | команду «Флэш-Рояль» | `/kvn/teams/royalflush` | 1 |
| `kvn/team` | команд КВН | `/kvn/teams` | 1 |
| `kvnteam` | все occurrences этого key | `/kvn/teams` | 1 |
| `quiz` | все occurrences этого key | `/quizzes` | 10 |
| `akhmedova` | все occurrences этого key | `/people/yuliya-akhmedova` | 1 |
| `dorohov` | все occurrences этого key | `/people/denis-dorohov` | 1 |
| `imyagkova` | все occurrences этого key | `/people/irina-myagkova` | 3 |
| `kositsyn` | все occurrences этого key | `/people/roman-kositsyn` | 4 |
| `lshkolnik` | все occurrences этого key | `/people/leonid-shkolnik` | 3 |
| `nkrasnova` | все occurrences этого key | `/people/natalya-krasnova` | 2 |
| `pavelvolya` | все occurrences этого key | `/people/pavel-volya` | 2 |
| `people/aleshin-vlados` | все occurrences этого key | `/people/vlados-aleshin` | 1 |
| `people/aslamova-ekaterina` | все occurrences этого key | `/people/ekaterina-aslamova` | 3 |
| `people/beloborodov-gosha` | все occurrences этого key | `/people/gosha-beloborodov` | 5 |
| `people/davydov-roman` | все occurrences этого key | `/people/roman-davydov` | 3 |
| `people/dmitrypeshkov` | все occurrences этого key | `/people/dmitry-peshkov` | 2 |
| `people/gazal-polina` | все occurrences этого key | `/people/polina-gazal` | 1 |
| `people/ginovyan-samvel` | все occurrences этого key | `/people/samvel-ginovyan` | 1 |
| `people/gudkov-aleksandr` | все occurrences этого key | `/people/aleksandr-gudkov` | 15 |
| `people/korobeynikov-vladislav` | все occurrences этого key | `/people/vladislav-korobeynikov` | 2 |
| `people/kotofeeva-katya` | все occurrences этого key | `/people/katya-kotofeeva` | 5 |
| `people/krasilnikova-ulyana` | все occurrences этого key | `/people/ulyana-krasilnikova` | 1 |
| `people/kudinova-svetlana` | все occurrences этого key | `/people/svetlana-kudinova` | 3 |
| `people/kurmangaliev-karim` | все occurrences этого key | `/people/karim-kurmangaliev` | 3 |
| `people/lomakina-valeriya` | все occurrences этого key | `/people/valeriya-lomakina` | 3 |
| `people/menshikova-ekaterina` | все occurrences этого key | `/people/ekaterina-menshikova` | 3 |
| `people/mirzalizade-idrak` | все occurrences этого key | `/people/idrak-mirzalizade` | 2 |
| `people/morgachev-vladimir` | все occurrences этого key | `/people/vladimir-morgachev` | 3 |
| `people/myasoedov-sergey` | все occurrences этого key | `/people/sergey-myasoedov` | 11 |
| `people/petrov-egor` | все occurrences этого key | `/people/egor-petrov` | 4 |
| `people/pihulya-maksim` | все occurrences этого key | `/people/maksim-pihulya` | 5 |
| `people/polomina-yuliya` | все occurrences этого key | `/people/yuliya-polomina` | 1 |
| `people/saleev-andrey` | все occurrences этого key | `/people/andrey-saleev` | 3 |
| `people/sergeyskachkov` | все occurrences этого key | `/people/sergey-skachkov` | 3 |
| `people/shabanov` | все occurrences этого key | `/people/alexander-shabanov` | 1 |
| `people/tsarukaev-chermen` | все occurrences этого key | `/people/chermen-tsarukaev` | 7 |
| `people/vartanyants-zamrat` | все occurrences этого key | `/people/zamrat-vartanyants` | 6 |
| `people/zulfugarov-kamil` | все occurrences этого key | `/people/kamil-zulfugarov` | 7 |
| `sergei-brysev` | все occurrences этого key | `/people/sergey-brysev` | 2 |
| `shabanov` | все occurrences этого key | `/people/alexander-shabanov` | 1 |
| `shastunimakar` | все occurrences этого key | `/people/shastun-i-makar` | 1 |
| `smatvienko` | все occurrences этого key | `/people/sergey-matvienko` | 3 |

## Проверка предложения

HTMLParser читает фактические исходные anchors и выбирает правило после получения полной подписи, что позволяет раздельные решения для двух смешанных keys. Quoted href offsets — Unicode codepoints. Source/field/plan hashes, exact target IDs/status, SQL identities и границы spans проверяются до согласования; Это проверка предложения до реализации; новые runtime-результаты приведены ниже.

Main, импорт24СМИ, VPS и индексация не меняются. Полный release archive,8 originals posters,111external/embed URL и интеграция остаются отдельными этапами.

Независимая проверка предложения:9/9 PASS, blockers0. Проверены source SHA, все247 preimage hashes/319 exact slices, Unicode offsets/overlap guards, полное соответствие label selectors двум вариантам каждого mixed key, target UUID/old_id/URI и существование static routes. SQL сокращения «ИК» (old_id1618) и «Команды ЛГ» (1771) отличаются от современных отображаемых названий; идентичность подтверждена ID/URI/currentold_urls/full_path и parent hierarchy. Review `.cache/r13l/proposal-review.json`, SHA256 `2ca6929fd190402ebb319152ddb9b05a4e6407bc3bd2a99dddbc00b16d0b8e68`; это статическая сверка без API/browser и без применения.

## Приёмка23.10.2026

HEAD до незакоммиченных изменений `8ddd3964633700be03e4a1245ab3cfc79d18b1a8`. Новых commit/push R13l не выполнялось.

-5 guard tests PASS; copier R13k без изменения алгоритма, закреплены новые source/plan SHA и counts. Копия `.cache/r13l/copy/patched.jsonl`, SHA256 `9d2fcb72a5a893bcb0f0aa4d7a12e88b0575956fd150bbe66508046ed6da2209`;25,620 records,319href/247fields/205docs,hidden10,insert/delete0. Source и span-plan SHA повторно совпали.
- Независимая сверка всех25,620records PASS: изменены только утверждённые319spans;25,415 прочих records, typed IDs и все прочие поля сохранены. R13i/media/сезоны не менялись. Evidence `.cache/r13l/independent-copy-audit.{py,json}`.
- Реальный resolver:2343unique keys/30,816occurrences,2269resolved/**74unresolved**. Остаток равен прежнему147 минус73 согласованных keys; relation findings0,122seasons и9276participations совпали без missing/stale/changed/duplicate. Evidence `.cache/r13l/audits/{summary,content-audit,relations-audit}.json`.
- Native run `009f559f3d5a4353b9f458d5b46c1637`: **205sources+69published document targets API/HTML200**, noindex. Оба каталога HTTP200/noindex, реальные listing API200: КВН24items/1123total, квизы11items/11total. UUID DB/internal network/no host ports,indexing=false,source/media RO; настоящий app lifespan.
- **21 реальный браузерный переход PASS**, exact normalized target h1, pageerrors0. Шесть actual source kinds: people/articles/teams/shows/news/kvn;15 дополнительных контекстных сценариев: оба варианта Союза, команда/каталог, alias каталогов, четыре города, раунд, show team, канал, команда КВН и инверсия имени. Штатная активная категория «Команды КВН» проверена. Выборочные screenshots обеих страниц Союза и каталога просмотрены; это не полный визуальный аудит. Четыре внешних userapi-origin перехвачены/заблокированы: доступность внешних изображений и111external/embed URL этим прогоном не подтверждается.
- Before/after Mongo сверка25,620records PASS вне штатных views; cleanup containers=[],network/imagesremoved,error=null, label-owned ресурсов не осталось. Основной стенд: чистый main `ca46155a9640d4723c07b9fd1762a6e639563414`, прежние IDs/StartedAt всех трёх контейнеров, restarts0, Mongo healthy, localhost3000 и8001/api/health200. Импорт24СМИ и VPS не затрагивались.

Evidence: `.cache/r13l/acceptance-final.json`, `native-pages/009f559f3d5a4353b9f458d5b46c1637/{result,cleanup}.json`, `closed/{links-http,links-browser}.json`, `main-final.json`. В Git входят только документация/утверждённые mappings; projected snapshot, harness и raw logs остаются ignored. Backend/frontend/scripts не изменены; новые полные unit/build/CI не запускались без изменения продукта. Сохранён результат R13k GitHub39926764123 на8ddd396:5jobs/3browser-сценария success.

Независимый final-scope review: **PASS_WITH_BOUNDARIES**, blockers0; `.cache/r13l/final-scope-review.json`, SHA256 `cbca4ae367bfaffd5945a9eff58eff7e9a5dfdec659dbcafdb301b785e0a2f5c`. Scope: static/artifact review завершённого native-run и отдельная полная сверка копии.

### Границы и исправления проверяющего стенда

Все10hidden spans проверены offline; parent API проверяет ожидаемые множества target URL, а не каждое скрытое поле ответа. Hidden-модули не включались в UI. Браузер проверил21 выбранный переход, а не319href. Legacy-модули сезонов намеренно подавлены React по текущему контракту; их spans покрыты offline/API, generic KVN case взят с отображаемой страницы отбивок. Проверка foreign-agent marker предусмотрена условно, но в этой выборке нет target с flag=true, поэтому marker coverage не заявляется.

Первый run `2f2654d8030d4b908edf95cb65c357c4` не закончил startup: test-only harness прочитал92MB целиком и получил OSError12. Только в ignored harness seed/verify переведены на потоковые пакеты ≤200records или1MiB на kind. Ownership-проверка разрешила остановку только owned checker; ресурсы удалены, но shutdown guard сохранил ошибку незавершённого lifespan. HTTP/browser этого запуска не выполнялись.

Промежуточные runs `80f158de68104a1290ed62632dedc2c3`, `a38a91cf55d04e0c8fce110c9b71ac0a`, `c57b7056f8b8472ea96b48d2c43f72b5` прошли HTTP/API, но остановились на дефектах выборки/локатора checker: потеря source kind, suppressed legacy field, detach при React render. Исправлены только тестовые scripts: preferred field+kind assertions, видимый KVN context, ожидание networkidle и живой locator по href/точной подписи. Во всех трёх cleanup error=null. Source/output/plan неизменны; эти прогоны не выдаются за полную приёмку.

У native fixture остаётся предупреждение unique-index `kvn.id`: duplicate null IDs в импортированной projection. Startup завершён, проверяемые API/browser прошли; отсутствие предупреждений и полноценная Mongo-миграция не заявляются. Эта projected copy не содержит полного release archive/roster_import.

### Следующий этап

Пользователь разрешил отдельный commit/push R13l с документацией и проверкой GitHub CI. Публикация на момент этой контрольной точки ещё не выполнена.74 неподтверждённых keys сохранены в JSON без автоматической подмены.8 оригинальных season posters,111external/embed URL, полноценный release archive, интеграция и dev-sync после интеграции остаются отдельными этапами. Main и VPS сейчас не переключать; индексация остаётся выключенной.
