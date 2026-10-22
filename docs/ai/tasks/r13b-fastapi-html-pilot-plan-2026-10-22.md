# R13b: изолированный пилот FastAPI HTML — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task; независимое итоговое ревью — после совместной проверки. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** На собственной временной БД проверить серверный HTML человека и статьи: метаданные, основной текст/ссылки, статусы и стоимость обработки — до подключения нового способа выдачи к приложению.

**Architecture:** Отдельная FastAPI app factory, не включённая в `server.py`/Compose/nginx. Read-only адаптер читает существующие people/articles через CRUD helper без инкремента просмотров; нормализованная модель метаданных и простая HTML-проекция вычисляются при GET. Новая коллекция, сохранённая проекция, очередь и Node-сервис не нужны пилоту.

**Tech Stack:** Существующие Python3.11, FastAPI0.110, PyMongo Async4.18.1, pytest/httpx; stdlib html/html.parser/urllib.parse. Новых production зависимостей нет.

**Spec:** [Утверждённый контракт R13a](r13a-search-metadata-2026-10-22.md).

Дата 22.10.2026 (МСК). Worktree `C:/Users/rdp6126443.gmail.com/.codex/worktrees/r5-zip-operations/humorpedia`, ветка `codex/local-page-builder`, базовый HEAD `893b57e`. Пользователь утвердил контракт, затем план и реализацию пилота. Статус: пилот реализован и локально принят 22.10.2026; публикация отдельным коммитом с документацией поручена пользователем 22.10.2026, запись обновлена перед commit/push.
Метод исполнения: основной агент реализует последовательные задачи, один помощник проверяет итог; модели по задачам указаны ниже. Коммит/push R13 — по отдельному поручению, как в текущем поэтапном процессе.

## Global Constraints

- Primary checkout и действующий стенд остаются `main ca46155`. Импорт 24СМИ, существующая Mongo, VPS, DNS и текущие nginx/Compose не изменяются.
- Origin canonical: `https://humorpedia.ru`. Обращений к этому адресу для проверки/получения контента нет: это значение выходных URL.
- Пилот доступен только при HTML_PILOT_ENABLED=1, RUN_ID из 32 hex и DB_NAME=humorpedia_html_pilot_<RUN_ID>; MONGO_URL обязателен. Примерочные env-имена этого плана — HTML_PILOT_RUN_ID и HTML_PILOT_INDEXING_ENABLED.
- Индексируемость включается явной настройкой только в собственном тестовом контуре; default noindex. Draft/missing-status по-прежнему читаются с noindex; archived/unknown — 404 даже при staff token/cookie.
- Не импортировать production app/lifespan для запуска пилота: там создаются индексы/админ и стартуют фоновые writers. Пилот использует get_db/close_db в одном event loop; seed/drop — только во владеющем тестовом harness.
- Полный контракт R13 шире пилота: команды/шоу/новости/сезоны, каталоги/sitemap/robots, React head sync/переходы и production wiring остаются последующими пакетами. Пилот не объявляется завершённой индексацией сайта.

## Review Focus

1. Draft/missing-status нельзя превратить в 404 строгим published-фильтром; cookie не должен раскрывать archived. Тесты задачи2/4.
2. HTML parser и escaping должны исключать script/style/iframe и javascript/data links, не исполняя импортированный HTML; кириллица/кавычки остаются текстом. Задачи1/3.
3. Чтение/обогащение не должны запускать views_counter или записывать данные; cold/restart не должны использовать client из другого loop. Задачи2/4/5.
4. Скрытые модули, порядок одинаковых order, sidebar, foreign-agent notice и legacy article.content должны сохранять семантику выбранной публичной страницы. Задачи2/3.
5. Недоверенный Host/query, URL-путь с UUID/old_url и archived redirect target не должны менять canonical origin или раскрывать документ. Задачи1/4.

## Файлы и интерфейсы

