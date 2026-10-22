# R13d: HTML + React — приёмка изолированного пилота

Дата:22.10.2026. План утверждён пользователем и выполнен. Worktree:`C:/Users/rdp6126443.gmail.com/.codex/worktrees/r5-zip-operations/humorpedia`, ветка `codex/local-page-builder`. HEAD до незакоммиченных изменений:`fa9342de7511376d2251ebbf13cdb0102b8d832a`. Код и документация составляют отдельный пакет R13d; пользователь поручил commit/push и проверку GitHub CI 22.10.2026. Итог публикации фиксируется в контексте следующего этапа.

Основания: [согласованная схема A / R13c](r13c-content-readiness-2026-10-22.md), [утверждённый план R13d](r13d-html-react-pilot-plan-2026-10-22.md), [контракт R13a](r13a-search-metadata-2026-10-22.md).

## Результат и границы

- Отдельная guarded factory `backend/html_react_pilot.py` отдаёт собранный frontend template: прежние CSS/module/nomodule/config assets, серверный head и безопасный текст вне пустого hidden React root. API и static зарегистрированы до HTML catch-all. Неизвестный маршрут —404, legacy —301; сбой чтения/невалидный template —503/noindex.
- React использует прежний `createRoot` и один обычный content GET. Опция `include_page_metadata=1` добавляется только при строгом `window.__HTML_PILOT__ === true`. Метаданные строятся сервером из уже загруженного документа; default/raw/production app не получают нового поля или дополнительных metadata reads.
- Готовность привязана к конкретному request/navigation token, а не только slug или повторно используемому history key. Layout и оба detail page передают управление после React commit. Дополнительный generic `App.jsx/WithTitle` отключён только для pilot details; прочие title effects сохранены.
- Initial HTML/head остаются при медленных chunk/API, отказе JS и сети/5xx. Подтверждённый API404 удаляет прежний fallback и ставит noindex. SPA network error без initial fallback очищает metadata предыдущей страницы. `page_metadata:null` сохраняет head initial fallback; после SPA перехода очищает старые tags к defaults. На непокрытом route очистка предшествует passive title effects.
- Legacy person text/escaping/timeline fallback/period и selected anchors приведены к существующим React renderers. Article header image, hidden-only, collapsed text/anchor и notices проверены. Интерактивные rating/poll/career/shows/correction остаются штатными API/UI.
- Непокрытые SPA routes получают исходный template; полнота их API/UI вне allowlist этим пилотом не аттестована.
- Production entrypoint/lifecycle, Mongo version, Compose/nginx, основной стенд и импорт24СМИ не менялись. На VPS ничего не выкладывалось. Canonical origin фиксирован `https://humorpedia.ru`; пилот по умолчанию noindex. Production share image,9 missing media/13 default-image pages/36 нейтральных descriptions из R13c не исправлялись этим пилотом.

## Проверки

| Уровень | Фактический результат |
|---|---|
| Полный backend `pytest -q -p no:cacheprovider tests` на отдельной Mongo8.0.32 | **1174 passed,2 skipped**,32.28s; включены PAGE_PACKAGE/SEASON_WRITE/SOURCE_IMPORT/DATABASE/PERFORMANCE/HTML_PILOT/HTML_REACT_PILOT integration flags. Skipped —2 readiness tests, запущенные отдельно ниже |
| Readiness с собственными mongodump/mongorestore | **2 passed**,4.96s: restart/backup/restore и storage/index readiness |
| Финальный targeted backend после дополнения fixtures | **14 passed**,1.95s: metadata/API/shell/lifecycle/native auth/poll/career/shows; остановка counter до закрытия Mongo и удаления owner DB |
| Полный frontend Jest | **357 passed,59 suites**,18.25s; baseline331 сохранён,26 новых tests |
| Frontend tooling | **5 passed**: Vite health/proxy/static/env/error/recovery |
| Production build | **PASS**, Node24.22.1, исходные package.json/yarn.lock совпали с frozen image dependencies; `REACT_APP_USE_API_PROXY=true` как в CI, BUILD_PATH отдельный. Последний build11.75s |
| Новый browser checker | **11 групп PASS** на окончательной сборке; отдельно **20 performance series** на той же версии frontend. Ни одного pageerror или внешнего URL |
| Старый browser smoke на окончательной сборке, default flag=false | **PASS**: login/page-builder/preview/ZIP export+import, R8 season roundtrip/conflict, R9 responsive person/team/show/quiz, R10 module/score/DnD/identity, поиск/back |
| Реальный отказ собственной Mongo | **JS-off503/noindex**, безопасный текст, без canonical; после restart Mongo **HTML200**. Не мок transport |
| Workflow | Новый checker добавлен в существующий browser-smoke job; собственная UUID DB, SIGTERM/wait и проверка её отсутствия в EXIT cleanup. YAML parsed и извлечённый shell `bash -n` PASS. Локальная приёмка выполнена до публикации; GitHub-run точного коммита проверяется после push по поручению пользователя |
| Diff/изоляция | `git diff --check` PASS; primary main/HEAD/IDs/StartedAt/restarts и HTTP/Compose сверены после cleanup |

