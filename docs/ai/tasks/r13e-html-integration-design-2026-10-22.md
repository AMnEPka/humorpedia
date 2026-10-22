# R13e: схема подключения публичного HTML

Дата:22.10.2026. Статус:**схема и implementation утверждены, R13e реализован локально**. [Приёмка](r13e-html-integration-acceptance-2026-10-22.md); commit/push/main integration/deploy не выполнены. Worktree `C:/Users/rdp6126443.gmail.com/.codex/worktrees/r5-zip-operations/humorpedia`, ветка `codex/local-page-builder`. R13d опубликован `3b6146ffe420afbaa697ae2f2eba607c8b258f6c`, отдельное исправление строгой CI-сборки —`98f37bb7c7943ae1da976c6f803fb50425e2b6e0`. CI исправленного SHA completed/success, все5jobs success; ссылка и точный результат ниже.

Основной текст ниже сохраняет историческую утверждённую схему до реализации; текущий результат и runtime evidence —в [приёмке R13e](r13e-html-integration-acceptance-2026-10-22.md).

## Цель и уже принятые решения

Перейти от отдельного пилотного приложения к проверяемой схеме выдачи HTML перед будущей интеграцией. Первый scope остаётся `/people/:slug` и `/articles/:slug`. Согласованы схема A (HTML fallback вне root + createRoot + обычный content GET), canonical `https://humorpedia.ru`, published-only indexing, noindex для draft/missing status,404 для archived/unknown в покрытых маршрутах. Повторное чтение HTML+API принято в R13c, метаданные приходят opt-in в том же API response. Изменять эти решения здесь не предлагается.

Исторический результат этапа проектирования —согласованная схема и границы implementation-плана. Ни основной стенд, ни production routing этим документом не изменены. Изолированная проверка сейчас; полный dev-sync —после отдельно разрешённой интеграции. Основной checkout остаётся main, импорт24СМИ/его workers не редактируются, VPS/DNS/сертификаты/домены не переключаются.

## Факты по checkout

| Точка | Что уже есть и чего нет |
|---|---|
| `backend/html_react_pilot.py` + `scripts/seo/react_pilot_server.py` | Guarded app с тестовыми API allowlist/UUID seed/cleanup; это не production entrypoint и не служба для постоянного запуска |
| `backend/server.py`, API registration/static mounts | Полное API, uploads/media/images; публичные HTML routes не зарегистрированы. Lifespan уже запускает views и source scheduler, поэтому новый HTML-код не должен запускать второй lifecycle |
| `frontend/nginx.conf` | Assets/config.js/frontend health и SPA fallback; `error_page 404 /index.html` может скрыть upstream404, если просто добавить proxy без разделения обработки |
| `scripts/vps-test/nginx.conf` + `compose.yml` | Отдельный VPS test release: frontend image с собственным Nginx config, API/media/images/uploads в backend. Backend образ пока не содержит frontend template |
| `scripts/vps-test/https-public.conf` | Репозиторная схема внешнего test nginx: global X-Robots-Tag noindex/nofollow и Disallow:/; это не live-проверка VPS |
| `frontend/vite.config.mjs` | Текущий dev proxy/HMR; его нельзя выдавать за production gateway |
| `frontend/index.html` | Общая SPA-оболочка; только isolated renderer R13d заменяет head/ru и вставляет fallback |
| R13c | 9 отсутствующих выбранных media-файлов,13 страниц без своего image,36 нейтральных description fallback. Массовая редактура не разрешена; тестовый1×1 PNG не является production share image |

## Варианты