| Файл | Ответственность |
|---|---|
| backend/services/html_text.py (new) | общий безопасный parser текста/ссылок для metadata и body, без возврата source HTML |
| backend/services/page_metadata.py (new) | frozen PageMetadata, чистые metadata/URL/robots builders |
| backend/services/public_html.py (new) | чтение без просмотров, TextBlock/HtmlPage read model, выбранный текст/ссылки, безопасный HTML renderer |
| backend/routes/html_pilot.py (new) | router только GET /people/{slug}, /articles/{slug}, проверенные legacy paths и status endpoint |
| backend/html_pilot.py (new) | create_app() и минимальный lifecycle с обязательными guard; не импортируется production server |
| backend/tests/test_page_metadata.py, test_public_html.py, test_html_pilot.py (new) | pure/unit/ASGI проверки |
| backend/tests/test_html_pilot_integration.py, fixtures/html_pilot.json (new) | opt-in настоящая Mongo и общие синтетические fixtures |
| scripts/seo/pilot_server.py, check_pilot.cjs (new) | guard/seed/cleanup одноразовой БД и JS-off HTTP/browser приёмка, без npm зависимостей приложения |
| scripts/seo/export_reference.py, compare_react.cjs (new) | read-only экспорт общих fixtures и сопоставление с неизменённой React-сборкой в network=none |
| .github/workflows/tests.yml | opt-in тест пилота добавлен в существующий Mongo integration job |
| docs/ai/tasks/r13b-fastapi-html-pilot-plan-2026-10-22.md | фактический результат/замеры и остаток контракта; CLAUDE/план обновляет root |

Перечисленные новые пути реализованы в этом пакете. Существующие source_html.py, public renderers, HTTP CRUD/lookup routes, models и requirements не редактируются в пилоте.

### Task 1: чистый metadata builder — Sol/high

**Interfaces:** `PageMetadata(title, description, canonical_url, og_type, image_url, image_alt, robots, lang="ru", locale="ru_RU")` — frozen dataclass. `build_page_metadata(kind: Literal["people","articles"], document: dict, *, site_origin: str, indexing_enabled: bool, default_image_url: str) -> PageMetadata`. Для people canonical path=/people/{document.slug}, articles=/articles/{document.slug}; og_type website/article. Пустой slug или недопустимый origin — ValueError; HTTP-преобразование выполняет Task4. Недопустимый image пропускается в пользу следующего fallback.

- [x] Добавить RED `test_title_origin_and_robots_contract`: для title=Альфа, seo.meta_title=Мета, slug=alpha ожидать `title == "Мета | humorpedia.ru"`, `canonical_url == "https://humorpedia.ru/people/alpha"`; SEO title имеет приоритет и suffix один раз; Unicode/HTML/кавычки остаются значениями; explicit description → excerpt → нейтральный fallback. Проверить relative image → origin, image schema только http(s), og:url равен canonical; Host/fragment/tracking не являются входами builder.
- [x] Запустить `pytest -q tests/test_page_metadata.py`: увидеть ожидаемое отсутствие builder/неверные значения.
- [x] Реализовать builder. Index,follow только при indexing_enabled=True и status=published; иначе noindex,follow. Ручные SEO значения не переписываются/не обрезаются. Image fallback в harness — собственная публичная fixture-картинка, не новый продуктовый медиаресурс.
- [x] Повторить указанный набор: PASS; fixture metadata содержит ровно значения контракта.

### Task 2: read model без записи — Sol/high

**Consumes:** PageMetadata/build_page_metadata из Task1. **Produces:** `async load_html_page(kind: Literal["people","articles"], slug: str, *, site_origin: str, indexing_enabled: bool, default_image_url: str) -> HtmlPage`. `HtmlPage(metadata, heading, blocks: tuple[TextBlock,...], links: tuple[tuple[str,str],...], notices: tuple[str,...], canonical_path: str)`; TextBlock — heading/body_text. Это вычисляемые объекты, не Mongo-модели.

