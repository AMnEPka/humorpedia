# R8: каноническая запись сезонов

Дата: 21.10.2026. Worktree: `C:/Users/rdp6126443.gmail.com/.codex/worktrees/r5-zip-operations/humorpedia`.
Ветка: `codex/local-page-builder`. HEAD до изменений R8: `85ba090ea11684172f053bd89c448d961212e33d`.
R7 опубликован отдельным коммитом с документацией; удалённый ref подтверждён. R8 пока не публикуется.

## Цель и границы

Сделать `seasons` единственным владельцем данных соревнования; `kvn.season_data` и `participations` — воспроизводимыми проекциями.
Название/slug/путь и оформление страницы остаются отдельными полями страницы по текущему контракту `SeasonUpdate`.
Основной checkout остаётся чистым на main `ca46155`, импорт источников не меняется, VPS не обновляется.
Миграции/обновления в общей БД запрещены в этом этапе; проверки выполняются на отдельной копии и fixture-БД.

## Решения

- Согласовано ранее в R3: отсутствие/несовпадение обязательной версии записи сезона возвращает 409.
- Согласовано в R8: `PUT /content/kvn/{id}` сохраняется как адаптер; при передаче season_data нужны версии страницы и канонического сезона. Админка переходит на `/competitions/seasons`.
- Подтверждено пользователем: журнал восстановления проекций и безопасный повтор на существующей standalone Mongo; без replica set и смены Mongo.
- Содержательные расхождения данных не разрешаются автоматически в пользу одной коллекции. Сначала read-only отчёт, затем отдельное решение для конфликтующих записей.

## Исходные факты

| Путь | Текущая операция и риск |
|---|---|
| `PUT /competitions/seasons/{id}` | CAS канонического сезона, затем delete/insert participations и безусловная запись season_data в страницу |
| `PUT /content/kvn/{id}` | CAS страницы при season_data, затем замена сезона без проверки его версии; title/slug/status тоже запускают обратный sync |
| `sync_kvn_pages` / startup bootstrap / миграция | Обратная пересборка каноники из legacy; непригодна как будущий rebuild проекций |
| Создание/import сезона, изменение/удаление команды | Пишут legacy и запускают обратный sync; должны перейти на общий путь |
| `SeasonDataEditor` и `SeasonDetailPage` | Оба используют legacy-формат; публичную проекцию нельзя удалить до перехода читателей |
| Raw Mongo admin и прямые ремонтные скрипты | Привилегированные обходы, требуют явного эксплуатационного режима и отдельного контроля |

Точки: `services/competitions.py:700–780`, `routes/competitions.py:101–117`,
`routes/content_kvn.py:878–882,1242–1247`, `routes/content_teams.py:850–1007`,
`services/season_import.py:141–171`. Это найденные границы гонки, а не доказательство уже случившейся потери данных.


Дополнительные найденные writers: `scripts/migrate_competitions.py:63` вызывает sync под --apply;
`scripts/fix_legacy_links.py:82,88` пишет документ и синхронизирует KVN;
`scripts/fix_kvn_seasons_league_slug.py:65`, `scripts/fix_ml_kvn_before_2014.py:142`,
`scripts/fix_kvn_2011.py:186` напрямую меняют season_data. Это пути относительно backend.
При переключении они должны обращаться к каноническому workflow либо выполняться как отдельно согласованные repair-операции.

## Копия данных

Из локальной основной Mongo выполнено только чтение шести коллекций. Запись шла в отдельную одноразовую MongoDB 8.0.32
без общих томов и опубликованного Mongo-порта, БД `humorpedia_r8_copy_20261021`.
Передача проверена совпадением SHA-256 потока и количества документов:

| Коллекция | Документов |
|---|---:|
| kvn | 152 |
| seasons | 122 |
| tournaments | 5 |
| teams | 1310 |
| people | 1041 |
| participations | 9276 |

