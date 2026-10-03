# Восстановление MongoDB

## Перед восстановлением

Определите формат копии и целевую версию MongoDB. Архив `humorpedia_backup_*.tar.gz` создаёт `backup/backup.sh`; прямой `mongodump --archive --gzip` создаёт иной формат `.archive.gz`. Не подменяйте бинарник MongoDB старой версией поверх уже обновлённого тома. Для точного отката обновления восстановите **холодный снимок старого тома в отдельный том** и запустите на нём исходную версию MongoDB.

Остановите frontend, backend и другие источники записи. Сохраните текущий том/архив отдельно, даже если собираетесь его заменить. Сначала проверьте выбранную копию восстановлением в изолированном окружении и сравнением коллекций, документов и индексов.

## Cloud-шаблон: архив backup-сервиса

Если cloud-шаблон будет запущен, его образ backend не содержит `mongorestore`. Для `humorpedia_backup_*.tar.gz` используйте команду из образа `backup`, который имеет доступ к `backups_data` и учётным данным MongoDB:

```bash
docker compose -f docker-compose-cloud.yml stop frontend backend backup
docker compose -f docker-compose-cloud.yml run --rm --no-deps \
  --entrypoint /backup/restore.sh backup \
  humorpedia_backup_YYYYMMDD_HHMMSS.tar.gz --force
docker compose -f docker-compose-cloud.yml start backend frontend backup
```

Подставьте фактическое имя **проверенного** архива. `--force` обязателен, чтобы запись нельзя было запустить случайно. Скрипт распаковывает архив и вызывает `mongorestore --drop`: коллекции, присутствующие в архиве, заменяются; **другие коллекции остаются**. Для точного возврата всей БД используйте новый пустой том или холодный снимок, а не восстановление поверх существующей БД. После запуска проверьте FCV, авторизованное подключение, число документов и ключевые API.

## Локальный Compose: архив штатного формата

Локальный backend содержит MongoDB tools. После остановки приложения можно запустить скрипт с учётными данными из Compose, минуя его обычный startup:

```powershell
docker compose stop frontend backend
docker compose run --rm --no-deps --entrypoint python backend `
  scripts/restore_specific_backup.py имя_файла.tar.gz --force
docker compose start backend frontend
```

Файл должен лежать в `backups/`. Скрипт читает `MONGO_HOST`/`MONGO_PORT`/`MONGO_USER`/`MONGO_PASSWORD`/`MONGO_AUTH_SOURCE` либо явный `MONGO_URL`; пароль в журнал не выводит. Он принимает архив `*.tar.gz`, созданный `backup/backup.sh`, и не принимает прямой `.archive.gz` от `mongodump --archive`.

## Проверка результата

```bash
docker compose ps
```

Проверьте авторизованный `ping` с учётными данными из окружения контейнера; один только статус `healthy` не подтверждает доступ приложения. Затем проверьте `/api/health` и основные операции чтения и записи через backend.