| Вариант | Цена и эффект | Решение |
|---|---|---|
| **A. FastAPI HTML на существующем backend + Nginx для assets** | Повторно использует проверенные reader/metadata/handoff, без Node-сервиса; требует доставки того же template и точного порядка маршрутов | **Рекомендую** для следующего ограниченного плана |
| B. Оставить HTML pilot отдельной постоянной службой | Ещё один backend/lifecycle/health/config, рассинхронизация сборок и риска ownership/cleanup тестового кода | Не переносить fixture harness в production |
| C. React SSR/Bootstrap или prerender | Меняет lifecycle/учёт просмотров или требует snapshot/invalidation; этого не требовал результат R13d | Отдельный архитектурный инкремент при новых требованиях |

## Предлагаемая схема A

### Владельцы и порядок обработки

Nginx обслуживает immutable assets своей сборки. Единственный существующий FastAPI backend при явно включённом HTML-режиме отдаёт покрытые detail HTML/legacy redirects, API metadata, robots/sitemap. Тестовый seed/UUID cleanup/listener/control endpoints R13d в production app не регистрируются.

| Запрос | Владелец и контракт |
|---|---|
| `/api/*` | Штатное API, auth/dependencies/JSON/errors и учёт просмотров сохраняются |
| `/uploads/*`, `/media/*`, `/images/*` | Прежний backend/static/media-router;404 файлов не подменять index.html |
| `/assets/*`, icons, static public files | Nginx текущей immutable сборки; отсутствующий asset —404, без HTML fallback |
| `/config.js` | Один runtime config/no-store. HTML mode и API opt-in согласованы; секретов/fixture flags нет |
| `/people/:slug`, `/articles/:slug` | HTML из общего reader, fixed canonical,200/301/404/503, no-store; GET не считает просмотр. Не маскировать ошибки как SPA200 и не фильтровать ботов отдельно от людей |
| Известные legacy URL этих двух типов | Anonymous resolver и301 только к разрешённой цели. Namespace `/api`,assets/media/admin/preview никогда не направляется в HTML legacy catch-all |
| `/robots.txt`, `/sitemap.xml` | Текст/XML с явными Content-Type; staging закрыт, sitemap не перечисляет draft/missing/archived/admin/search/preview/остальные типы |
| Остальные существующие React routes | Прежняя SPA. Автоматическое включение HTML или изменение их индексируемости не входит в этот инкремент |

Последовательность регистрации: API и health → native media/static → служебные HTML endpoints → покрытые detail/legacy → только затем допустимый SPA/unknown fallback. Классификация старых адресов отделяется от признака «любой неизвестный URL»: сохранить прежние news/teams/shows/КВН full_path, не отправлять весь сайт в двухтипный reader. Финальный универсальный404/HTML для остальных типов —следующий scope, а не обещание этого частичного включения.

### Как включается proxy и сохраняется выключенный режим

Один release-параметр `PUBLIC_HTML_ENABLED` передаётся backend и frontend gateway. Из него при старте frontend формируются согласованные Nginx include и runtime config; ручного независимого переключения трёх файлов не предполагается. Согласованность режима входит в gateway readiness.

- **false (default):** Nginx использует прежний SPA fallback, не включает proxy detail/robots/sitemap/legacy; runtime head owner выключен, optional HTML routes backend не регистрируются. Контроль —те же запросы/статусы/API, что в R13d flag=false smoke.
- **true:** отдельные proxy locations направляют ровно detail people/articles (не каталоги), exact robots/sitemap в backend; API/media/assets/health/admin остаются отдельными правилами более высокого приоритета. Для этих proxy запрещена подмена upstream404/503 на index.html. `/config.js` включает общий head owner того же режима.
- Для extensionless legacy вне detail namespace нужен **внутренний dispatch**, а не проксирование всего сайта в двухтипный reader. После исключения API/static/admin gateway перед обычным SPA fallback спрашивает anonymous resolver: `redirect` →301, `known_unavailable` →404, `no_match` →прежний SPA handler, `error` →503. Эти исходы различимы; нельзя превращать архивную/приватную известную цель в no_match и SPA200. Внутренний транспорт/служебный URL не публикуются как ещё один content API; точные имена, кодирование ответов и тесты —в implementation-плане.
- Ни один internal location/endpoint не позволяет миновать auth существующих API или выдать приватный target. Прямой запрос служебного gateway namespace извне —404. Неизвестный covered detail остаётся404, даже если обычная SPA могла бы его обработать.