- [x] RED `test_reader_is_anonymous_and_never_enqueues_views` и `test_module_visibility_order_and_article_fallback` в test_public_html.py: mocked CRUD вызван с increment_views=False/editor=False; документ и его модули не мутируют; draft/missing-status читаются, archived raises404. Hidden=false исключён, missing visible включён, equal order стабилен. Article.content fallback используется только при отсутствии content-модулей, как в текущем React.
- [x] Запустить `pytest -q tests/test_public_html.py` и зафиксировать ожидаемый FAIL.
- [x] Использовать `services.crud.get_by_id_or_slug(kind, slug, message, increment_views=False, editor=False)`. Не вызывать get_person/get_article routes. На копии документа сохранить существующие LinkResolver.resolve_document/decorate_document enrichment; они читают данные/используют process-local cache, не увеличивают просмотры. Public foreign-agent notice и маркеры — существующего содержания; не вычислять новые правовые признаки.
- [x] Выбор модулей повторяет R9: visible is not False, sort(order or0) стабилен, placement/sidebar по backend.models.module_contract. В теле пилота allowlist text_block/quote/timeline. Остальные типы отмечаются как непокрытые; rating/poll/widgets/произвольные structured objects не превращать в строку.
- [x] PASS указанных тестов; добавить fixture с notice/linked text и подтвердить сохранность подписи/ссылки. Backend source-import sanitizer и его правила остаются без изменения.

### Task 3: безопасная HTML-проекция — Sol/high

**Consumes:** HtmlPage. **Produces:** `render_html_page(page: HtmlPage) -> str` в public_html.py; нормализованные текст/ссылки извлекаются stdlib HTMLParser с исключением active-content subtree, затем выводятся через html.escape. Не передавать исходный произвольный HTML в готовый документ.

- [x] RED `test_semantic_html_head_text_and_escaping`: ровно один title/canonical и каждый OG-тег, ru/ru_RU, H1, основной текст и обычные ссылки. Для script/style/iframe, nested tags, entities, javascript/data/protocol-relative URL — отсутствие исполнения/небезопасного href. Кириллица, кавычки, quote author, timeline dates и notice сохранены.
- [x] `pytest -q tests/test_public_html.py` — ожидаемый FAIL нового render-пути.
- [x] Реализовать минимальный semantic HTML с head/main/article/paragraph/links/note. Без подключения React/hydration/динамических модулей и без нового CSS/UI-дизайна. Не копировать весь DOM React; сопоставлять нормализованный пользовательский текст выбранных блоков на общих fixtures.
- [x] PASS renderer tests. В отчёте явно указать непокрытые media/interactive modules и качество body extraction; расхождение обязательного notice/содержания блокирует пилот.

### Task 4: отдельно запускаемая app и HTTP-семантика — Sol/high

**Consumes:** load_html_page/render_html_page. **Produces:** `create_app() -> FastAPI` в backend/html_pilot.py, router из routes/html_pilot.py. `GET /__html_pilot__/status` возвращает только run_id/db_name/mode для подтверждения владения; никаких credentials.

- [x] RED `test_factory_rejects_unowned_database` в test_html_pilot.py: guard не разрешает запуск без flag/валидного UUID/точного DB_NAME/MONGO_URL; нет POST/PUT/DELETE и production routing. Закрытие клиента проверяется в том же loop.
- [x] RED `test_http_visibility_robots_and_safe_redirects`: published200 + index только при явном flag; draft/missing200 + noindex; unknown/archived404, независимо от staff token; DB exception/ошибка построения документа → 503 с noindex, Cache-Control no-store. Для UUID alias/подтверждённого old_url — 301 на canonical; archived/missing target не раскрывается.
- [x] Создать minimal lifespan get_db/close_db; не вызывать server.py/init_admin/create_indexes/views_counter. HTTP unknown404 не заменяется generic200. Все пилотные ответы no-store; нет нового shared HTML cache.
- [x] Old URL искать только в people/articles fixture-коллекциях, затем повторно загрузить цель как anonymous. Не переиспользовать текущий lookup response без visibility check. Любой внешний/некорректный target отвергается. Host и Forwarded не используются для canonical/Location origin.
- [x] `pytest -q tests/test_page_metadata.py tests/test_public_html.py tests/test_html_pilot.py` — PASS; assert production app routes не содержат router пилота.

### Task 5: настоящая Mongo и приёмка без JS — Sol/high

