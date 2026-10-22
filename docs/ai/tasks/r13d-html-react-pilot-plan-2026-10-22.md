# R13d: изолированный HTML + React — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans для последовательной реализации основным агентом; один помощник — read-only итоговое ревью. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** На собственной временной БД и production-сборке React проверить согласованный вариант A: содержательный initial HTML, затем штатный content GET и безопасная передача управления React.
**Architecture:** Отдельная guarded app factory/harness использует R13b reader и собранный HTML template. Fallback расположен вне пустого React root; React работает через createRoot. Не bootstrap/hydrateRoot: метаданные приходят opt-in в том же JSON content response, просмотры считает прежний API-путь.
**Tech Stack:** Текущие Python3.11/FastAPI/PyMongo4.18.1, React19/Vite8, Jest27, Playwright1.62.1; stdlib HTMLParser, без новых production dependencies.
**Spec:** [R13c: инвентаризация и согласованная схема A](r13c-content-readiness-2026-10-22.md).

Дата:22.10.2026. Worktree/ветка прежние, HEAD `fa9342de7511376d2251ebbf13cdb0102b8d832a`. Пользователь утвердил план R13d 22.10.2026. Реализация Tasks1–6 выполнена в том же worktree; локальная приёмка завершена, см. отчёт ниже. Метод сохраняется:root реализует, один помощник проверяет; Пользователь отдельно поручил commit/push R13d с документацией и проверку GitHub CI.

## Global Constraints

- Primary main ca46155, его контейнеры/volumes/порты и dev-sync не трогать. Импорт24СМИ, VPS, DNS и production nginx/Compose не изменять.
- Только people/articles; не расширять индексируемый scope на news/teams/shows/каталоги. Canonical origin ровно `https://humorpedia.ru`, не Host/Forwarded. Default noindex; index только явный флаг + published.
- Guard как R13b: HTML_PILOT_ENABLED=1, HTML_PILOT_RUN_ID=32lowerhex, DB_NAME=humorpedia_html_pilot_<RUN_ID>, обязательный MONGO_URL на собственной Mongo. HTML_REACT_PILOT_ENABLED=1 дополнительно для нового harness; штатное завершение с проверкой owner marker.
- Runtime frontend flag `window.__HTML_PILOT__ === true` выставляет только свой config.js harness. Default=false:сохранить нынешние fetch/title/UI без запросов новых metadata и управления fallback.
- Без изменений production entrypoint/server lifecycle, переноса данных, сохранённых проекций, SSR/Node-службы и HTML cache. HTML GET не увеличивает просмотры; API GET сохраняет прежний инкремент. JS disabled —0 content API calls/новых views, production JS initial mount —1.
- Production share image/восстановление9 отсутствующих файлов/36 description fallback — отдельные контентные решения. Здесь fixture image на собственном origin, без внешних запросов; пилот не равен готовой production индексации.
- Не повторять полный dev-sync из worktree. Сборка/браузер/БД — собственные временные ресурсы; текущие immutable assets/R13b baseline не перезаписывать.

## Review Focus

1. Person/Article переиспользуются между URL:старый response/loaded state не должен снять fallback или перезаписать head новой страницы. Tests Task4/5/6.
2. Existing usePageTitle может затереть SEO title на loading; head должен оставаться согласованным до opt-in metadata и очищаться при уходе. Task4/5.
3. JS/API failure не оставляет пустой экран; подтверждённый404 между HTML и API удаляет старый контент, network error его сохраняет. Task4/5/6.
4. Legacy text/SQL escaping/anchors/notice могут отличаться между двумя renderer даже без JS-ошибок. Task2/6.
5. Factory/API/static registration после catch-all может дать404 для assets/API; background view flush после cleanup может восстановить удалённую БД. Task3/6.

## Файлы и интерфейсы