Это механизм переключения в **репозиторной схеме**, а не распоряжение менять действующие Nginx/Compose на VPS или main. Пока он не реализован/не принят, текущие файлы serving не редактируются.

### Настройки и согласованность release

Предлагаемые имена для implementation-плана: `PUBLIC_HTML_ENABLED=false` и `SEARCH_INDEXING_ENABLED=false`; это проектный контракт env vars, реализованный в R13e. HTML serving и разрешение индексации —разные переключатели. Комбинация SEARCH_INDEXING_ENABLED=true при PUBLIC_HTML_ENABLED=false запрещена: конфигурационная проверка до запуска отклоняет её; тихого разрешения индексации без HTML нет. Frontend head owner включается нейтральным runtime признаком режима; совместимость с строгим pilot flag остаётся в isolated harness. При выключенном serving —нынешние API/UI/прокси, без опции metadata у обычного клиента.

Backend и frontend должны получать template/assets из **одного** build/release artifact. Предпочтительно один build stage, из которого template/manifest и необходимые public metadata-ресурсы копируются в backend image, полный build —в frontend image. Никакого скачивания index.html по runtime HTTP и никаких main checkout bind mounts. Проверка release identity входит в HTML readiness; при несовпадении template/chunks или отсутствии template —503/noindex, без ложного ready/SEO200. Health API и готовность HTML различать.

Существующий backend lifespan остаётся единственным владельцем views/Mongo; HTML reader работает anonymous и не запускает scheduler/flush сам. Новая регистрация не меняет импорт24СМИ и его конфигурацию. В интеграционном harness —только собственная UUID DB/media/network, отсутствие import jobs/credentials, блокированный внешний egress; проверка cleanup после остановки native writers.

### HTTP, headers и crawl policy

HTML/error responses: no-store, явные robots, фиксированный canonical origin без доверия Host/Forwarded. Nginx не перехватывает upstream404/503 под index.html. Для статических cache headers порядок точных location и regex проверяется на настоящем Nginx.

Тестовый VPS/изолированный gateway сохраняет noindex и Disallow:/. Production индексирование не включается этим планом. Sitemap будет брать только published people/articles через тот же canonical/visibility contract, с XML escaping и ограниченным чтением; без хранения новой проекции/lastmod из воздуха. При serving=true/indexing=false —200 с пустым валидным XML sitemap и robots Disallow:/; при serving=false новые endpoints не включаются и сохраняется нынешняя маршрутизация; global staging noindex не снимать ради теста published fixture.

**Ограничение:** два типа не равны завершённому R13 для всего сайта. Не заявлять правильные HTML404, SEO/индексацию и sitemap остальных публичных типов без их отдельной проверки. До отдельного выпускного решения все новые serving/indexing flags остаются off.

### Изображения и контент

Для изолированной приёмки используются только собственные fixture images и существующий synthetic corpus. Это позволяет проверить wiring до редакционных решений и не требует переписывать реальные документы.

Отдельный gate перед выпуском: выбрать/утвердить публичный общий share image, проверить HTTP200/Content-Type/декодирование через целевой gateway, восстановить9 отсутствующих файлов либо согласовать безопасный fallback. Проверенный URL должен одинаково использоваться initial head и JSON metadata. Не делать HEAD/FS-проверку сотен изображений на каждом запросе; конкретный lookup/manifest/fallback протокол определить в implementation-плане. Отсутствие share image или unresolved9 media не маскировать fixture PNG при включении production indexing. Neutral descriptions/кандидаты на дубли остаются read-only редакционной очередью.

## Границы следующего implementation-плана после согласования схемы

