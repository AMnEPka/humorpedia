# Browser smoke

`run.cjs` выполняет три сценария настоящим Chromium без моков API:

1. Вход → новая заготовка человека → редактура → preview внутри iframe → скачивание ZIP.
2. Загрузка ZIP → preflight без публикации → явный apply → обычный редактор → сохранение → публичный preview.
3. Анонимный поиск → карточка → browser back с восстановлением результатов.

Технический тест не запускает Codex worker и не генерирует материалы. Все имена/страницы синтетические.
Проверяется browser file input, без автоматизации системного диалога выбора файла.

`server.py` подключает настоящее `backend/server.py` и production frontend на одном origin.
Он требует уникальный `SMOKE_RUN_ID` (32 hex) и точный `DB_NAME=humorpedia_browser_test_<run_id>`,
отказывается работать с непустой БД, создаёт marker владения и удаляет только свою БД после остановки writers.
Uploads/private storage изолированы в `TemporaryDirectory`. Тестовая учётная запись создаётся только там.

## Windows с существующим local-first Docker

Нужны production build того же HEAD, Node, Playwright **1.62.1** и Chromium либо установленный Chrome/Edge.
Зависимости самого приложения не меняются. Если Playwright отсутствует, установить отдельно:

```powershell
$browserTools = Join-Path $env:TEMP 'humorpedia-browser-tools'
npm install --prefix $browserTools --no-save playwright@1.62.1
# При использовании системного Chrome этот шаг не нужен:
& (Join-Path $browserTools 'node_modules/.bin/playwright.cmd') install chromium
powershell -ExecutionPolicy Bypass -File scripts/browser-smoke/local.ps1 `
  -BuildDirectory C:/path/to/production-build `
  -PlaywrightModules (Join-Path $browserTools 'node_modules')
```

Для установленного браузера добавить `-ChromiumChannel chrome` или `msedge`.
Можно указать уже доступный каталог пакетов через `-PlaywrightModules` без установки.

`local.ps1` экспортирует **HEAD** приложения, копирует текущий smoke harness, запускает один временный backend
из образа существующего контейнера на том же Mongo network, но с новой БД. Основной стек не переключается
и не перезапускается; source/build mounts read-only, порт только `127.0.0.1:18001` (`-Port` меняет его).
Учётные данные Mongo передаются через временный env-file без вывода; файл удаляется в `finally`.
Контейнер останавливается в `finally`; scratch с исходниками, ZIP и screenshot остаётся в системном temp
для диагностики. При принудительном завершении процесса очистка не гарантирована — остатки нельзя удалять
массово по одному префиксу без проверки владения.

## CI / Linux

Job `browser-smoke` получает artifact frontend из того же workflow. Сборка использует
`REACT_APP_USE_API_PROXY=true`, поэтому все `/api` и uploads идут на изолированный сервер.
Mongo service принадлежит job. Playwright устанавливается отдельно в `$RUNNER_TEMP/browser-tools`;
версии frontend/backend dependencies остаются прежними.

Для ручного запуска на Linux задать `MONGO_URL`, уникальные `SMOKE_RUN_ID`/`DB_NAME`, `BROWSER_BUILD_DIR`,
`NODE_PATH` к каталогу с Playwright; запустить `python scripts/browser-smoke/server.py`, затем
`node scripts/browser-smoke/run.cjs`. Сервер по умолчанию слушает `127.0.0.1:18001`.
В конце отправить серверу SIGTERM и дождаться завершения для очистки БД. Screenshot и ZIP сохраняются
в `SMOKE_ARTIFACT_DIR` либо в новом temp-каталоге; CI также сохраняет журнал сервера.
