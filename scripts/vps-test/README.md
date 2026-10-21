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