**Consumes:** app factory и общие fixtures. **Produces:** opt-in `HTML_PILOT_INTEGRATION=1` набор, собственный guarded server и check_pilot.cjs. Интеграционный marker/cleanup и запуск — в test/harness, app factory сама не создаёт/удаляет данные.

- [x] RED `test_real_mongo_gets_preserve_documents_and_restart`: новая пустая humorpedia_html_pilot_<uuid>, owner marker и fixtures published/draft/missing/archived + legacy aliases; до/после нескольких GET BSON/коллекции/просмотры не изменились. Разрешённые seed/drop принадлежат harness. При cleanup проверять marker и точный UUID DB; все операции клиента в одном event loop.
- [x] Запустить на новой Mongo в отдельной Docker-сети, без публикации Mongo и использования primary volumes. Команда внутри подготовленного backend image: `HTML_PILOT_INTEGRATION=1 pytest -q tests/test_html_pilot_integration.py`. FAIL должен относиться к новому контракту.
- [x] Реализовать guarded harness с fixture image и owned server, порт только собственной сети/loopback; reuse Playwright1.62.1 вне app dependencies. Не включать production server lifecycle ради выдачи HTML.
- [x] Checker использует HTML_PILOT_BASE_URL только loopback и проверяет HTML_PILOT_RUN_ID через status; NODE_PATH указывает на отдельный Playwright toolchain. HTTP checker и browser с JS disabled проверяют согласованные metadata/H1/text/links/notice, image200/image content-type (canonical image path проверяется на собственном test origin, не fetch production URL), 301/404/503/noindex. Входные заголовки и cookie не меняют scope. Ни одного запроса к humorpedia.ru/primary/VPS.
- [x] PASS integration/browser. Изменение текста fixture, published→draft/archived и slug немедленно отражается в следующем GET без прогрева/ручного сброса; restart не возвращает старый документ. Удалить только собственные server/Mongo/network после корректного shutdown.

### Task 6: замеры и решение по архитектуре — Sol/high

**Consumes:** рабочий пилот двух типов. **Produces:** таблица p50/p95/error rate/память/число Mongo reads, ограничения и рекомендация для следующего пакета — продолжать FastAPI, сравнить React SSR или пересмотреть подход.

- [x] На синтетических text fixtures 10 KiB и250 KiB выполнить cold/startup и пять warm-серий по100 GET на каждый тип (concurrency1); до каждой warm-серии 30 прогревочных GET. Зафиксировать версии, payload sizes, cache state и RAM; отдельные A/A-серии одного кода оценивают разброс.
- [x] Записать все ошибки и фактическую стоимость; метрики nginx SPA shell/API не считать эквивалентной функциональной базой полной HTML-страницы. Численный production SLO не выдумывать. Рекомендация должна учитывать стоимость второго renderer и непокрытые типы, не только скорость.
- [x] Совместная проверка: новые unit/API/integration/browser; действующие backend tests на отдельной БД по утверждённой схеме CI. Frontend331 и существующий full browser smoke повторять при новых изменениях/сомнениях, затрагивающих их путь; основная frontend-сборка в пилоте не изменяется.
- [x] Проверить diff/source-import paths, primary branch/HEAD/IDs/StartedAt/restarts и HTTP3000/8001 без запуска dev-sync. Обновить эту запись фактическими результатами и ссылкой из общего плана. Все проверки отличать от текущего R13a baseline.
- [x] Независимое итоговое ревью; подготовить конкретный результат к commit/review по поручению пользователя. Следующий пакет согласовывается по результату измерений; production wiring/выкладка из этого плана не следуют автоматически.

## Остаток полного R13 и критерий завершения пилота

Пилот принят, когда для двух fixture-типов пройдены metadata/text/status/visibility/no-write/restart проверки, есть измерения и известные расхождения с React. Окончательный R13 остаётся открытым: остальные типы/модули, frontend head sync и переходы, общая share-картинка, production способ выдачи, sitemap/robots и аудит реального legacy status/контента.

Открытого продуктового вопроса внутри пилота нет: origin, цель, anonymous visibility и noindex policy согласованы. План утверждён пользователем до реализации. Фактические результаты пилота приведены ниже; полный R13 и production способ выдачи остаются открытыми.