| Файл | Роль |
|---|---|
| backend/services/page_response_metadata.py (new) | opt-in metadata adapter к существующему builder, без повторного чтения |
| backend/routes/content_people.py, content_articles.py | совместимый include_page_metadata=False, только public/non-raw ответ |
| backend/services/html_text.py, public_html.py | ограниченная parity legacy text/timeline и anchors выбранных блоков |
| backend/services/html_react_shell.py (new) | собранный frontend template + SEO head + fallback, сохранение всех assets |
| backend/html_react_pilot.py (new), backend/html_pilot.py, routes/html_pilot.py | новая isolated factory и маленький render callback extension R13b, прежний default сохранён |
| scripts/seo/react_pilot_server.py, check_react_pilot.cjs (new) | owned seed/lifecycle/сборка/браузерная матрица |
| frontend/src/public/utils/htmlPilot.js (new) | runtime flag, route token, DOM handoff и общий head owner |
| frontend/src/public/utils/api.js, frontend/src/utils/pageTitle.js | opt-in query flag и backward-compatible отключение title effect |
| frontend/src/public/pages/PersonDetailPage.jsx, ArticleDetailPage.jsx; public/components/Layout.jsx; App.jsx (WithTitle) | ready/error signals и сброс head при навигации |
| backend/tests/test_page_response_metadata.py, test_html_react_shell.py, test_html_react_pilot.py (new); test_public_html.py | unit/ASGI/lifecycle; старые tests остаются |
| frontend/src/public/utils/htmlPilot.test.js; public/pages/htmlPilotPages.test.jsx (new) | DOM/head/navigation/stale API paths |
| backend/tests/fixtures/html_react_pilot.json (new) | общие synthetic cases, не raw реальная БД |
| .github/workflows/tests.yml | browser job запускает новый checker после штатного smoke на собственных ресурсах |

## Task 1: opt-in metadata без повторного content GET — Sol/high

**Produces:** `attach_page_metadata(kind: Literal["people","articles"], document: dict, request: Request|None, *, enabled: bool) -> dict`. Использует `request.app.state.html_page_metadata` только при enabled=True; config имеет site_origin/indexing_enabled/default_image_url как у R13b. Нет config — вернуть прежний документ. Есть config — новый dict с `page_metadata=asdict(build_page_metadata(...))`; metadata error →page_metadata:null, без утечки exception/падения исходного API. Config создаёт только новый harness.
**Route contract:** новый keyword/query `include_page_metadata: bool = False` (Annotated Query с обычным False default); если raw=true — не обогащать и не дописывать computed поле. Никаких новых DB reads/increments для metadata.

- [x] RED `test_metadata_is_opt_in_and_uses_existing_document`: default/non-pilot/raw response равен прежнему; enabled+configured возвращает title `Альфа — карточка | humorpedia.ru`, canonical `https://humorpedia.ru/people/alpha`; input не мутирует.
- [x] Run `pytest -q tests/test_page_response_metadata.py` →FAIL отсутствующего adapter.
- [x] Реализовать adapter, подключить его после существующего resolve/decorate в двух GET. Для прямых route calls request=None сохраняет старое поведение; bool Query default не становится truthy object.
- [x] Добавить `test_metadata_failure_does_not_break_json` и `test_metadata_does_not_add_views_or_reads`: invalid slug→JSON200/page_metadata:null; tracked CRUD/read/view calls равны baseline, Host/raw/staff не задают config.
- [x] Run новый набор + existing content/auth guards tests →PASS; production app не устанавливает config.

## Task 2: parity выбранного текста и anchors — Sol/high

**Consumes:** существующий HtmlPage/TextBlock/render_html_page. **Produces:** backward-compatible `TextBlock(heading,body_text,anchor_id: str|None=None)` и `normalize_person_rich_text(value: str) -> str` в html_text.py.
Ровно повторить bounded person normalization из текущего PersonDetailPage:экранированные newline/quotes/slashes/angle brackets; никаких новых правил source-import sanitizer.
People:text_block получает section-<content_index>; timeline —timeline-<index>/timeline-<index>-event-<i>, period и default `Хронология`, fallback content_html→content при пустых events; legacy text повторяет текущий person renderer. Articles:общий renderer text_block anchor_id либо title lower/space→dash; timeline date/year/title/events как сейчас. Не включать неподдержанный article legacy text, если общий renderer его не выводит.

- [x] RED fixtures `test_person_legacy_text_timeline_and_anchors` / `test_article_explicit_anchor_and_notice`: тексты/period/dates/идентификаторы совпадают с текущим React; malformed HTML/attribute escaping безопасны, sidebar/hidden исключены, equal order стабилен.
- [x] Run `pytest -q tests/test_public_html.py` →FAIL нового поведения.
- [x] Реализовать только перечисленные ветви/optional anchor_id, сохранить shape/positional constructors R13b. Не менять React renderer ради соответствия новому Python.
- [x] Run metadata/public_html tests →PASS; общий fixture используется в browser parity Task6. Непокрытые media/interactive types остаются явно отмеченными.

## Task 3: guarded shell и minimal public API harness — Sol/high