Это последовательная копия выбранных коллекций работающего стенда, не транзакционный snapshot и не резервная копия.
Исходные workers не останавливались. Перед будущим переносом на реальной цели требуется свежая согласованная сверка.
Приложение на копии до отчёта не запускалось: startup sync мог бы изменить исходное состояние сравнения.

## Порядок продолжения

| Шаг | Результат / проверка | Рекомендуемая модель |
|---|---|---|
| R8.1 | Read-only reconciliation по page_id: нормализованная проекция, metadata, canonical round-trip; тесты missing/duplicate/invalid/cap и неизменности входа/БД | Sol / high |
| R8.2 | Общий workflow — общий versioned workflow, адаптер с двумя версиями и воспроизводимые проекции; конкурентные и failure tests | Astra / high для границ протокола, Sol / high для реализации |
| R8.3 | Переключить админку и служебные writers, сохранить публичный legacy-render; UI/API create/edit/reorder/rename/role/person-only | Sol / high |
| R8.4 | Rebuild на копии: канонические документы неизменны, повтор без дублей, reconciliation без новых расхождений; полный backend/frontend и browser smoke | Sol / high |

Sol = `gpt-6.1-sol`, Astra = `gpt-6-astra`; это рекомендации для подэтапов, не смена модели чата.

## Контрольная точка R8.1 (до продолжения)

R8.1 выполнен: добавлены `services/competition_reconciliation.py`, CLI `scripts/report_competition_reconciliation.py`
и 14 unit/CLI сценариев. Воспроизведён RED отсутствующего сервиса; затем дополнительные RED выявили
неверную классификацию nonseason-страниц, равенство bool/int, потерю категорий при cap, загрязнение DB_NAME,
несовпадение фактической БД и остановку отчёта повреждённым full_path. Эти случаи исправлены.

Полный backend на отдельной Mongo: **1027 passed / 15 skipped**, четыре существующих deprecation warning.
Включены PAGE_PACKAGE_INTEGRATION, SEASON_WRITE_INTEGRATION и READINESS_INTEGRATION; source-import integration выключен.
Frontend/build/browser UI не запускались: frontend и HTTP-пути в R8 не менялись. Hosted CI не запускался.

[Полный отчёт по всем 122 сезонам](r8-season-reconciliation-2026-10-21.md): нормализованные проекции и metadata совпадают;
406 round-trip различий в 107 сезонах — только missing stage.comment против пустой строки.
Прочитаны все различия без truncation. Хеши шести коллекций до и после CLI совпали.
Левая сторона JSON diff — сохранённый канонический документ/его проекция, правая — legacy-проекция либо реконструированная каноника.
Статус equal_projection не означает, что любые канонические поля представимы старой моделью.

Независимое статическое ревью сверило join, типы/null, cap/counters и неизменность входов.
Последний дефект malformed full_path дополнительно воспроизведён основным агентом и проверен полным набором.

Эта сохранённая точка завершала только R8.1. Продолжение после ответа пользователя описано ниже.

Финальная сверка контрольной точки: main чистый на `ca46155a9640d4723c07b9fd1762a6e639563414`;
ID/StartedAt/restart count backend/frontend/Mongo совпадают с исходным снимком.
Основной сайт и `/api/health` вернули 200, `docker compose ps` подтвердил работающий стек.
После отчёта и проверок одноразовая Mongo R8 с копией, сеть и обе Mongo volumes удалены.
Для продолжения с данными потребуется новая копия; отчёт выше сохранён как результат конкретного среза.
Удалённая ветка рефакторинга подтверждена на R7 `85ba090`; R8 остаётся незакоммиченным пакетом в прежнем worktree.
Импорт источников, конфигурация VPS и рабочие данные основного стенда этой задачей не изменялись.


## Продолжение R8: контрольная точка перед публикацией

21.10.2026, тот же worktree и HEAD `85ba090`. Выбран журнал без изменения инфраструктуры.

- `season_projection.py`: claims сезона и страницы, version-CAS, журнал в том же canonical write,
  snapshot строк participations и patch страницы, состояние applying/error/ready.
  Ошибка после commit возвращает сохранённый сезон с projection_status=error.
  Retry не меняет содержимое и updated_at сезона; автоматического takeover нет.
