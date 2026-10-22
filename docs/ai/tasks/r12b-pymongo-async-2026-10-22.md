# R12b: PyMongo Async вместо Motor

Дата: 22.10.2026 (МСК). Ветка `codex/local-page-builder`, HEAD до незакоммиченных изменений `2ea75f67963c6814df974cd66479bdac45edef9e`.
Worktree: `C:/Users/rdp6126443.gmail.com/.codex/worktrees/r5-zip-operations/humorpedia`.
Статус: реализация опубликована отдельным коммитом `f97d79607dfe9122356a09f0f13f807fe86671f0` в `origin/codex/local-page-builder`. [GitHub CI39740431478](https://github.com/AMnEPka/humorpedia/actions/runs/39740431478) на этом SHA: все пять jobs success. Полный dev-sync после интеграции.
Основной checkout остаётся на `main ca46155`; его стек/БД, VPS и код импорта 24СМИ не изменяются.

## Результат и решения

- Выполняется R12b из [плана](project-refactoring-plan-2026-10-21.md): native `pymongo.AsyncMongoClient` вместо Motor, без изменения коллекций/данных и контрактов API.
- Версия `pymongo==4.18.1` сохраняется; `motor==3.7.1` удалён из requirements. В новом образе Motor отсутствует и pip check проходит.
- В `utils/database.py` сохраняются URI/credentials и pool `max50/min10/idle45s/serverSelection5s`. `get_db` возвращает один клиент на worker/event loop. `close_db` сначала отсоединяет globals, затем ожидает async close; ошибка закрытия не оставляет непригодный клиент в кеше.
- Адаптированы все семь aggregate-вызовов: каталоги/доступные буквы, случайная карточка/статья, голоса рейтинга/опроса и Mongo-admin. find по-прежнему возвращает cursor синхронно, его чтение остаётся async. Сигнатуры фейков трёх unit-наборов приведены к native API.
- Все прямые Motor imports заменены: клиент, аннотация views_counter, link_cities, fix_team_types, два старых MODX migration/import_person*.py и perf integration. Эти MODX-скрипты не относятся к 24СМИ; изменение ограничено import/constructor/async close. Скрипты записи реальных данных не запускались.
- Отдельное малое изменение deprecations: ConfigDict с прежними populate_by_name/use_enum_values и Query(pattern=...) с прежним выражением. Alias и сериализация enum сохранены.
- Native AsyncMongoClient не разделяется между event loops. Production lifecycle остаётся прежним (один loop на Uvicorn worker); compatibility shim и глобальный loop registry не добавляются.
- Полный dev-sync требует primary checkout; по ограничению пользователя main сохраняется и приёмка выполняется изолированно, как R12a. Полный sync — после интеграции.

Основания по API: [MongoDB migration](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/), [PyMongo4.18.1 collection](https://pymongo.readthedocs.io/en/4.18.1/api/pymongo/asynchronous/collection.html), [async client lifecycle](https://pymongo.readthedocs.io/en/4.18.1/api/pymongo/asynchronous/mongo_client.html). Настройки валидации: [Pydantic2.12](https://docs.pydantic.dev/2.12/migration/#changes-to-config), [FastAPI Query](https://fastapi.tiangolo.com/tutorial/query-params-str-validations/).

## Тестовая утечка и её устранение

Первый общий прогон: 1105 passed / 2 skipped, 1 failure и 1 setup error. Новый integration test обнаружил оставшийся database._client; setup старого source-import теста затем получил different event loop при close.

Временный pytest probe определил первый источник: `test_auth_guards.py` создаёт TestClient без lifespan и заявляет отсутствие Mongo, но CacheSyncMiddleware получает реальный get_db до проверки записи. Исправлена только fixture этого auth-набора: cache metadata подменяется, middleware и проверки авторизации выполняются, появление нового глобального клиента проверяется отдельным assert. Source-import тест и продуктовый cache/auth код не менялись. Точечная связка auth → native DB → source import: **172 passed**.

## Проверки

| Проверка | Результат и охват |
|---|---|
| RED → GREEN async lifecycle и aggregate-фейки | 12 failed / 74 passed на прежнем коде → **86 passed** после адаптации |
| Native-driver integration | **6 passed**: lifecycle, все aggregate-пути, русский collation/пагинация/буквы, await close, отказ старого клиента, reopen, два explain/perf контракта |
| Полный backend с opt-in Mongo наборами | **1107 passed / 2 skipped**, включая ZIP/recovery, season writes, source-import integration, новый native-driver и perf-набор. Readiness намеренно выполняется отдельно |
| Readiness/restart/restore | **2 passed**; настоящая Mongo и dump/restore private storage |
| Deprecation gate | До изменения импорт падал на Config warning; после него import с -W error::DeprecationWarning проходит, alias/enum assertions сохранены. Осталось одно стороннее PendingDeprecationWarning Starlette о python_multipart, версия framework не менялась |
| Native image dependencies | Новый backend dev image: PyMongo4.18.1, importlib.find_spec(motor) is None, pip check — exit0 |
| Изолированный cloud runtime | Gunicorn26.2.0, native PyMongo4.18.1: четыре worker boot/startup complete, tracebacks/errors отсутствуют; ready200 подтверждает Mongo/indexes/private storage. Motor отсутствует, pip check — exit0 |
| Полный browser smoke | Native backend + неизменённая Node24 production-сборка R12a: R8/R9/R10, ZIP export/preflight/apply, save/reopen, canonical IDs, stale409, 390/1120 и keyboard DnD — exit0 |
| Точная новая команда Mongo CI | **38 passed**, включая readiness и новые database/perf integration в одном pytest-процессе |
| Статическая проверка и контекст | Синтаксис 22 изменённых/new Python-файлов, actionlint/ShellCheck, diff whitespace и относительные Markdown-ссылки — успешно. Прямых Motor imports в backend/migration/scripts больше нет |

CI mongodb-integration дополнен DATABASE_INTEGRATION/PERFORMANCE_INTEGRATION и двумя файлами, чтобы новые контракты запускались после будущей публикации R12b.
Логи и одноразовые артефакты — ignored `.cache/r12b`; в документацию данные/секреты не включаются.

## Публикация R12a

Отдельный коммит `2ea75f67963c6814df974cd66479bdac45edef9e` запушен в `origin/codex/local-page-builder`. [GitHub CI39737149112](https://github.com/AMnEPka/humorpedia/actions/runs/39737149112): completed/success, backend, frontend, mongodb-integration, windows-tools и browser-smoke — success. Node24 реально проверен hosted runner.

## Продолжение

R12b опубликован 22.10.2026: `f97d796`, remote ref проверен; GitHub run39740431478 — backend, frontend, mongodb-integration, windows-tools и browser-smoke success на точном SHA. Продолжение — [R12c](r12c-vite-2026-10-22.md) в том же worktree.

Полный dev-sync из primary checkout отложен до интеграции: основной стенд сохранён на main по прямому ограничению пользователя. R12c выполняется отдельно. Модель плана — Sol/high; ограниченный независимый аудит и ревью выполнены помощником, тестовая утечка подтверждена и устранена основным агентом.

## Воспроизводимые проверки и очистка

В отдельном dev image с Mongo только собственной Docker-сети:

- `PAGE_PACKAGE_INTEGRATION=1 SEASON_WRITE_INTEGRATION=1 SOURCE_IMPORT_INTEGRATION=1 PERFORMANCE_INTEGRATION=1 DATABASE_INTEGRATION=1 pytest -q -p no:cacheprovider tests` — 1107 passed / 2 skipped.
- `READINESS_INTEGRATION=1 PAGE_PACKAGE_INTEGRATION=1 pytest -q -p no:cacheprovider tests/test_readiness_integration.py` — 2 passed.
- Обновлённая job-команда из `.github/workflows/tests.yml` с DATABASE/PERFORMANCE/READINESS flags — 38 passed.
- Полный `scripts/browser-smoke/run.cjs` в Linux Playwright1.62.1 на `scripts/browser-smoke/server.py` с собственной UUID-базой — exit0.

Исходники клиентских/типовых изменений проверены в новом backend image без установленного Motor. Production данные и standalone MODX-скрипты записи не запускались. Это функциональная приёмка миграции драйвера; matched p95-серии R11 заново не проводились, VPS SLA не оценивается.

Все собственные R12b app/cloud/Mongo контейнеры, anonymous volumes и сеть удалены после остановки writers; ignored логи/образы оставлены для воспроизведения. Primary checkout чистый: `main ca46155`. Исходные три container IDs, StartedAt и restart count0 сохранены; backend/frontend running, Mongo healthy; localhost:3000 и :8001/api/health — HTTP200. Код, тесты и task-документ импорта 24СМИ не менялись.