**Produces:** `render_react_shell(page: HtmlPage, template_html: str) -> str`; `create_app() -> FastAPI` в html_react_pilot.py; `create_fixture_app()` в scripts/seo/react_pilot_server.py.
Малое расширение R13b:create_app/create_router принимают keyword `render_page` с нынешним render_html_page default. Новый factory передаёт shell renderer; все прежние R13b callers/default сохраняются.
Shell читает только свой `HTML_REACT_BUILD_DIR/index.html`:валидирует один пустой root, сохраняет scripts/CSS/polyfill/config assets и viewport, заменяет owned SEO теги/ru, вставляет `#html-pilot-fallback[data-path]` вне `#root`. Root первоначально hidden/aria-hidden только для такого HTML; без bootstrap JSON. Некорректный template→безопасный503/noindex.

- [x] RED `test_shell_has_one_root_and_preserves_assets`:один title/canonical/OG набор, все hashed/legacy chunks и config script сохранены, fallback вне hidden root, </script> в контенте не создаёт активный script. Fixture template содержит CSS/module/nomodule.
- [x] RED `test_factory_rejects_unowned_database` и `test_api_assets_precede_legacy_catchall`:bad flag/DB/build path отклоняется до seed; GET/api/assets/config работают, arbitrary unknown404, R13b redirects прежние.
- [x] Реализовать shell/factory/render callback; config.js harness выставляет boolean flag и loopback API base. Assets из фактически собранного template, без hardcoded hashes/пакетных зависимостей.
- [x] Собрать **allowlist route objects**, сохраняя исходные dependencies, перед HTML catch-all:content detail GET2; GET/content/articles, GET/sections; GET/competitions/people/{id_or_slug}/career (из memberships); GET/show-appearances/people/{person_id}; GET/recommendations и related-news/{entity_type}/{entity_id}; GET+PUT/ratings/{entity_type}/{entity_id}; GET/polls/{poll_id}, POST/polls/{poll_id}/vote; POST/correction-suggestions; POST/auth/login и GET/auth/me. Не регистрировать import/admin/editor CRUD, register/OAuth, season sync и фоновые schedulers.
- [x] Harness создаёт только own fixtures/owner/test user/test poll и нужные собственные индексы. Lifespan:get_db/ping→views_counter.start(db); finally:views_counter.stop/flush→owner cleanup→close_db в том же loop. Подключить limiter state/handler как в server для включённых vote/correction routes, не импортируя server app/lifespan.
- [x] Known uncovered SPA paths своего harness:`/`,`/people`,`/articles`,`/news` — прежний собранный shell без metadata прошлого detail; остальные direct unknown404/legacy по R13b. Это test routing, не изменение production policy остальных разделов.
- [x] Run `pytest -q tests/test_html_react_shell.py tests/test_html_react_pilot.py` →PASS; интеграция доказывает HTML GET views delta0, один JSON GET +flush delta1; запрещённые routes отсутствуют, shutdown не воссоздаёт БД.

## Task 4: один head owner и DOM handoff — Sol/high

**Produces (htmlPilot.js):** `isHtmlPilotEnabled() -> boolean`; `beginPage(pathname: string) -> token`; `commitPage(token, {status:"ready"|"not_found"|"network_error", metadata:object|null}) -> boolean`; React hook `useHtmlPilotNavigation()`.
Token связан с текущим pathname и generation; stale commit возвращает false без DOM/head эффектов. Initial server head сохраняется во время loading. После ready commit показать root/убрать fallback;404→показать существующую ошибку/noindex/очистить старые SEO; network_error→сохранить server fallback/head и добавить доступный статус. Для JS SPA transitions без initial fallback root остаётся доступным.
На уходе в непокрытый route очистить только owned title/canonical/OG/robots и восстановить исходные shell defaults, без новой production noindex-политики остальных разделов. Layout вызывает navigation hook в layout effect до passive title effects непокрытых страниц; flag=false все операции no-op.

- [x] RED Jest `keepsServerHeadWhileLoading`, `staleTokenCannotCommit`, `handoffIsAtomicAndErrorSpecific`:SEO title не превращается в `Человек`, stale token не снимает fallback, network_error сохраняет его, not_found удаляет старый текст/noindex.
- [x] Run `yarn test --watchAll=false --runInBand --runTestsByPath src/public/utils/htmlPilot.test.js` →FAIL.
- [x] Реализовать flag/navigation/head ownership/handoff; DOM меняется после React commit, не через таймер готовности. Метаданные — только из Python API/initial HTML; не дублировать алгоритмы title/URL/robots в JS.
- [x] Добавить Back/Forward, detail→uncovered, no metadata/null metadata, malicious field escaping и flag=false no-op; повторить targeted Jest →PASS.

## Task 5: два detail page и прежний API путь — Sol/high

