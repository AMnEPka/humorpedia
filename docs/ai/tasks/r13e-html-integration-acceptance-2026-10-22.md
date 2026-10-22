# R13e — приёмка подключения HTML

Дата: 22.10.2026. Статус: локальная реализация и приёмка завершены; пользователь поручил отдельный commit/push R13e с документацией и проверку CI. Ветка codex/local-page-builder, базовый HEAD реализации 98f37bb7c7943ae1da976c6f803fb50425e2b6e0. План утверждён пользователем 22.10.2026. Этот отчёт фиксирует локальную приёмку; hosted CI проверяется после публикации на точном новом SHA.

## Результат и границы

Опциональные people/articles HTML, legacy dispatch, robots/sitemap работают внутри настоящего FastAPI с единственным родным lifespan. Nginx и backend получают один готовый артефакт с SHA256 всех файлов; отдельные serving/indexing flags выключены по умолчанию. Текущие dev/cloud Dockerfiles, Compose и VPS-конфигурации не переключались. Новые targets в Dockerfile.public-html — подготовка будущего выпуска, не действующая выкладка.

Основной технический план R0–R12 реализован в ветке, но общая поставка ещё требует разрешённой интеграции и main dev-sync. R13 — отдельный продуктовый инкремент сверх исходной суммы работ. После R13e остаются выпускные content/media gates, интеграция/приёмка и отдельно разрешённая выкладка. SEO других типов и UX-план не входят в этот этап.

## Конфигурация

| Настройка | Контракт |
|---|---|
| PUBLIC_HTML_ENABLED | только true/false, default false |
| SEARCH_INDEXING_ENABLED | только true/false, default false; false/true запрещено |
| PUBLIC_HTML_BUILD_DIR | обязателен при serving=true; в новом backend target /opt/public-html/build |
| PUBLIC_HTML_DEFAULT_IMAGE_URL | явно заданный URL при serving=true; для тестов /media/pilot-share.png |
| canonical | всегда https://humorpedia.ru, независимо от Host/Forwarded |
| frontend runtime | строгий boolean window.__PUBLIC_HTML_ENABLED__; старый pilot flag только для совместимости тестового приложения |

Один build создаётся Node24.22.1/frozen dependencies. Post-build manifest public-html-release.json включает index/module/nomodule/CSS/dynamic chunks/public assets и исключает себя. Генерируемые Nginx/runtime варианты находятся в bundle/gateway-configs вне hashed build; config.js — runtime overlay. Обе images получают bundle через named context public_html_release, без повторной сборки frontend. Backend проверяет release один раз при регистрации; missing/corrupt release закрывает HTML и public_html readiness с503, API liveness сохраняется.

Gateway перезаписывает X-Humorpedia-Release и X-Humorpedia-Original-URI. Проверка release — защита от рассинхронизации, не авторизация. Только named legacy location перехватывает private418 и возвращает прежнюю SPA; known unavailable404 и DB error503 не маскируются. Внешний /_internal закрыт. Conditional backend readiness проверяет собственный artifact, gateway readiness дополнительно проверяет пару и indexing mode.

## Проверки

| Уровень | Результат |
|---|---|
| Config/unit/API/native Mongo, полный backend | 1192 passed,16 skipped;15 source-import integrations не включались,1 отдельный React-pilot integration выполнен отдельно:1PASS |
| Frontend | 362 tests/59 suites PASS |
| Node tooling | 11 PASS |
| Strict build | CI=true,0 lint warnings; повторная сборка дала тот же identity |
| Release identity | 16755fe3939e00d62b806148c6f86df87540c6c9b322c1594806c3e2cf554067 |
| Nginx | 1.29.3, три конфигурации nginx -t PASS; новые assembled targets PASS |
| Native gateway | disabled/closed/indexed-fixture PASS, финальный UUID4a07e5e8831740fcbfe60b0eb79f8f26 |
| Browser через gateway | 11 групп R13d PASS: JS-off/on1280/390, metadata/text/anchors/notices/header image, real rating/poll/correction/career/shows, network/chunk/abort/archive, stale A–B–A/Back |
| Accounting | 0HTML views,1API content GET/view; штатные JSON default/raw сохранены |
| ZIP/auth/CAS | 401/403/409,20MiB default/52MiB preview,120s timeout;51MiB multipart проходит gateway и отклоняется API с422 «ZIP больше50MiB»;53MiB body даёт nginx413 |
| Crawl | closed Disallow:/ + empty XML; indexed только published people/articles; live slug/status, safe canonical, no views |
| Hosted CI R13e | не запускался: новые изменения пока не опубликованы; предыдущий published98f37bb/run39783968388 success |

Полный backend запуск использовал собственный Mongo8.0.32 и tmpfs без host ports. Первые два сбоя были отсутствующими /scripts при неверном mount; после запуска с полным корнем проекта1192PASS. Это устранение тестового окружения, без изменения импорта/данных.

Fresh Astra/high whole-diff review нашёл timeout/null как ложный успех и HEAD405 в legacy dispatcher. Оба воспроизведены RED и исправлены; Node2 timeout/resource guards + Python3 actual DB ownership guards + unit4 routes GREEN. Ревью текущих production/code/tests/tooling/CI не имеет открытых Important/Critical; финальные native HEAD200/301/404, readiness pair mismatch и forced-failure cleanup PASS; итоговый delta review не выявил открытых Important/Critical; исторические формулировки схемы уточнены.

## Воспроизведение и изоляция

Из корня worktree после одной strict Node24 сборки:

    BROWSER_BUILD_DIR=<готовый build с manifest> node scripts/seo/run_gateway.cjs