- Canonical API и legacy-адаптер используют общий save; legacy требует версии страницы и сезона.
  GET/PUT возвращают editor_data и page_updated_at. Метаданные страницы не восстанавливают
  содержимое соревнования из stale season_data.
- `season_editor.py`: sidecar canonical IDs этапов/игр, запрет чужих/повторных ID, сохранность
  person_id, extra и исторических team_id при неизменном участнике.
  Сопоставление legacy без sidecar использует однозначное совпадение; неоднозначные ссылки
  не выбираются по позиции. Нативный canonical API остаётся способом явно задать ID.
- KVNEditPage загружает canonical сезон и сохраняет его через API competitions.
  409 сохраняет черновик; pending/error оставляет данные видимыми, блокирует повторную запись
  тела и даёт кнопку повтора проекций. Пустой объект season_data не превращает страницу лиги
  в отсутствующий сезон. Copy игры получает новый ID; bulk replacement не теряет person refs молча.
- Bootstrap создаёт только missing canonical; /sync восстанавливает проекции.
  Переименование/удаление команды пишет канонику с CAS; исторические названия сохраняются,
  повтор после частичного конфликта использует точный team_id.
  Создание и дублирование страницы инициализируют missing canonical.
- Добавлен CLI `scripts/rebuild_season_projections.py`: read-only по умолчанию, явная БД,
  rebuild/retry и освобождение exact-token claim после остановки workers.
  Старые одноразовые legacy repair --apply отключены; fix_legacy_links переведён на canonical save.
  Raw Mongo import/delete защищённых коллекций и aggregation write stages больше не обходят workflow.

Ограничение протокола: проекции согласуются последовательно. Во время сбоя чтение может видеть
частично обновлённые связи до retry; межколлекционная атомарность не заявляется.
Журнал охватывает save/rebuild/retry. Физическое удаление страницы и пакет изменений команды
не являются общей транзакцией; активные/pending claims блокируют удаление.
Прямые внешние Mongo writers требуют остановки приложения и отдельного repair-процесса.

### CI: причины и локальное исправление