**Consumes:** Task1 page_metadata, Task4 tokens/commitPage. **Produces:** backward-compatible `usePageTitle(pageTitle, {enabled=true}={})`; publicApi.getPerson/getArticle добавляют include_page_metadata=1 только при runtime flag. Никакого отдельного metadata/content prefetch.
В Person/Article хранить requested slug/generation результата вместе с status; ready возможен только после успешного ответа именно текущего запроса. Унаследованный loading=false/document предыдущего slug не считается ready. Фиксировать error status404/network раздельно для handoff, не менять прежний UI при flag=false/preview. Callback из useLayoutEffect после commit нужной страницы; title effect отключён только в pilot mode.

- [x] RED `htmlPilotPages.test.jsx`:включённый flag делает один обычный GET с opt-in query и сохраняет SEO title; выключенный —старый query/title, preview не запрашивает content.
- [x] RED race fixtures:A→B, B response раньше A, loading state от A; fallback/head остаются уB. API404 убирает старый initial text, network failure не оставляет пустой screen.
- [x] Run targeted Jest →FAIL; подключить hooks/optional title flag/request generation, сохранить career/appearances/rating/related/correction code.
- [x] Run new tests + PersonDetailPage/API/pageTitle existing tests →PASS. Полный Jest —Task6, не переписывать331 baseline тест.

## Task 6: production browser и окончательная приёмка — Sol/high

**Produces:** scripts/seo/check_react_pilot.cjs и общие fixtures; изолированная воспроизводимая проверка, без установки Playwright в app dependencies. Обязательные source files одного владельца root, помощник только read-only review.

- [x] Собрать production frontend в своём `.cache/r13d/frontend-build` (Node24.22.1, frozen lockfile, BUILD_PATH); не заменять R13b baseline build. Запустить Task3 harness со свежими runId/DB, отдельной Mongo/network/temporary uploads; own config flag=true, no published primary ports.
- [x] Checker проверяет runId/database status до запросов, блокирует external origins; JS-off:metadata/text/anchors/notices/301/404/image200, HTML0 views;503 проверен отдельным browser fault-run с реальной остановкой собственной Mongo и восстановлением200. JS-on:SEO title переживает mount, один content GET/view после flush, full React UI появляется один раз.
- [x] Synthetic slow chunk/API/network/404/stale navigation/Back/Forward/direct refresh; JS failure сохраняет fallback. Две viewport ширины1280/390; initial fragment/anchor и переход к непокрытому route очищают старый head.
- [x] Через реальную own API проверить rating PUT, poll vote (own test user/login), correction POST202, career/appearances. Не mock-обходить разрешения и не отправлять сообщения/формы во внешние сервисы.
- [x] Unit/API/integration + полный backend и baseline/frontend Jest/tooling/build; прежний scripts/browser-smoke после frontend changes. В existing CI browser-smoke добавить второй checker с отдельной UUID БД/ресурсами и обязательным finally cleanup.
- [x] На bounded real representative fixtures и synthetic10/250KiB зафиксировать HTML+API командные counts/полный time-to-ready/RSS, network timings и5 одинаковых warm серий по10 полных навигаций на каждую комбинацию типа/размера, после3 warmup навигаций, concurrency1; сравнение с прежним SPA описывать с разницей функциональности, без выдуманного production SLO. A не обещает2 reads/GET.
- [x] Ревью общего diff и требований R13c, обновление task/CLAUDE/главного плана. Штатно остановить own writers/server, проверить owner DB удалена, удалить own Mongo/volumes/network. Primary main/HEAD/IDs/StartedAt/restarts и HTTP3000/8001/compose должны совпасть с началом.
- [x] Подготовить конкретный пакет к commit/review; commit/push/production integration —только по поручению. R13d считается принятым при фактическом прохождении матрицы, а не наличии нового factory.

## Self-review и handoff

Требования R13c покрыты Tasks1–6:общий metadata source/compatibility→1, selected text parity→2, HTTP/изоляция/lifecycle→3, head/handoff→4, stale states и прежний fetch→5, browser/UI/стоимость/cleanup→6. Interface names/config/token/optional fields согласованы; review risks привязаны к конкретным tests. Новых продуктовых вопросов сверх согласованного A в плане нет; image/content remediation остаётся отдельным будущим выпускным gate.

Пользователь утвердил план R13d. Основной агент реализовал изменения последовательно, независимый помощник проверил общий diff и две исправленные границы навигации. Сводная приёмка и условия измерений записываются в [отчёте R13d](r13d-html-react-pilot-acceptance-2026-10-22.md).