Tool требует32hex runId, создаёт отдельные humorpedia_html_gateway_<UUID> DB, internal Docker network, собственные backend/gateway/Mongo/checker containers и image tags. Mongo /data/db и /data/configdb — tmpfs, ни одного primary volume/port. До импорта server wrapper устанавливает собственные uploads/packages/builder/backups, synthetic auth; import jobs/credentials не сидируются, внешний egress заблокирован. Fixture/control routes присутствуют только в wrapper. Cleanup DB следует после остановки native writers; потеря ownership запрещает delete. Артефакты по умолчанию .cache/r13e/<UUID>/{commands.json,docker.log,cleanup.json,result.json}; exact Docker argv записан в commands.json. Проверки ошибки также выполняют finally cleanup.

Измерения: HTML_GATEWAY_MODES=closed HTML_GATEWAY_PERF=warm —4комбинации people/articles10/250KiB,3warmup,5×10nav,concurrency1. Для cold дополнительно HTML_GATEWAY_PERF=cold, HTML_GATEWAY_PERF_KIND=people|articles, HTML_GATEWAY_PERF_KIB=10|250; каждый из3повторов запускает orchestrator заново с новой UUID/процессами/browser context. Измеряются observed core_ready после goto(load)+waitForFunction и конец API/widget ресурсов; это не точный внутренний React timestamp. Quiet period networkidle используется только для завершения набора ресурсов и не добавляется в recorded widget responseEnd. Сырые navigation/resource timings, Mongo commands и RSS сохранены отдельно; production SLO и сравнение с иной топологией не заявляются.


## Измерения native gateway

200 измеренных warm полных навигаций +12warmup;12 cold навигаций с новой UUID/процессами/browser context. Concurrency1, viewport1280x900, internal network/Mongo8.0.32, тот же release16755fe. Основной сайт не участвовал. Warm и cold —разные условия; сравнение с R13d/VPS и production SLO не заявляется.

| Комбинация | N warm | core median / p95,мс | widgets p95,мс | HTML p95 / content API p95,мс | find/nav | backend RSS max,KiB |
|---|---:|---:|---:|---:|---:|---:|
| people 10KiB | 50 | 389.1 / 421.5 | 456.3 | 25.2 / 14.9 | 39.46 | 84228 |
| people 250KiB | 50 | 420.1 / 464.3 | 477.8 | 35.4 / 21.4 | 39.52 | 86044 |
| articles 10KiB | 50 | 396.9 / 453.2 | 463.5 | 16.6 / 14.7 | 24.54 | 85800 |
| articles 250KiB | 50 | 427.1 / 490.2 | 490.2 | 34.1 / 20.0 | 24.52 | 85868 |

| Комбинация cold | N | core median [min,max],мс | widgets median [min,max],мс | backend RSS max,KiB |
|---|---:|---:|---:|---:|
| people 10KiB | 3 | 444.5 [429.7,454.9] | 473.7 [459.2,490.4] | 83436 |
| people 250KiB | 3 | 484.3 [476.3,509.3] | 512.4 [500.0,560.9] | 83788 |
| articles 10KiB | 3 | 443.1 [432.7,462.4] | 469.0 [460.8,484.0] | 83152 |
| articles 250KiB | 3 | 463.6 [463.2,465.8] | 487.1 [485.1,494.2] | 83468 |

Для3 cold samples p95 не интерпретируется как статистическая граница. Mongo commands совокупны: HTML+content API+виджеты/фоновые native задачи и измеритель; это не число запросов одного reader. Raw series содержат find/aggregate/update/прочие команды и все API timings. RSS —backend process после серии, не весь Docker/Mongo/браузер. Warm peak86044KiB.

## Итоговая runtime/evidence

- Старый полный browser smoke (preview/quiz/season/editor/DnD/search/back) PASS; старый R13d pilot11групп PASS. .cache/r13e/legacy; native React accounting отдельно1PASS.
- Broken release UUID1ed16b303f2442c2823f749a33c383d2: API health200, HTML/sitemap503/noindex, public_html readiness503/error и gateway not-ready; cleanup PASS.
- Forced checker failure UUID7d96092905344f7d88966e79baa593cd возвращает ненулевой код выхода; native writers останавливаются, owned DB удаляется, checker/containers/network/images очищаются; cleanup.json без ошибки. Timeout/null/signal unit2 PASS. Python3 проверяют запрет foreign DB, nonempty seed и drop после потери marker теми же guards, что использует wrapper.
- Nginx HEAD: SPA/каталоги200, legacy301, archived404, пустое тело; missing assets/media404. Spoof-header overwrite, no public418/internal endpoint; default-image200/image/png и browser decoding PASS.
- Primary: чистый main ca46155a9640d4723c07b9fd1762a6e639563414. Backend6e4c3567/frontend0cba07b3/Mongo21cb1fd6 и StartedAt прежние, restarts0, HTTP3000/8001 —200/200, Mongo healthy. Mounts указывают на основную папку; .cache/r13e/primary-final.json без env/secrets.
- Source-import/scheduler/VPS конфигурации не менялись; main dev-sync не запускался. Реальные media/данные не редактировались.
- Ignored evidence: .cache/r13e/performance-summary.json,13measurement UUID, frontend/backend logs, exact Docker argv/cleanup каждого run; в commit это не включается.

## Оставшиеся gates

- Выбрать production share image и восстановить9 отсутствующих media либо отдельно согласовать fallback; fixture PNG это решение не подменяет.
- 13 страниц без собственного image/36 нейтральных description — редакционная очередь, реальные документы не изменялись.
- Production serving/indexing остаются off; остальные content types сохраняют SPA.
- Merge/main sync, полная приёмка основного стенда и VPS deployment требуют отдельного поручения.
