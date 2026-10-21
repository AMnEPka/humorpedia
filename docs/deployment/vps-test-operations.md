# Тестовый VPS: доступ и обслуживание

Проверено 04.10.2026. `77.105.139.231`: Ubuntu 26.04, 1 vCPU, 956 МБ RAM, диск 10 ГБ + swap 1 ГБ. Это отдельная копия Humorpedia из commit `1813cf02f08c`, не production. Старый сайт, DNS и почта не изменены. Автозапуск после reboot проверен. CI/CD пока не настроен.

## Открыть сайт

Публичный стенд открыт по доверенному HTTPS, без дополнительного общего пароля:

- Сайт: https://77.105.139.231/
- Админка: https://77.105.139.231/admin/login — требует учётную запись приложения.

Эти ссылки можно отправить тестировщикам. SSH-туннель им не нужен. Стенд доступен всем, кто узнает адрес; HTTPS шифрует соединение, но не ограничивает аудиторию. База MongoDB и backend не имеют опубликованных портов; Docker-web остаётся на `127.0.0.1:8080`. HTTP перенаправляет на HTTPS, кроме служебного ACME endpoint. Локальный dev-сайт на портах 3000/8001 работает независимо.

Не передавайте всем пароль администратора: он даёт широкие права в копии данных. Для просмотра сайта вход не нужен. Отдельные роли тестировщиков на этом этапе не создавались.

Для диагностики по-прежнему доступен SSH-туннель. В Windows PowerShell выполните и оставьте окно открытым:

```powershell
ssh -p 22 -o IdentitiesOnly=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -i "$env:USERPROFILE\.ssh\humorpedia_vps" -N -L 127.0.0.1:8080:127.0.0.1:8080 deploy@77.105.139.231
```

Отсутствие вывода нормально: это туннель. Если порт 8080 уже занят запущенным туннелем, второй не запускайте.

- Сайт: http://localhost:8080/
- Админка: http://localhost:8080/admin/login

HTTP на localhost проходит внутри зашифрованного SSH.

Администратор VPS: `vps-test@humorpedia.invalid`. Пароль сгенерирован отдельно, исходного пользователя не меняли. Получить пароль у себя в PowerShell:

```powershell
ssh -p 22 -o IdentitiesOnly=yes -i "$env:USERPROFILE\.ssh\humorpedia_vps" deploy@77.105.139.231 "grep '^ADMIN_PASSWORD=' /home/deploy/humorpedia-test/.env"
```

Пароль — часть строки после `=`. Не отправляйте её в чат. Закрытая копия: `backups/vps-test-2026-10-04/credentials.env` на Windows. Сохраните её и SSH-ключ в защищённом хранилище. Это не рабочий почтовый адрес; отправка почты на стенде не настроена.

## Состояние и логи

Подключение обычной SSH-сессией:

```powershell
ssh -p 22 -o IdentitiesOnly=yes -i "$env:USERPROFILE\.ssh\humorpedia_vps" deploy@77.105.139.231
```

На VPS:

```bash
cd /home/deploy/humorpedia-test
sudo docker compose ps
curl -fsS http://127.0.0.1:8080/api/health
sudo docker compose logs --tail=60 backend
sudo docker stats --no-stream
free -h
df -h /
```

`sudo` теперь требует пароль deploy; временный NOPASSWD отключён. SSH — только ключом. Docker стартует при boot; контейнеры имеют restart unless-stopped. После ручного `compose stop` запускайте `sudo docker compose up -d --wait`: остановленные вручную контейнеры не обязаны подняться после reboot.

## HTTPS и продление

Host nginx обслуживает TLS и проксирует в Docker через loopback. Сертификат Let's Encrypt выдан именно на IPv4 `77.105.139.231`, без домена; первоначально действует до 11.10.2026 01:01:54 MSK. Профиль `shortlived` даёт около 160 часов, поэтому продление обязательно. Certbot 5.8.0 установлен отдельно в `/opt/humorpedia-certbot`, а не старый системный пакет.

`humorpedia-certbot.timer` проверяет необходимость продления дважды в сутки, со случайным сдвигом до часа. При успешном продлении deploy-hook проверяет nginx и перезагружает конфигурацию без остановки сайта. Certbot зарегистрирован без email: письма об ошибках не придут. Отдельные мониторинг и уведомления пока не настроены.

Проверка на VPS:

```bash
sudo systemctl list-timers humorpedia-certbot.timer --no-pager
sudo journalctl -u humorpedia-certbot.service -n 30 --no-pager
sudo /opt/humorpedia-certbot/bin/certbot certificates
sudo /opt/humorpedia-certbot/bin/certbot renew --cert-name humorpedia-vps-ip --dry-run --run-deploy-hooks --no-random-sleep-on-renew
curl -fsS https://77.105.139.231/api/health
```

Не запускайте несколько экземпляров Certbot одновременно. Порт 80 нужен для проверки владения IP при продлении; закрывать его нельзя. Ключи и конфиги сертификата хранятся в `/etc/letsencrypt`; они секретные. Изменение IP требует нового сертификата и конфигов.

На login действует лимит 5 запросов/минуту на IP с коротким burst; превышение даёт 429, нужно подождать. Общий API ограничен 10 запросами/секунду на IP с burst 40. Это смягчает простой перебор, но не заменяет защиту от распределённых атак. `robots.txt` и `X-Robots-Tag` просят не индексировать стенд, но не являются контролем доступа. Просмотр потенциально увеличивает счётчики посещений в копии данных.

## Резервные копии

На Windows сохранены исключённые из Git файлы в `backups/vps-test-2026-10-04/`: исходный дамп, архив медиа, manifest, новый дамп после запуска и credentials. Папка закрыта Windows ACL от других обычных пользователей. Скопируйте её в своё долговременное защищённое хранилище: это пока одна машина, не автоматическое внешнее резервирование.

Новый дамп на VPS (интерактивная SSH-сессия):

```bash
cd /home/deploy/humorpedia-test
sudo -v
umask 077
backup_name="backups/db-$(date +%Y%m%d-%H%M%S).archive.gz"
sudo docker compose exec -T mongodb bash -lc 'exec mongodump --host localhost --username root --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db humorpedia --numParallelCollections=1 --archive --gzip' > "$backup_name"
test -s "$backup_name" && sha256sum "$backup_name"
```

Скачайте конкретный файл через `scp` в закрытую папку Windows. У дампа нет `--oplog`: для согласованной копии при активных изменениях сначала сделайте `sudo docker compose stop backend`, затем дамп и копию изменившихся медиа, и обязательно `sudo docker compose start backend`. MongoDB останавливать не нужно. Если медиа не менялись, исходный архив размером 1 ГБ уже есть вне сервера; не плодите дубликаты на VPS.

При восстановлении нужны вместе БД, media/uploads и `.env` с Mongo-паролями. Не запускать `restore-data.sh` повторно поверх непустой БД. Первоначальный импорт выполнен; новое восстановление планировать в отдельную чистую цель. Полный повторный restore нового backup пока не тестировался; исходный dump восстановлен и сверён.

## Обновление и ограничения

VPS использует `scripts/vps-test/compose.yml`, не локальный dev-Compose. Образы собирать на Windows из выбранного коммита и переносить после резервного копирования и проверки места. Не собирать React/Python на VPS и не переносить Windows `.env` или dev-volumes. Локальная и VPS-БД автоматически не синхронизируются.

Свободно примерно 1,4 ГБ: перед обновлением проверяйте `df -h /`. Большой архив образов может не поместиться. Старые данные/образы не удалять без определения точных целей; не использовать `docker system prune --volumes`. Успешный запуск на 1 ГБ не гарантирует достаточности для 5–10 тыс. посетителей/сутки — нужны отдельные измерения. Тяжёлый CI-runner на этот VPS не устанавливался.

Mongo 8.0.32 использует `seccomp-mongodb.json` с запретом rseq: иначе на исходном Linux 7.0.0-14 срабатывала проверка совместимости при старте. Runtime подтвердил запасной режим allocator без per-CPU cache; socketcall тоже запрещён. Профиль не отключает остальные ограничения seccomp. Обновление Mongo или снятие профиля требуют отдельной проверки и резервной копии; не меняйте версию БД простым pull.

Домен, почта/OAuth, регулярное внешнее резервирование, CI/CD и нагрузочные испытания — отдельные задачи. Независимый внешний portscan и полный UI-login не подтверждены; серверные привязки портов/firewall, публичный HTTPS и вход администратора через API проверены. Подробные результаты — [статус развёртывания](../ai/tasks/vps-test-deployment.md).