- [Main run 39571996187](https://github.com/AMnEPka/humorpedia/actions/runs/39571996187):
  backend падает в Initialize containers, до pytest. MongoDB 8.0.32 отказывается стартовать
  на новом ядре runner (сообщение Linux kernel versions 6.19 and newer).
  [MongoDB SERVER-121912](https://jira.mongodb.org/browse/SERVER-121912) описывает tcmalloc/rseq;
  [исходник r8.0.32](https://github.com/mongodb/mongo/blob/r8.0.32/src/mongo/db/startup_check_rseq.cpp)
  проверяет активность per-CPU cache перед отказом.
- [R7 run 39600411894](https://github.com/AMnEPka/humorpedia/actions/runs/39600411894):
  jobs отсутствуют; gh сообщает workflow file issue. Actionlint 1.7.12 воспроизвёл две ошибки:
  job.services.mongodb.id и runner.temp недопустимы в job-level env.
- Services заменены запуском Mongo после checkout через scripts/ci/start-mongodb.sh,
  используя существующий seccomp-профиль с запретом rseq; Mongo остаётся 8.0.32.
  URL/ID задаются через GITHUB_ENV, cleanup — always по точному ID с anonymous volumes.
  runner.temp перенесён на уровень шага.
- Actionlint и bash -n прошли. Helper реально создал отдельную Mongo, дождался ping=1,
  экспортировал loopback random-port URL и точный ID; этот контейнер использован для R8 acceptance.
  Hosted workflow после правок не запускался: изменения пока не опубликованы.
  Локальный запуск не доказывает результат на том же ядре hosted runner.

### Данные и приёмка

Свежая последовательная read-only копия тех же шести коллекций:
kvn 152, seasons 122, tournaments 5, teams 1310, people 1041, participations 9276.
Цель: отдельная `humorpedia_r8_copy_20261021b`; общие volumes и БД не использовались.
SHA-256 source/target потока совпал:
`18a1f8515312887e34e1067ef84893cf47dfaf58e632d0a42637c6bb5177df18`.

Выполнены два полных rebuild по 122 сезонам. Канонические содержимое/created_at/updated_at
не менялись; исключались только корневые технические поля _projection/_write_claim.
SHA-256 до/после:
`7977182de7e66932b32a8c97decea754d44bfaa850aa5045d1c3b34a6992383b`.
После второго прохода 9276 строк participations, их hash совпал с первым проходом;
tournaments/teams/people не изменились, незавершённых claims нет.
Окончательная read-only сверка без truncation: 122 equal_projection, 0 projection/metadata diff,
406 прежних round-trip различий — только missing stage.comment / пустая строка.

При проверке найден дефект самого отчёта: TeamLookup включал команды других шоу
с одинаковым slug. Ограничение show_id missing/null приведено к производственному loader;
ложные 195 team_id round-trip различий исчезли. Данные не исправлялись.

Проверки конечного кода:
- Backend: **1058 passed / 15 skipped**, 4 существующих предупреждения;
  PAGE_PACKAGE_INTEGRATION, SEASON_WRITE_INTEGRATION, READINESS_INTEGRATION включены.
  Интеграция импорта источников не включалась.
- Frontend: **266 passed / 47 suites**; строгая CI production build успешна.
- Реальная Mongo/API: stale/missing/null версии, оба API и два токена, конкурирующие writers,
  metadata-only без reverse overwrite, postcommit failure + exact retry, повтор без дублей.
- Настоящий SIGKILL тестового Uvicorn после canonical commit и первого participation upsert:
  exit 137; после рестарта retry 409; все probe workers остановлены; exact-token CLI recovery;
  два повтора 200, canonical version прежняя. Это отдельная fixture-БД, не основной стенд.
- Browser smoke реальным Chrome: login/builder/preview/ZIP/apply/search/back плюс новый
  seasons.cjs: create, canonical UI edit, ID/person refs, reorder/role API, stale 409,
  публичный комментарий. Transport не подменялся.
- AST backend, actionlint, bash -n, node --check, module-contract check прошли.

Импорт 24СМИ и его файлы не изменялись, VPS не подключался и не обновлялся.
Commit/push не выполнялись: remote ref по-прежнему R7 `85ba090`.
Основной checkout и контейнеры проверяются перед завершением; текущие изменения находятся только в worktree.

Финальная сверка: main чистый на ca46155; ID/StartedAt/restart count трёх основных контейнеров неизменны. HTTP 3000 и /api/health — 200. Одноразовые browser/crash workers, Mongo с копией, две anonymous volumes и сеть удалены. Коммиты и remote ref не изменились.

## Подготовка публикации

По поручению пользователя CI оформлен отдельным коммитом 5d369dd; [диагностика CI](ci-workflow-recovery-2026-10-21.md). R8 и документация оформляются следующим отдельным коммитом. Перед ним повторно пройдены 1058 backend / 15 skipped, 266 frontend / 47 suites и CI production build. Проверка hosted CI на опубликованном SHA выполняется перед началом реализации R9; окончательные SHA и run будут сохранены в задаче R9. Основной checkout остаётся на main; импорт источников и VPS не меняются.

## Публикация и hosted CI

21.10.2026: R8 и документация опубликованы отдельным коммитом b67aacb73da477863ea1a739068ef4308d41ad63 после CI-коммита 5d369dd. Remote codex/local-page-builder подтверждён на том же SHA. [GitHub Actions](https://github.com/AMnEPka/humorpedia/actions/runs/39611516778) — success: backend, frontend, Mongo integration, Windows tools и browser smoke. Последующее состояние R9 ведётся [отдельно](r9-public-rendering-2026-10-21.md); сведения о неопубликованном R8 выше — исторические контрольные точки.