## Результат приёмки — 22.10.2026

Пилот работает отдельным приложением, без регистрации router в production server. Новых production зависимостей, изменений схемы/данных и сохранённых HTML-проекций нет. Вся реализация находится в worktree `codex/local-page-builder` поверх `893b57e`; Публикация поручена отдельным коммитом; точный SHA и итог GitHub CI фиксируются в следующем состоянии R13c после push.

### Реализованное поведение и уточнения по ревью

- Для people/articles: единые ru/ru_RU title/description/canonical/OG/robots, H1, выбранный текст, ссылки и пометка. Index только explicit published + флаг, по умолчанию noindex.
- Draft, отсутствующий/null/пустой status сохраняют анонимную доступность с noindex. Archived и остальные непустые статусы (в том числе private) дают404 до enrichment; staff cookie/token это не меняют. Это политика только пилотного HTML; JSON API сохранён.
- UUID, old_urls и существующие pattern-адреса people/articles `.html` дают301 только после повторного anonymous чтения разрешённой цели. Origin/Location фиксированы, Host/Forwarded/query их не меняют.
- Чтение выполняется с increment_views=False/editor=False на копии; resolver/notice enrich не сохраняют документ. У всех ответов no-store, у ошибок404/503 — noindex. Никакого общего HTML cache.
- Parser `html_text.py` выделен для общего безопасного извлечения текста/ссылок; source HTML никогда не вставляется в ответ. Неверный image URL, включая malformed IPv6/port, пропускается к fallback; fixture image обслуживается только собственным harness.
- React pages передают в ForeignAgentNotice только visible, без массива notices. Пилот сохраняет фактическую стандартную подпись `* — признан в РФ иностранным агентом.`. Специальные подписи не объявляются поддержанными за счёт существования массива в API; их синхронизация — отдельная будущая задача. Legacy-подпись в модуле не дублируется. Legacy article.content с уже встроенной подписью имеет прежние ограничения decorator, который ищет готовую подпись только в modules; это не исправлялось.
- У article сохранён выбор первого visible image и legacy content fallback, включая hidden-only modules. Quote остаётся буквальным текстом; timeline проверен на events. Полное оформление и варианты legacy timeline/content_html, экранированные SQL-артефакты, media/interactive modules и все реальные импортированные документы этим пилотом не покрыты.
- Статическое независимое ревью выявило и помогло исправить unknown-status, pattern redirect, подпись и буквальный перенос в CI YAML. После повторного ревью блокирующих замечаний к реализации/инструментам нет.

### Подтверждённые проверки

| Уровень | Результат |
|---|---|
| RED → GREEN новых metadata/read model/HTML/HTTP tests | Первоначальное отсутствие реализации и конкретные замечания воспроизведены; журналы в `.cache/r13b/*red*.log` |
| Общий backend с integration flags на собственной Mongo | **1157 passed, 2 skipped**, 31.13s; readiness пропущен в этой серии и выполнен отдельно |
| Отдельный READINESS_INTEGRATION | **2 passed**, 5.21s |
| Production app isolation | Тест подтверждает отсутствие router/status endpoint пилота в server.app; production lifespan не запускается |
| Настоящая Mongo, BSON snapshot | Коллекции/документы/просмотры до и после GET равны; seed отклоняет непустую БД; mutation текста/status/slug видна сразу и после close/reopen |
| HTTP + Chromium через Playwright1.62.1 с JS disabled | Metadata, H1, текст, notice, link/image200/content-type, 301/404/noindex, staff/Host — PASS; неожиданных внешних запросов и browser pageerrors нет |
| Сравнение с текущей React-сборкой | 5 общих fixtures, 8 выбранных блоков, 4 ссылки и подписи совпали по содержанию; пробелы нормализованы, весь DOM/дизайн/интерактивность не сравнивались |
| Реальная остановка собственной Mongo | GET503 + noindex/no-store за5338.98ms; текст страницы не раскрыт; после запуска Mongo GET200 за2977.13ms без рестарта пилота |
| Локальный набор обновлённого CI Mongo job | **39 passed**, 12.85s; GitHub для незакоммиченного пакета не запускался |
| Повторный запуск процесса | 5 cold-start/shutdown циклов: каждый раз новая seed той же освобождённой UUID БД; старое состояние не возвращается |