Браузерная матрица: JS-off metadata/text/anchors/notice/301/404/image200 и0 content API/views; JS-on1280/390 —1 content GET и1 view после flush, один h1 и сохранённый SEO title; реальные rating/poll/correction/career/shows. Медленные API/chunk, JS failure, API abort, реальное архивирование между HTML и API, SPA network error, stale response, Back/Forward/refresh, начальный fragment, переход к каталогу и очистка head. Обложка действительно декодируется; collapsed text читается после открытия summary; hidden-only не возвращает legacy fallback.

Image200 подтверждён на локальном fixture-пути; доступность production OG image этим не доказывается.

Сценарии SPA в checker используют History API + событие popstate реального BrowserRouter. Ссылки из rich text намеренно делают полную навигацию и не выдаются за SPA-тест. `ready()` проверяет token-bound marker текущего pathname, а не только исчезновение initial fallback. Скриншоты делаются после завершения закрытия диалога.

Независимое read-only ревью выявило SPA stale-head при network error; RED1/9→исправление→GREEN. Дополнительный Back-кейс с уже загруженным A и повторным history key: RED2/12→token binding→полный Jest357 PASS. Независимый DOM-probe после исправлений PASS; существенных замечаний не осталось. Полные браузерные проверки и cleanup выполнил основной агент.

## Стоимость варианта A

Docker Desktop/Windows, Python3.11.17/PyMongo4.18.1, Mongo8.0.32, production React/Vite build, Chromium/Playwright1.62.1. Для каждой комбинации:3 warmup, затем5 одинаковых серий по10 полных навигаций, concurrency1. В таблице pooled p95 по50 наблюдениям; p95 —nearest rank. На10 наблюдениях p95 серии равен максимуму. Готовность —основной документ после React commit; career/recommendations и прочие виджеты не задерживают её.

| Fixture | Ready p95,ms | p95 серий,min–max,ms | HTML TTFB p95,ms | Content API p95,ms | find/навигацию,min–max | RSS сервера,MiB |
|---|---:|---:|---:|---:|---:|---:|
| people 10 KiB | 406.38 | 395.06–455.45 | 22 | 10.6 | 36.8–41.1 | 68.1–69.8 |
| people 250 KiB | 420.08 | 415.47–443.25 | 24.7 | 11.5 | 36.1–41.4 | 71.3–71.7 |
| articles 10 KiB | 409.96 | 395.55–411.28 | 20.8 | 10.5 | 23.4–24.5 | 71.4–71.6 |
| articles 250 KiB | 414.18 | 402.76–418.71 | 23.1 | 12.1 | 22.3–25.9 | 71.9–72.0 |

find —все команды данного серверного окна, включая layout/widgets и фоновые flush; это не только content endpoint и не атомарный query budget одной страницы. Raw observations сохраняют ready timing, Navigation/Resource Timing и Mongo counts каждой серии. SLO не вводился; ускорение или отсутствие регрессии относительно старого SPA этим протоколом не заявляется. Старый SPA отдавал пустую оболочку; вариант A дополнительно читает/рендерит содержательный HTML, затем повторяет обычное чтение API и запускает виджеты. Эти режимы функционально различаются.

Дополнительно использованы2 bounded representative документа из read-only снимка R13c: по одному published people/articles с≥2 modules, медианные по BSON-size среди подходящих документов. Копии5.97/10.79KB, только собственная UUID DB, без обращения к primary. HTML:11/12 find и13.54/10.52ms; content API:по2 find и6.04/4.89ms; HTML6.87/12.64KB, JSON6.31/11.47KB. Это ASGI/driver observations двух выбранных документов без всего исходного графа ссылок, не population/browser p95. Копия удалена. Общее обещание «2reads на весь путь» к A неприменимо.

