# R13e: подключение HTML через FastAPI и Nginx — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Сохранённый метод: root последовательно реализует и интегрирует; один read-only помощник проверяет общий результат. Steps use checkbox (`- [ ]`) syntax. Не запускать отдельный implementer на каждый пункт.

**Goal:** Подготовить опциональную выдачу people/articles HTML в существующем backend и доказать на отдельном gateway работу serving, immutable build, metadata, legacy и crawl endpoints; default-off сохраняет нынешний сайт.
**Architecture:** Согласованная схема A: существующий FastAPI lifecycle, Nginx для assets/proxy, один frontend build для обеих images. Серверный fallback + createRoot + штатный API GET; без новой службы, bootstrap, prerender projection или смены Mongo.
**Tech Stack:** Python3.11/FastAPI/PyMongo4.18.1, React19/Vite8/Node24.22.1, Jest27/Playwright1.62.1, Mongo8.0.32. Контрольный local cloud image содержит Nginx1.29.3; не обновлять зависимости ради этапа.
**Spec:** [Схема R13e](r13e-html-integration-design-2026-10-22.md), **схема и implementation-план утверждены пользователем**.

Дата:22.10.2026. Worktree прежний, `codex/local-page-builder`; HEAD до незакоммиченной реализации `98f37bb7c7943ae1da976c6f803fb50425e2b6e0`. План утверждён пользователем 22.10.2026; реализация и локальная приёмка R13e завершены в прежнем worktree. R13d/CI-fix опубликованы, [GitHub39783968388](https://github.com/AMnEPka/humorpedia/actions/runs/39783968388) completed/success, все5jobs success.

## Global Constraints

- Primary остаётся чистым main ca46155; не переключать/пересобирать/перезапускать основной стек. Импорт24СМИ и scheduler не редактировать; VPS/production flags/DNS не менять. Никакого merge/deploy.
- Не запускать `dev-sync`/`dev-finish` из worktree или `scripts/vps-test/export-local.mjs`: последний останавливает primary writers. Только собственные UUID DB/media/network/containers; без primary ports/volumes и нового чтения/переноса рабочей БД.
- Два covered типа people/articles; API/media/assets/admin/preview не попадают в HTML legacy catch-all. Остальные React routes сохраняют SPA. Не объявлять завершённым весь R13/SEO остальных типов.
- Canonical ровно `https://humorpedia.ru`; anonymous HTML независимо от auth/cookies,0HTML views и1 обычный API GET/view после JS. Default/raw API прежние; никаких дублирующих metadata GET.
- `PUBLIC_HTML_ENABLED=false`, `SEARCH_INDEXING_ENABLED=false` по умолчанию; значения env только `true`/`false`. Комбинация false/true запрещена до запуска. Новый frontend runtime `window.__PUBLIC_HTML_ENABLED__ === true`; строгий `__HTML_PILOT__ === true` остаётся совместимым только для existing harness.
- Production image и9 missing media —отдельный выпускной gate; R13e использует fixture image, не переписывает реальные документы. Метаданные не проверяют файловую систему/HTTP на каждом GET.
- Никаких изменений сохранённых проекций, Mongo версии/режима, зависимостей или новой Node runtime-службы. Node используется только build/tooling.
- Commit/push и schema согласование уже были для R13d. Новые implementation commits R13e —по отдельному поручению или явно подтверждённому процессу; не перемешивать с параллельными изменениями.

## Review Focus

1. false/false должен сохранить прежние fetch/title/preview и Nginx; не спутать runtime mode со сменой индексации —Task1/4/6.
2. Default `error_page 404 /index.html` и legacy miss способны превратить архивную цель/ошибку в200 —Task3/4/6.
3. Несовпадение template/modern+legacy chunks двух images или spoofed release header не должно давать HTML200 —Task2/3/4/6.
4. Internal dispatcher/path encoding/Host/auth не обходят public visibility, API auth или media privacy —Task3/4/6.
5. Native lifecycle/fixtures/sitemap не должны породить вторые writers, просмотры, stale snapshot или воссоздать owner DB после cleanup —Task3/5/6.

## Карта файлов

| Пакет | Создать / изменить |
|---|---|
| Настройки/клиент | new `backend/services/public_html_config.py`, `backend/tests/test_public_html_config.py`; modify `frontend/src/public/utils/htmlPilot.js` и его existing tests |
| Release artifact | new `frontend/scripts/html-release.mjs`, `frontend/tooling/html-release.test.mjs`, `backend/services/public_html_release.py`, `backend/tests/test_public_html_release.py`; modify `frontend/scripts/build.mjs` |
| Native HTML/legacy | new `backend/services/public_html_dispatch.py`, `backend/routes/public_html.py`, `backend/tests/test_public_html_routes.py`; modify `backend/server.py` (только optional registration), `backend/routes/health.py`, `backend/routes/html_pilot.py` и tests только для повторного использования anonymous legacy resolver |
| Gateway/release images | new `Dockerfile.public-html`, `Dockerfile.public-html.dockerignore`, `frontend/tooling/public-html-gateway.mjs` и test, `frontend/docker/public-html-mode.sh`, `frontend/docker/public-html-ready.sh`; existing dev/cloud Dockerfiles/Compose/VPS configs не переключать |
| Crawl | new `backend/services/search_discovery.py`, `backend/tests/test_search_discovery.py`; modify `backend/services/page_metadata.py` (выделить pure canonical helper), `backend/routes/public_html.py` |
| Owned native harness/CI | new `scripts/seo/gateway_server.py`, `scripts/seo/run_gateway.cjs`, `scripts/seo/check_gateway.cjs`, `scripts/seo/test_gateway_tools.cjs`; existing browser/HTML fixtures reuse; modify `.github/workflows/tests.yml` и затронутые task/context docs |

## Task 1: настройки и нейтральный runtime flag — Sol/high

**Produces:** frozen `PublicHtmlSettings(enabled:bool,indexing_enabled:bool,site_origin:str,build_dir:Path|None,default_image_url:str|None)`; `load_public_html_settings(env:Mapping[str,str])->PublicHtmlSettings`. Когда enabled=false, build/image не требуются. При true обязательны `PUBLIC_HTML_BUILD_DIR` и `PUBLIC_HTML_DEFAULT_IMAGE_URL`; origin фиксирован. Недопустимая комбинация flags и неизвестные значения env дают ValueError до регистрации.

- [x] RED `test_defaults_preserve_legacy_mode`, `test_rejects_index_without_html`, `test_enabled_requires_explicit_build_and_image`: defaults false/false, false/true отклоняется, Host не является config. Run `pytest -q tests/test_public_html_config.py` →ожидаемый FAIL отсутствующего модуля.
- [x] Реализовать config, затем расширить `isHtmlPilotEnabled()` строгим OR нейтрального boolean flag, без изменения имени existing export/callers. Строки `"true"`/1/undefined не включают клиентский режим. При обоих false не добавлять API query/head operations.
- [x] GREEN config + `htmlPilot.test.js/htmlPilotApi.test.js/htmlPilotPages.test.jsx` и existing preview tests; проверить case neutral=true/pilot=false и Back generation guard. Штатные getPerson/getArticle/WithTitle уже используют общий helper, не дублировать новый flag в каждом месте.

## Task 2: один проверяемый build artifact — Sol/high

**Produces:** `writeHtmlRelease(buildDir:string)->Promise<ReleaseManifest>` в Node build tooling; JSON `public-html-release.json`: `schema_version:1`, `release_id`=sha256 детерминированной sorted map, `files:{relativePath:sha256}`. В files входят index.html, все module/nomodule/CSS/dynamic chunks и public static файлы сборки; manifest не хеширует сам себя. Не добавлять timestamp, секреты/env или содержимое source DB.

Python: frozen `HtmlRelease(release_id:str,template_html:str,files:Mapping[str,str])` и `load_html_release(build_dir:Path)->HtmlRelease`. Отдельный `ReleaseError` для corrupt/missing/hash/path/symlink/root-template errors; отсутствие release не делает API liveness ложным healthy HTML.

- [x] RED `release_is_deterministic_and_covers_all_chunks`, `rejects_symlink_and_escape`; `test_rejects_missing_chunk_or_changed_template`. Run `node --test frontend/tooling/html-release.test.mjs` + `pytest -q tests/test_public_html_release.py` →FAIL.
- [x] Добавить post-build writer после успешного `await build()`; reader проверяет hashes и shell validation существующим renderer. Проверка один раз на immutable artifact, без сканирования всего build на каждом GET. Не заменять R13d artifacts; свой BUILD_PATH.
- [x] GREEN unit/tooling; `CI=true REACT_APP_USE_API_PROXY=true BUILD_PATH=<own> yarn build`, manifest и matching identity. Повторная сборка одинакового input даёт тот же identity; старые assets не включать случайно через накопленный каталог.

## Task 3: optional native HTML и различимый legacy dispatch — Sol/high

**Consumes:** Task1 settings, Task2 release, existing `load_html_page`/`render_react_shell`/metadata adapter. **Produces:** `register_public_html(app:FastAPI,settings:PublicHtmlSettings)->None`; router создаётся только enabled=true. Metadata config на app.state ставится только в этом режиме как dict ровно из site_origin/indexing_enabled/default_image_url (не весь settings object); fixture control/seed/status endpoints не регистрируются. Native lifespan views/Mongo/scheduler остаётся единственным.

`resolve_legacy_html(path:str,*,settings:PublicHtmlSettings)->LegacyResult` в service; `LegacyResult(kind:Literal["redirect","known_unavailable","no_match","unavailable"],page:HtmlPage|None)`. Перенести только read-only lookup/visibility, R13b default поведение и tests сохранить. Не переиспользовать весь pilot router с catch-all/status в production.

**HTTP contract:** covered GET/HEAD `/people/{slug}`, `/articles/{slug}` →200/301/404/503/no-store; HEAD без тела и views. Internal GET `/_internal/public-html/dispatch` получает raw URI через перезаписанный gateway заголовок `X-Humorpedia-Original-URI`; resolver отделяет query и нормализует percent encoding один раз, без потери literal ampersand в path. Ответы: redirect301, known_unavailable404, unavailable503, **no_match418** с пустым телом/no-store. 418 —только private gateway sentinel, не публичный статус. Internal GET `/_internal/public-html/state` отдаёт readiness и заголовок `X-Humorpedia-Release`, без FS paths/DB/секретов. Весь этот namespace Nginx закрывает снаружи.

- [x] RED `test_disabled_registers_nothing_and_keeps_metadata_absent`; `test_detail_statuses_and_zero_html_views`; `test_legacy_miss_is_not_archived_target`: auth/cookie не раскрывают private/archived, unknown covered404, unknown legacy418, known unavailable404, DB exception503; literal ampersand/tracking/encoded API-admin path не обходят namespace exclusion. Run `pytest -q tests/test_public_html_routes.py` →FAIL.
- [x] Registration после API/media mounts, до общих fallbacks; ровно один вызов в server.py, без нового lifespan. ReleaseError сохраняет API, но covered HTML/state и conditional public_html readiness дают503/noindex. `/api/health` прежний; при disabled `/api/ready` не получает нового обязательного check.
- [x] Для covered HTML проверять `X-Humorpedia-Release` от gateway против backend release_id; missing/mismatch →503/noindex. Это version check, не механизм auth. Клиентский заголовок gateway всегда перезаписывает. Не доверять Host/Forwarded.
- [x] GREEN routes/config/release/health/metadata/R13b tests, native own DB smoke; проверить CAS/writer tests не изменены. HTML не добавляет view, JSON с opt-in добавляет1, default/raw прежние.

## Task 4: Nginx переключение и две images из одного build — Sol/high

**Produces:** `renderGatewayConfigs({releaseId,backendOrigin})->{disabled,enabled_noindex,enabled_index}` в Node tooling; генерирует полные Nginx/runtime config варианты на build stage, без Node/Python в Nginx runtime. `public-html-mode.sh` выбирает готовый вариант только из валидных flags; false/true отклоняется. Один release-параметр подаётся backend и gateway при запуске own harness.

Новый root `Dockerfile.public-html` с backend-release/gateway-release targets получает один заранее собранный Task2 artifact через named build context `public_html_release`. `writeGatewayBundle(buildDir:string,outputDir:string,{backendOrigin:string})->Promise<void>` создаёт отдельный bundle: build/ и gateway-configs/. Конфиги, зависящие от release_id, лежат вне hashed build/ во избежание self-reference. Backend получает тот же immutable build/template/manifest, gateway —полный build и конфиги. CI использует скачанный frontend artifact; локально сначала ровно один Node24.22.1 frozen build. Не пересобирать frontend отдельно для каждой image. Python runtime/requirements/gunicorn как в существующем cloud image, без добавления Mongo tools в release. Для Nginx взять pinned1.29.3-alpine —версию уже проверенного local cloud runtime; обновление не входит в этап. Существующие production/dev Dockerfiles и VPS deployment не переключаются этим планом.

- [x] RED `disabled_config_preserves_original_spa`, `enabled_proxy_and_sentinel_are_scoped` и `context_excludes_secrets_snapshots_and_media`. Node tooling assertions: disabled не добавляет HTML proxy; API/media/ZIP proxy baseline берётся из репозиторной VPS test gateway-схемы (включая52MiB preview), а не из standalone frontend/cloud config без API proxy; исходные конфиги не изменять; enabled covered locations без intercept_errors; только named legacy location intercepts418; нет общего `error_page404 /index.html` в enabled варианте; backendOrigin валидируется как фиксированный HTTP host:port без URI/userinfo/control chars, injection отклоняется. Run `node --test frontend/tooling/public-html-gateway.test.mjs` →FAIL.
- [x] Точные enabled locations: API/media/uploads/images/admin/preview/assets/health исключаются раньше legacy; `^/(people|articles)/[^/]+/?$` в native backend; exact robots/sitemap тоже. Covered proxy `proxy_intercept_errors off`, no-store. Отсутствующий asset —404, не index.html. Prefix/case/percent/trailing slash проверять на Nginx, не только regex unit.
- [x] Остальные пути: existing file либо named legacy proxy. Он передаёт raw request URI перезаписанным X-Humorpedia-Original-URI в internal dispatcher, `proxy_intercept_errors on` и **только** `error_page418 = @spa`. No-match возвращается в прежний SPA; известная unavailable цель404 и DB-error503 не попадают в @spa. Прямой `/_internal/public-html/*` извне404. 418 никогда не выходит наружу.
- [x] Nginx задаёт release header литералом из своего manifest; игнорирует входной одноимённый header. Config.js no-store выдаёт neutral boolean и same-origin API; никаких fixture flags. `public-html-ready.sh` проверяет nginx config и matching backend state/header при enabled, обычную gateway liveness при disabled; внешний /healthz сохранить.
- [x] Dockerfile-specific ignore —allowlist source/runtime/tooling, исключить .git/.cache/.env*/private/backups/uploads/media/node_modules/real snapshots; реальные media в release не запекать. Build targets из worktree не запускают dev-sync. GREEN Node tests + `nginx -t` для3 вариантов + проверка assembled images/manifest identity, без выкладки.

## Task 5: robots и ограниченный live sitemap — Sol/high

**Produces:** pure `canonical_document_url(kind:str,document:dict,*,site_origin:str)->str` в existing page_metadata.py; builder переиспользует его. `render_robots(settings)->str` и async `render_sitemap(db,*,settings)->bytes` в search_discovery.py. Sitemap читает только published people/articles с projection slug/_id/status, batch500; не делает HTTP/HTML GET, enrichment, updates/views или новую persisted projection. Стабильный порядок, XML escaping, dedup canonical; invalid slug исключается, не превращается в другой URL. Lastmod не придумывать.

- [x] RED `test_sitemap_only_published_valid_canonical`, `test_status_slug_changes_are_live_without_views`, `test_closed_crawl_does_not_list_urls`. Assert draft/missing/archived/private/admin/preview/search/другие коллекции отсутствуют; Cyrillic/quotes/query/Host не меняют fixed canonical. Run `pytest -q tests/test_search_discovery.py tests/test_page_metadata.py` →FAIL только новых функций.
- [x] Optional router Task3 регистрирует endpoints только serving=true. Indexing=false: robots Disallow:/, sitemap200 с пустым валидным XML/no-store. Indexing=true в isolated synthetic test: published URLs и Sitemap directive; robots запрещает admin/preview/search, не устанавливает новую noindex-политику остальных SPA страниц. Content-Type text/plain/application/xml с UTF-8; ошибки БД —503/noindex без частичного XML.
- [x] Не возвращать обрезанный валидный-looking sitemap: >50000 URLs либо >50MiB uncompressed →503, отдельный sitemap index —будущий scope. Unit bounds проверять уменьшенным test cap. Сформировать полностью до200 response, без частичного streaming при failure.
- [x] GREEN crawl/metadata/API tests; через native DB изменить status/slug после первого запроса и проверить следующий без кеша/restart. Staging default noindex/Disallow сохраняется; production разрешение индексации остаётся отдельным gate.

## Task 6: own full-native gateway harness, browser и CI — Sol/high

**Produces:** `run_gateway.cjs` —orchestrator с собственным32hex runId/DB `humorpedia_html_gateway_<runId>`, network/containers/media и обязательным finally cleanup; `gateway_server.py` —wrapper настоящего server.app, guard/seed/owner marker, родной lifespan и cleanup после stop writers. До импорта server задаются собственные UPLOAD_DIR/PAGE_PACKAGE_DIR/PAGE_BUILDER_DIR/BACKUP_DIR, пустые backups и synthetic auth env; ни одного primary каталога. Не импортировать fixture endpoints в production app. `check_gateway.cjs` —loopback Playwright checker; browser tools отдельно от app dependencies. `test_gateway_tools.cjs` проверяет ownership/cleanup отказ и отсутствие обращения к primary именам/портам.

- [x] RED ownership и cleanup tests: запрет DB безточного UUID, nonempty безowner, чужие container names/volumes; no automatic stash/reset/cleanup primary. Run `node --test scripts/seo/test_gateway_tools.cjs` →FAIL новых tools.
- [x] Orchestrator требует BROWSER_BUILD_DIR с готовым Task2 manifest, создаёт свой bundle и собирает только новые own targets через --build-context public_html_release=<own-bundle>, создаёт internal Docker network с blocked external egress, own Mongo8.0.32/no host port и media fixtures. Ни source-import jobs, ни credentials/реальный контент в seed не добавлять. Native scheduler код не менять. Перед удалением owner DB штатно дождаться native writers; ownership loss →ошибка и никаких чужих deletes.
- [x] Окончательные команды: `BROWSER_BUILD_DIR=<own Task2 build> node scripts/seo/run_gateway.cjs` запускает modes disabled/closed/indexed-fixture; child checker получает runId/base/артефакты автоматически. Ограничить клиент loopback, namespace статуса guarded wrapper подтверждает UUID до тестов. Exact Docker argv/таймауты/пути встроены в tool и описаны в task report после реализации; default artifact root .cache/r13e.
- [x] Матрица Nginx: flags off baselineAPI/UI/preview; covered raw200/301/404/503, URI/legacy known-private/unknown; robots/XML; API401/403/409/413/ZIP52MiB route limits не затронуты; assets/config/media cache/error; client spoof release header; stale frontend/backend release503. Ни один internal418/endpoint или private target не публикуется.
- [x] BrowserJS-off/on1280/390: server metadata/text/anchor/notice/header image, slow API/chunk/abort/archive, stale A-B-A и повторный Back key, neutral runtime flag, один root,0HTML views/1API view; rating/poll/correction/career/shows штатные. Использовать проверенный R13d checker helpers, не копировать весь150-line сценарий; самостоятельный old smoke сохранить.
- [x] В existing browser-smoke CI добавить gateway command после старых smoke, timeout увеличить до25min из-за image assembly; использовать тот же frontend artifact identity, cleanup и artifacts always. Новые tests команды Node/Python включить в подходящие existing tooling/backend job без отдельного runner/секретов. CI build всегда CI=true, ESLint не ослаблять.
- [x] GREEN own orchestrator + existing scripts/browser-smoke + existing R13d checks; unit инструмента подтверждает cleanup и при падающем browser. Проверки main HTTP/IDs/mounts только read-only.

## Task 7: приёмка, измерения и доставка — Sol/high, reviewer Astra/high

- [x] Полные backend unit/API + отдельные native integration flags/readiness с Mongo tools, frontend Jest/tooling и strict CI=true build. Зафиксировать уровни: static/unit/native/browser/NGINX/actual mode, а не объединённое «всё проверено».
- [x] Для4 synthetic combinations people/articles10/250KiB:3 warmup,5 warm серий×10 full nav, concurrency1; отдельно core React ready и завершение обязательных widget запросов, HTML/API timings, commands и RSS. Cold:3 fresh own backend/gateway процесса на каждую комбинацию с новой UUID и fresh browser context. Не сравнивать разные условия и не объявлять production SLO по этим данным.
- [x] Отдельные gate checks default-image URL/content-type/decoding на fixture origin; image availability9/production asset не считать решёнными. Не запускать восстановление реальных media/редактуру как side effect.
- [x] Fresh whole-diff read-only review по approved spec, исправить подтверждённые Important/Critical с RED/GREEN. Root владеет source/context, помощник не переключает ветки и Docker/commits.
- [x] После штатного stop отсутствуют UUID DB/own volumes/network/writers; primary main ca46155 чистый, исходные3 IDs/StartedAt/restarts0 и HTTP3000/8001/Compose прежние. Изменений source-import/VPS deployment нет.
- [x] Обновить R13e приёмку/CLAUDE/главный план со status/HEAD/цифрами/границами. Подготовить конкретный пакет к отдельному commit/review; не коммитить/push новый этап без поручения. Полный dev-sync/merge/включение flags/deploy остаются отдельными действиями.

## Self-review и handoff

Spec coverage: owners/default-off/flags →Task1/3/4; immutable images/identity →2/4; legacy status+HTTP →3/4/6; staging/crawl →5/6; media gates →7; single lifecycle/ownership →3/6; замеры и отсутствие ложных production claims →7. Review Focus1–5 имеют явные тесты. Task3 internal418 используется только Task4 named location и проверяется Task6; Task2 release_id одинаково именован во всех consumers. При self-review устранены raw URI/query escaping риск и возможность повторной Docker-сборки frontend: raw URI —overwrite header, обе images получают один artifact named context; generated config вне hashed build. Нет нерешённых продуктовых вопросов внутри реализации, кроме отдельно вынесенных production media/release gates.

Пользователь утвердил implementation22.10.2026. Семь задач выполнены; [приёмка](r13e-html-integration-acceptance-2026-10-22.md). Отдельный commit/push с документацией поручены пользователем 22.10.2026; hosted CI проверяется после публикации. Main/VPS/24СМИ не менялись. Включение production flags и поставка не выполнялись.

Технические основания для реализации: [Nginx error_page/internal](https://nginx.org/en/docs/http/ngx_http_core_module.html#error_page) и [proxy_intercept_errors](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_intercept_errors) описывают named redirect и контролируемую обработку upstream статусов; [Docker build context](https://docs.docker.com/build/concepts/context/#dockerignore-files) —отдельный ignore конкретного Dockerfile. Эти правила дополнительно проверяются реальным gateway; чтение документации не считается runtime acceptance.

Sitemap bounds и UTF-8/XML escaping сверены с [Sitemaps protocol](https://www.sitemaps.org/protocol.html):50000 URL и52428800bytes; это проверка формата будущего endpoint, не заявление его готовности.

Решения реализации: API file>50MiB сохраняет422 (ValidatedRoute), nginx body>52MiB —413. Общие gateway_ownership.py и react_pilot_fixtures.py используются настоящим wrapper и проверками; performance вынесен в gateway_performance.cjs без копирования browser checker.