Проверки выполнены в отдельной Docker-сети `humorpedia-r13b-pilot`, Mongo `humorpedia-r13b-mongo` без опубликованного порта, БД `humorpedia_html_pilot_ccb3a6c39f8349109d0cb10ae3d1492d`. Временная owner-коллекция — только в harness/fixture DB, не новая коллекция приложения. Сервер имеет собственный native client/lifecycle; закрытие/seed/drop происходят в том же event loop. Никаких обращений к production canonical origin, VPS или основной базе.

### Измерения

Среда: Docker Desktop Linux, Python3.11.17, PyMongo4.18.1, Mongo8.0.32, FastAPI0.110, Playwright1.62.1. Один Uvicorn worker, concurrency1; Node fetch измеряет полный HTTP-ответ внутри собственной сети/loopback. 5 одинаковых warm-серий по100 GET на каждую комбинацию, перед каждой30 warmup GET: **2000 measured + 600 warmup**, ошибок0. Отдельных 20 первых запросов после пяти process restart — ошибок0. Во время warm-серий тесты backend не запускались; другие проекты на общей машине работали, поэтому результаты локальные и содержат шум хоста.

| Тип | Текст fixture | HTML bytes | p50 pooled, ms | p95 pooled, ms | p95 пяти одинаковых серий, ms |
|---|---:|---:|---:|---:|---:|
| people | ~10KiB | 11143 | 2.902 | 4.186 | 3.019–4.650 |
| people | ~250KiB | 256914 | 5.172 | 8.173 | 5.582–9.926 |
| articles | ~10KiB | 11159 | 2.635 | 3.215 | 2.896–3.578 |
| articles | ~250KiB | 256930 | 5.014 | 6.394 | 5.718–6.859 |

Pooled nearest-rank рассчитан по500 samples на строку; p95 серии — 95-й из100. Диапазоны одинакового кода показывают разброс, а не изменение скорости между версиями. Сравнение с SPA shell/API, React SSR и прежними R11-цифрами не проводилось: ответы функционально неэквивалентны.

На100 measured GET каждой серии: **200 find**, остальные counted commands delta0, записей0. Это 2 reads/GET: сам документ и набор people для существующего notice enrichment; cache cold/warm не скрывает записи или чтение всей foreign-agent выборки. При большом production-наборе эту стоимость требуется повторно оценить; пилот имеет только синтетические данные.

RSS процесса в warm-сериях **60684–61432KiB (59.26–59.99MiB)**, после cold первых запросов максимум61564KiB (60.12MiB). Это VmRSS процесса Python, не лимит контейнера/всего стенда. Harness-only startup от начала lifespan/seed до готовности: **50.67–60.54ms**, без импорта Python/создания контейнера. Первый GET people10KiB после нового процесса4.13–5.23ms; далее первый GET каждой другой страницы в том же процессе: people250KiB6.37–14.71ms, articles10KiB4.15–6.12ms, articles250KiB7.10–8.90ms. Порядок фиксирован; лишь первый people10KiB является полностью первым запросом процесса, остальные — first-use страницы.

Measurement endpoint/listener существуют только при HTML_PILOT_MEASURE=1 в fixture harness, не в app factory/production. Используется PyMongo command listener без query payload и без включения Mongo profiler. Raw samples/commands/RSS: `.cache/r13b/final-browser/metrics.json`; cold — `.cache/r13b/final-cold-*/cold.json`; browser — `.cache/r13b/final-browser/browser.json`; React — `.cache/r13b/reference/react.json`. Эти журналы игнорируются Git; воспроизводимые fixture/checker исходники входят в пакет.

### Воспроизведение

Запускать из этого worktree в отдельном Python-контейнере, подключённом к собственной временной Mongo; не использовать primary Compose/порты/volumes. Требуются текущие backend dependencies и выделенный Playwright1.62.1 toolchain, frontend production build для сравнения React. MONGO_URL должен явно вести на собственную Mongo.

