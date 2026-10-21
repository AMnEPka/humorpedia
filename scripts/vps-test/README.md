# Малый тестовый VPS

Конфиги реально развёрнутого тестовогоVPS: [эксплуатация](../../docs/deployment/vps-test-operations.md), [проверки](../../docs/ai/tasks/vps-test-deployment.md).

Не запускать `provision.sh`, `harden.sh`, `init-secrets.sh` и `restore-data.sh` повторно на текущем стенде. Они предназначены для первоначальной подготовки пустой цели; сервер уже настроен и содержит данные. `export-local.mjs` кратко останавливает локальные frontend/backend: повторное выполнение требует согласованного окна остановки.

## Публичный HTTPS на IP

Пользователь выбрал доступ без дополнительного общего пароля. Host nginx слушает 80 (ACME/redirect) и IPv4 443 (HTTPS), проксирует в Docker на `127.0.0.1:8080`; backend/Mongo не опубликованы. `https-prepare.sh`, `https-issue.sh staging|production` и `https-enable.sh` уже применены: не запускать первоначальную настройку повторно без проверки текущего состояния.

Certbot 5.8.0 из официального PyPI находится в отдельном venv. Используется доверенный Let's Encrypt IP-сертификат с `shortlived` и webroot; продление — systemd timer и nginx deploy-hook. Staging имеет отдельные каталоги и не подставляется в публичный nginx. Инструкции проверки — в эксплуатационном документе выше.

Для переданных shell-скриптов перед запуском нормализовать CRLF в LF. Конфиги Compose/nginx сохраняют переносы без изменения поведения. Docker nginx доверяет клиентскому IP и HTTPS-заголовку только от существующего bridge gateway `172.18.0.1`; если сеть удалена/создана заново, проверить gateway и обновить конфиг. Host nginx всегда перезаписывает входные forwarding headers. Backend доверяет внутреннему proxy, но не доступен напрямую с хоста/Интернета.

## Seccomp: источник и изменения

`seccomp-mongodb.json` взят из [moby/profiles/seccomp/default.json](https://github.com/moby/profiles/blob/main/seccomp/default.json) 04.10.2026, Apache License 2.0 ([копия лицензии](LICENSE-MOBY)). Изменён: из allow-list удалены `rseq` и `socketcall`. Default остаётся SCMP_ACT_ERRNO/EPERM; остальные правила сохранены. Это не отключение seccomp.

Запретrseq включает предусмотренный allocatorfallback Mongo8.0.32 и устраняет наблюдавшийся startupfatal на Linux7.0.0-14 ([SERVER-121912](https://jira.mongodb.org/browse/SERVER-121912)). Запретsocketcall дополнительно исключает legacy32bitmultiplexer; используемый image —amd64. После изменения проверены запуск/restore/uptime и `serverStatus().tcmalloc.usingPerCPUCaches=false`.

Не удалять профиль и не использовать `seccomp=unconfined`. Будущее обновление БД/ядра проверять отдельно. Healthcheckfrontend явно используетIPv4loopback, а не потенциальныйIPv6localhost.

## R5: подготовка следующего выпуска

21.10.2026 в ветке `codex/local-page-builder` подготовлены private bind `data/page-packages`, readiness backend, 52 MiB на точном ZIP preview в обоих nginx и backup/restore private-файлов с SHA-256. **На VPS эти изменения ещё не применены.** API ZIP остаётся 50 MiB, остальные proxy-маршруты — 20 MiB. Существующий dev-стенд на main этим пакетом не переключается и не перезапускается.

При первоначальной передаче файлов положить `restore_files.py` **рядом с `restore-data.sh`**. Вызов helper определяется относительно shell-скрипта и работает при плоской раскладке серверного каталога. Нужен Python 3 на host; `provision.sh` устанавливает его. Private-каталог — 0700, архивы и восстановленные файлы — 0600. Не добавлять nginx alias к `page-packages`.

`export-local.mjs DESTINATION` рассчитан на локальный стек выпуска с `/app/private/page-packages` и заранее созданную закрытую папку назначения, содержащую `humorpedia-vps-` в имени. Он останавливает frontend/backend, сохраняет Mongo, media/uploads и private tree, вычисляет private manifest, возобновляет контейнеры и создаёт `media.tar.gz`. На текущем main без нового storage этот exporter не запускать. Для backup нужны остановленные writers, внешние SHA-256 обоих архивов и защищённая копия `.env`; см. [эксплуатационный контракт](../../docs/deployment/vps-test-operations.md#подготовка-r5-zip-постоянные-файлы-и-готовность). Внешние SHA-256 передаются аргументами `restore-data.sh`. Это первоначальный restore в пустую цель, без merge/overwrite.

Проверки файлов и прокси:

```powershell
node --test scripts/vps-test/test_export_local.mjs
python -m unittest discover -s scripts/vps-test -p test_restore_files.py
python scripts/vps-test/test_proxy_limits.py --backend-image humorpedia-backend
```

Node-тест подставляет Docker/process boundaries и проверяет private SHA-256 manifest, состав архива и возобновление writers при ошибке/SIGINT/SIGTERM; реальный экспорт и native process exit он не выполняет. Python unittest использует временные файлы и проверяет private manifest, SHA-256, небезопасные TAR-пути/типы, запрет overwrite и старый архив. Linux-прогон проверяет также symlink. Proxy-тест требует локальные Docker images `humorpedia-backend` и `nginx:1.28-alpine`; создаёт свои временные ресурсы, случайные loopback-порты и тестовый TLS-сертификат. Проверяет оба nginx и HTTP-лимиты на синтетическом upstream без обращения к main/VPS. Успех этой проверки не означает, что backend примет содержимое произвольного ZIP.

Проверка readiness и восстановления с настоящей MongoDB:

```bash
cd backend
READINESS_INTEGRATION=1 MONGO_URL=mongodb://127.0.0.1:27017 \
  pytest -q tests/test_readiness.py tests/test_readiness_integration.py
```

MongoDB должна быть **отдельной тестовой**. Тест создаёт случайную `humorpedia_r5_test_<uuid>` БД и свои временные uploads/private-каталоги; только эту БД он удаляет после проверки. Нужны `mongodump`/`mongorestore` в PATH либо `MONGO_TOOLS_CONTAINER` с Mongo tools и доступом к тому же URI. GitHub Actions использует свой Mongo service. Проверяется новый lifespan приложения, отсутствующий unique index, отказ private storage, импорт с фото и реальный restore dump+файлов с SHA-256 и декодированием PNG. Readiness unit-тесты отдельно проверяют отказ/таймаут Mongo и недопустимые пути. Результаты и границы — в [отчёте](../../docs/ai/tasks/initial-refactoring-fixes-2026-10-21.md).

Прерывание локального exporter через SIGINT/SIGTERM вызывает попытку запустить исходные backend/frontend. При принудительном завершении процесса, сбое Docker или выключении машины это не гарантируется: проверить `docker ps` и при необходимости выполнить `docker start humorpedia-backend humorpedia-frontend`. Незавершённый backup не использовать; повторять экспорт в новую закрытую папку. В R5 настоящий exporter на main не запускался.