## Повторение и артефакты

Новый штатный CI шаг в `.github/workflows/tests.yml` показывает полный запуск/cleanup. Для ручного изолированного запуска нужны собственная Mongo, frontend build и установленные backend dependencies; Playwright держать отдельно от app dependencies. Все переменные процесса должны указывать на эти временные ресурсы:

```bash
export HTML_PILOT_ENABLED=1 HTML_REACT_PILOT_ENABLED=1
export HTML_PILOT_RUN_ID=$(python -c 'import uuid; print(uuid.uuid4().hex)')
export DB_NAME="humorpedia_html_pilot_$HTML_PILOT_RUN_ID"
# Задать MONGO_URL своей временной Mongo и HTML_REACT_BUILD_DIR своей сборки.
python scripts/seo/react_pilot_server.py
# В другом процессе с тем же HTML_PILOT_RUN_ID и отдельным NODE_PATH:
node scripts/seo/check_react_pilot.cjs
# HTML_REACT_PILOT_MEASURE=1 задаётся серверу, HTML_REACT_PILOT_PERF=1 —checker.
# Завершить сервер SIGTERM и дождаться выхода; owner DB удаляется после views.stop.
```

Локальные ignored artifacts `.cache/r13d/`: `backend-full.log`, `readiness.log`, `backend-final-target.log`, `frontend-final.log`, `frontend-full.log` (tooling), `build.log`, `browser-final.log`/`browser/result.json` и screenshots, `performance-result.json`/`performance-summary.json`, `representative.json`, `old-browser-smoke.log`, `fault.json`/`fault.log`, `primary-before.txt`/`primary-after.txt`/`primary-proof.txt`, `cleanup.txt`. Они не добавлены в Git; устойчивые итоги приведены выше, CI сохраняет browser artifacts3дня.

## Итоговое состояние

Primary остаётся чистым `main ca46155a9640d4723c07b9fd1762a6e639563414`. Все3 исходных container IDs/StartedAt/restarts0 совпали с началом; frontend/backend HTTP200/200, Mongo healthy. Временные writers штатно остановлены, owner HTML/browser UUID DB отсутствуют, собственные containers/Mongo/anonymous volumes/network удалены. Снимок R13c и локальные отчётные artifacts сохранены. Изменения импорта24СМИ, рабочие БД/volumes, основная ветка и VPS не затронуты.

Пилот принят локально в заявленном scope. Он не подключён к production serving; следующий выпускной этап требует отдельного плана интеграции, решения по media и проверки dev-sync после интеграции. Автоматического merge/deploy из этой приёмки не следует.


## Публикация и строгая CI-сборка

R13d с документацией R13c/R13d опубликован отдельным коммитом `3b6146ffe420afbaa697ae2f2eba607c8b258f6c` в `origin/codex/local-page-builder`; remote ref проверен. [Первый CI39783235689](https://github.com/AMnEPka/humorpedia/actions/runs/39783235689) на этом SHA: backend/mongodb-integration/windows-tools PASS; frontend Jest357 и tooling5 PASS, но строгий build завершился ошибкой из-за6 предупреждений React hooks; зависимый browser-smoke пропущен.

Причина: локальная приёмочная сборка выполнялась без `CI=true`. `frontend/scripts/build.mjs` в этом режиме сообщает предупреждения; CI отклоняет их. В Person/Article effect использовал pathname/navigationKey, а dependencies содержали условные выражения, которые exhaustive-deps не может проверить.

Отдельное исправление выделяет `pilotPathname`/`pilotNavigationKey` и использует те же значения в effect и его dependencies. При выключенном пилоте они остаются null: обычные запросы/preview и защита от запоздавших ответов сохраняются. Правила ESLint и строгость CI не ослаблены. Воспроизведение: `CI=true REACT_APP_USE_API_PROXY=true yarn build` →FAIL6warnings; после исправления полный Jest **357 PASS**, строгий build **PASS**,0warnings,10.83s. Логи `.cache/r13d/ci-strict-red.log` и `ci-strict-green.log`; GitHub CI исправленного коммита проверяется после push, итог фиксируется в следующем проектном контексте.