| Пакет | Результат и проверка | Рекомендуемая модель |
|---|---|---|
| 1. Общая опциональная регистрация/контракт настроек | Исключить fixture endpoints; flags off сохраняют API/UI; один lifecycle; covered HTTP statuses и Host safety | Sol/high |
| 2. Один frontend build artifact и readiness | Одинаковый release/template/asset manifest, ошибки/mismatch дают503; config/handoff согласованы | Sol/high |
| 3. Nginx gateway rehearsal | Собственные containers/сеть/UUID DB, без primary ports/volumes; routing/media/cache/error matrix на реальном Nginx; старый smoke | Sol/high |
| 4. Robots/sitemap partial scope | Text/XML, published-only, safe URLs, noindex/disallow staging; изменения статуса/slug отражаются без новой сохранённой проекции | Sol/high |
| 5. Полная локальная приёмка и read-only review | Unit/API/native Mongo, strict CI=true build, JS-off/on/Back/error,0 HTML views/1 API view, latency/RSS/commands; cleanup и primary proof | Sol/high; reviewer Astra/high |
| Выпускные content/media gates | Общий image и9 файлов по отдельному решению, HTTP проверка; без массового изменения данных | Sol/high; пользователь утверждает контент |

Точный список новых файлов, интерфейсы, порядок RED/GREEN и воспроизводимые команды будут в implementation-плане **после выбора схемы**. Не обещать числовой production SLO по локальному R13d; измерять core ready и полный набор виджетов отдельно, указывать фоновые запросы и стоимость двух чтений. Имеющиеся R13d measured bounds —[отчёт](r13d-html-react-pilot-acceptance-2026-10-22.md).

## Согласование схемы

Пользователь подтвердил **схему A** для подготовки детального плана: существующий FastAPI backend + Nginx, один immutable frontend build, отдельные off-by-default serving/indexing flags, сначала isolated gateway rehearsal; media/выпуск и расширение типов —отдельными gates. Это не разрешение merge/main sync/включения production flags/выкладки на VPS.

Основание запроса —пользовательское правило AGENTS:«До реализации спроси, если варианты меняют пользовательское поведение, данные, совместимость, архитектуру, объём работы или внешние последствия». Здесь меняется точка выдачи HTML и связь двух release images. Согласно [brainstorming/SKILL.md](C:/Users/rdp6126443.gmail.com/.codex/plugins/cache/openai-curated-remote/superpowers/6.4.2/skills/brainstorming/SKILL.md), architectural path также требует written-spec approval до implementation-плана. Историческое основание согласования схемы; после отдельного утверждения implementation-плана R13e реализован в worktree. Новые commit/push не поручались.

## Публикация R13d / CI

- R13d: [3b6146f](https://github.com/AMnEPka/humorpedia/commit/3b6146ffe420afbaa697ae2f2eba607c8b258f6c),32 файла, включая документацию R13c/R13d.
- CI fix: [98f37bb](https://github.com/AMnEPka/humorpedia/commit/98f37bb7c7943ae1da976c6f803fb50425e2b6e0), только dependencies двух detail effects и отчёт. Remote ref после push совпал с этим SHA.
- Первый [run39783235689](https://github.com/AMnEPka/humorpedia/actions/runs/39783235689): frontend strict build отклонил6 hooks warnings; Jest357/tooling5 и3 других jobs PASS. Причина и локальный RED/GREEN зафиксированы в отчёте R13d.
- Исправленный [run39783968388](https://github.com/AMnEPka/humorpedia/actions/runs/39783968388) на точном98f37bb: **completed/success**, все5jobs success (backend, mongodb-integration, frontend, windows-tools, browser-smoke). Оба browser сценария в job выполнены, не skipped.

Независимое read-only ревью схемы: основной пробел default-off/enabled proxy устранён явным разделом Nginx/dispatcher; дополнен инвариант несовместимой комбинации flags. Существенных незакрытых замечаний к схеме не осталось. Это статическое ревью, не проверка ещё не написанного R13e runtime.