1. Задать HTML_PILOT_ENABLED=1, свежий HTML_PILOT_RUN_ID (32 hex), DB_NAME=humorpedia_html_pilot_<тот же id>, MONGO_URL, HTML_PILOT_INDEXING_ENABLED=1 для проверки index, HTML_PILOT_MEASURE=1 для метрик. При bind внутри изолированного Docker — HTML_PILOT_BIND=0.0.0.0, без публикации порта.
2. `python scripts/seo/pilot_server.py`. Seed требует пустую UUID БД, создаёт owner marker; штатный shutdown удаляет только эту БД после проверки имени/marker. При ненормальном завершении не применять общий drop/reset: сначала проверить владение и отсутствие работающего процесса.
3. В контейнере Playwright, разделяющем network namespace пилота: NODE_PATH=<выделенный node_modules>, тот же HTML_PILOT_RUN_ID, HTML_PILOT_BASE_URL=http://127.0.0.1:18013, HTML_PILOT_ARTIFACT_DIR=<папка результатов>; `node scripts/seo/check_pilot.cjs`. HTML_PILOT_COLD=1 делает только first-use/startup замер; HTML_PILOT_MEASURE=1 — пять warm-серий. Для cold повторить штатный stop/start процесса.
4. Пока owned server запущен, с его UUID env выполнить `python scripts/seo/export_reference.py`, затем `node scripts/seo/compare_react.cjs` в отдельном Playwright-контейнере с network=none. Тест сам обслуживает существующий frontend/build на loopback18014 и подменяет JSON API общими fixture-документами; frontend src не меняется.
5. Backend: `HTML_PILOT_INTEGRATION=1 pytest -q tests/test_html_pilot_integration.py` из backend с own Mongo; полный набор и флаги — как в existing tests.yml. Пилотный integration добавлен в существующий GitHub Mongo job. Удалить свой server/Mongo/network после приёмки.

### Архитектурный вывод и границы

**Для проверенного текстового поднабора FastAPI подходит:** стабильные исходные metadata/статусы без JS, немедленная актуальность без дополнительной сохранённой проекции, небольшой процесс и два чтения на GET. Переводить весь сайт на него по этим цифрам преждевременно: главный риск — расхождение второго renderer с React на большом legacy-наборе, а не скорость короткой fixture.

Рекомендованный следующий пакет R13c (Sol/high, архитектурное ревью Astra/high): read-only инвентаризация реальных status/slug/SEO/images/вариантов modules и notices, затем конкретная схема единого документа HTML + запуска существующего React/интерактивности и проверяемая матрица parity. По этой матрице выбрать расширение FastAPI или отдельное сравнение React SSR. React SSR в R13b не реализован и по скорости/памяти не оценивался. Production wiring, включение индексации, новые зависимости и выкладка требуют отдельного согласованного пакета. Сайт на main, импорт24СМИ и VPS сохранены.

### Финальная сверка окружения

- Primary: чистая main, HEAD ca46155a9640d4723c07b9fd1762a6e639563414. Исходные backend/frontend/Mongo container IDs и StartedAt совпали с началом задачи; RestartCount0, compose running, Mongo healthy. http://localhost:3000 и http://localhost:8001/api/health вернули200. dev-sync/restart primary не выполнялись.
- Whitelist diff:20 файлов этого пакета и предшествующей документации R13a/R12c. Source-import/24СМИ, production server/Compose/nginx, зависимости и VPS не изменены. Python/Node syntax, MD links, whitespace и staged-empty проверены.
- Пилот остановлен с exit0 и completed lifespan; перед удалением Mongo через список БД подтверждено отсутствие owned UUID DB. Собственные server/Mongo (с их anonymous volumes) и Docker network удалены. Основные контейнеры сохранены.
- Перед публикацией: ветка codex/local-page-builder на893b57e, изменения готовы к отдельному commit/push по поручению пользователя. Локальный updated CI Mongo job39 PASS; GitHub run проверяется после push на точном новом SHA.
