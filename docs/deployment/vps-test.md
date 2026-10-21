# Развёртывание Humorpedia на тестовом VPS

Это первоначальная инструкция для предполагаемого VPS с Ubuntu22.04,1vCPU,1ГБ RAM и диском20ГБ. **Фактический VPS уже развёрнут04.10.2026; на нём Ubuntu26.04 и диск10ГБ. Для текущего сервера используйте [инструкцию эксплуатации](vps-test-operations.md), не выполняйте повторно первоначальную настройку и импорт ниже.** Проверенная конфигурация находится в `scripts/vps-test/`, включая обязательный для текущей связки ядра/MongoDB seccomp-профиль.

Это пробный стенд, не подтверждение достаточности ресурсов для production. Запуск, восстановление данных и автозапуск после reboot проверены; нагрузочные испытания не выполнены. Нижние блоки — исторический вариант для Ubuntu22.04, а не команды обслуживания текущего Ubuntu26.04.

Каждый блок выполняйте в указанном месте. При ошибке не продолжайте следующий зависимый шаг. Не присылайте пароли, приватный SSH-ключ или `.env` в чат. Для первой загрузки не используйте обычный `docker-compose.yml`: это тяжёлый dev-стек.

## 1 Подготовьте доступ и проверьте сервер

Нужны IP VPS, первоначальный SSH-доступ от хостера и доступ к веб-консоли хостера на случай ошибки настройки SSH. Далее предполагается SSH на порту 22 и первоначальный пользователь root. Если хостер выдал другого пользователя или порт, замените их в командах; firewall должен разрешать фактический SSH-порт.

**Windows, PowerShell:** создайте отдельный ключ с парольной фразой. Если файл с таким именем уже существует, используйте его, не перезаписывайте.

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.ssh" | Out-Null
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\humorpedia_vps" -C "humorpedia-vps-test"
Get-Content "$env:USERPROFILE\.ssh\humorpedia_vps.pub"
ssh root@IP_VPS
```

При первом подключении сравните отпечаток сервера с данными хостера или его веб-консоли. Скопируйте строку публичного ключа, начинающуюся с `ssh-ed25519`.

**VPS, первоначальная SSH-сессия:**

```bash
uname -m
grep -m1 -w avx /proc/cpuinfo
free -h
df -h /
swapon --show
sshd -T | grep '^port '
```

Продолжайте этот вариант инструкции при архитектуре `x86_64` и наличии `avx`. Современной MongoDB на x86 требуется поддерживаемый CPU; если флаг отсутствует, уточните у хостера возможность включить подходящую модель виртуального CPU. Не пытайтесь решить это установкой устаревшей MongoDB. [Требования MongoDB](https://www.mongodb.com/docs/manual/administration/production-notes/).

Если диск уже существенно занят, сначала выясните причину. ОС, распакованные Docker-образы, база, медиа и временные архивы должны помещаться с запасом; число 20 ГБ само по себе этого не гарантирует.

Создайте пользователя:

```bash
adduser deploy
usermod -aG sudo deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
nano /home/deploy/.ssh/authorized_keys
```

Вставьте публичный ключ одной строкой, сохраните файл через Ctrl+O, Enter, выйдите через Ctrl+X.

```bash
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
```

**Windows, второе окно PowerShell:**

```powershell
ssh -i "$env:USERPROFILE\.ssh\humorpedia_vps" deploy@IP_VPS
```

В этой новой сессии выполните `sudo -v`: должен приниматься пароль пользователя deploy. Пока это не работает, не отключайте первоначальный вход.

## 2 Защитите SSH и включите firewall

**VPS, сессия deploy:**

```bash
sudo nano /etc/ssh/sshd_config.d/00-humorpedia.conf
```

Содержимое:

```text
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
```

Проверьте конфигурацию и примените её:

```bash
sudo sshd -t
sudo sshd -T | grep -E '^(pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication|permitrootlogin|port) '
sudo systemctl reload ssh
```

Ожидается `pubkeyauthentication yes`, остальные три параметра — `no`. Оставьте старые SSH-сессии открытыми и ещё раз проверьте новое подключение deploy по ключу. Это защищает от случайной потери доступа. [Настройка OpenSSH в Ubuntu](https://ubuntu.com/server/docs/how-to/security/openssh-server/).

```bash
sudo apt-get update
sudo apt-get install -y ufw ca-certificates curl openssl
sudo apt-get upgrade -y
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw enable
sudo ufw status verbose
```

Не открывайте 80, 443, 8080, 8001 или 27017. При нестандартном SSH-порте замените 22 до включения firewall. В сетевом firewall панели хостера также можно оставить только SSH; при постоянном IP разрешить его только со своего адреса. Учтите IPv6, если он назначен VPS.

Если обновления требуют перезагрузки (`test -f /var/run/reboot-required`), перезагрузите VPS и проверьте вход deploy по ключу. Настройки SSH уже должны быть проверены.

## 3 Добавьте swap и установите Docker

**VPS:** если `swapon --show` не показывает swap и файла `/swapfile` нет, создайте его:

```bash
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
sudo nano /etc/fstab
```

Добавьте одну строку, не меняя существующие:

```text
/swapfile none swap sw 0 0
```

```bash
free -h
swapon --show
```

Не повторяйте создание существующего swap-файла. Swap — страховка; постоянное активное использование swap означает, что памяти недостаточно.

Установите Docker из официального репозитория. Команды ниже предназначены для Ubuntu 22.04 (`jammy`) на `amd64`, при отсутствии ранее установленного Docker. Если Docker уже установлен, сначала проверьте его версию и источник, не устанавливайте второй комплект поверх него.

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo nano /etc/apt/sources.list.d/docker.sources
```

Содержимое:

```text
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: jammy
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
```

```bash
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
sudo docker run --rm hello-world
```

Команды Docker на VPS далее выполняются через `sudo`; добавлять deploy в группу docker не требуется. [Официальная установка Docker](https://docs.docker.com/engine/install/ubuntu/).

## 4 Соберите образы на Windows

Включите Docker Desktop в режиме Linux containers. Все команды этого раздела и последующей отправки выполняйте в одном окне PowerShell, чтобы сохранить переменные `$releaseDir` и `$releaseId`.

Сборка ниже использует только выбранный Git-коммит. Незакоммиченные и staged-изменения не попадут в образы; данные отдельно будут взяты из действующего локального стенда. Перед экспортом проверьте, что версии кода и данных совместимы. Эти команды не коммитят и не сбрасывают изменения рабочей папки.

```powershell
Set-Location 'C:\Users\rdp6126443.gmail.com\humorpedia'
git status --short --branch
$releaseRef = 'HEAD'
$releaseId = (git rev-parse --short=12 $releaseRef).Trim()
$releaseDir = Join-Path $env:TEMP ('humorpedia-vps-' + $releaseId + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $releaseDir | Out-Null
git archive --format=zip --output="$releaseDir\source.zip" $releaseRef
Expand-Archive -LiteralPath "$releaseDir\source.zip" -DestinationPath "$releaseDir\source"
```

Вместо `HEAD` можно заранее указать конкретный проверенный коммит в `$releaseRef`. Переключать рабочую ветку не требуется.

```powershell
docker build --platform linux/amd64 -f "$releaseDir\source\backend\Dockerfile-cloud" -t "humorpedia/backend:$releaseId" "$releaseDir\source\backend"
docker build --platform linux/amd64 -f "$releaseDir\source\frontend\Dockerfile-cloud" --build-arg REACT_APP_BACKEND_URL=http://localhost:8080 -t "humorpedia/frontend:$releaseId" "$releaseDir\source\frontend"
docker pull --platform linux/amd64 mongo:8.0.32
docker save -o "$releaseDir\images.tar" "humorpedia/backend:$releaseId" "humorpedia/frontend:$releaseId" mongo:8.0.32
tar -czf "$releaseDir\images.tar.gz" -C "$releaseDir" images.tar
$releaseId
$releaseDir
```

Запишите выведенный `$releaseId`: он понадобится в `.env` сервера. Тяжёлая сборка происходит на Windows, на VPS передаются готовые образы. Каждый следующий блок выполняйте только после успешного завершения предыдущей команды; PowerShell сам по себе не останавливается при ошибке внешней программы.

На локальном диске потребуется место для исходников, экспортированных образов и архивов. Папка создаётся вне репозитория; её содержимое, особенно копию БД, не добавляйте в Git.

## 5 Экспортируйте базу и изображения

**Windows, тот же PowerShell:** этот шаг ненадолго остановит локальные frontend/backend, чтобы получить согласованную копию. Закончите редактирование контента и остановите другие скрипты, пишущие в локальную БД. MongoDB продолжит работать.

```powershell
docker compose ps
New-Item -ItemType Directory -Path "$releaseDir\media\imported-images", "$releaseDir\media\images", "$releaseDir\media\uploads" | Out-Null
docker compose stop frontend backend
docker compose exec mongodb bash
```

Последняя команда откроет bash **внутри локального контейнера MongoDB**. Выполните там:

```bash
mongodump --host localhost --port 27017 \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --db humorpedia --archive=/tmp/humorpedia-test.archive.gz --gzip
exit
```

Должен завершиться успешный экспорт, без ошибок авторизации. Это логическая копия базы `humorpedia`; учётная запись root из базы `admin` на новый сервер не переносится.

**Снова Windows, PowerShell:**

```powershell
docker cp humorpedia-mongodb:/tmp/humorpedia-test.archive.gz "$releaseDir\humorpedia-test.archive.gz"
docker cp humorpedia-backend:/app/media/imported/images/. "$releaseDir\media\imported-images"
docker cp humorpedia-backend:/app/images/. "$releaseDir\media\images"
docker cp humorpedia-backend:/app/uploads/. "$releaseDir\media\uploads"
docker compose start backend frontend
tar -czf "$releaseDir\media.tar.gz" -C "$releaseDir\media" imported-images images uploads
Get-Item "$releaseDir\images.tar.gz", "$releaseDir\humorpedia-test.archive.gz", "$releaseDir\media.tar.gz" | Select-Object Name, Length
```

`docker cp` работает и с остановленным контейнером. Указанные имена сверены с локальным Compose; если они изменены, возьмите фактические имена из `docker compose ps -a`. Не оставляйте локальный сайт остановленным при ошибке экспорта: после разбирательства выполните `docker compose start backend frontend`.

Проверьте локальный сайт после запуска. Копия медиа взята из реально смонтированных каталогов контейнера, а не только из папки исходников.

## 6 Подготовьте каталог на VPS и отправьте архивы

**VPS, пользователь deploy:**

```bash
mkdir -p ~/humorpedia-test/incoming
chmod 700 ~/humorpedia-test
chmod 755 ~/humorpedia-test/incoming
cd ~/humorpedia-test
mkdir -p data/mongo data/uploads data/imported-images data/images
```

**Windows, PowerShell с сохранённой переменной `$releaseDir`:**

```powershell
scp -i "$env:USERPROFILE\.ssh\humorpedia_vps" "$releaseDir\images.tar.gz" "$releaseDir\humorpedia-test.archive.gz" "$releaseDir\media.tar.gz" deploy@IP_VPS:/home/deploy/humorpedia-test/incoming/
Get-FileHash "$releaseDir\images.tar.gz", "$releaseDir\humorpedia-test.archive.gz", "$releaseDir\media.tar.gz" -Algorithm SHA256
```

**VPS:**

```bash
cd ~/humorpedia-test
sha256sum incoming/images.tar.gz incoming/humorpedia-test.archive.gz incoming/media.tar.gz
df -h /
set -o pipefail
tar -xOzf incoming/images.tar.gz images.tar | sudo docker load
tar -tzf incoming/media.tar.gz | head
tar -xzf incoming/media.tar.gz -C data
chmod 644 incoming/humorpedia-test.archive.gz
```

Сравните хеши с Windows. Архив образов содержит один вложенный `images.tar`; он поступает в Docker потоком, без создания второй распакованной копии файла на VPS. Архив медиа должен содержать только `imported-images`, `images`, `uploads` и файлы внутри них. Извлекайте его в новый каталог тестового стенда.

После загрузки образов и медиа повторите `df -h /`. Желательно оставить несколько ГБ свободными. Архив образов и медиа можно удалить с VPS после проверки переноса, сохранив исходные копии на Windows; не удаляйте каталоги `data`.

## 7 Создайте настройки закрытого стенда

**VPS, каталог `~/humorpedia-test`:** создайте пять файлов через `nano`: `.env`, `mongo-init.js`, `config.js`, `nginx.conf`, `compose.yml`.

Для секретов выполните `openssl rand -hex 32` отдельно четыре раза. Первые три результата используйте для root MongoDB, пользователя приложения и JWT; четвёртый — как пароль тестового администратора. Сохраните их в менеджере паролей.

### Файл .env

```dotenv
RELEASE_ID=ВСТАВЬТЕ_RELEASE_ID_ИЗ_WINDOWS
MONGO_ROOT_PASSWORD=ВСТАВЬТЕ_ПЕРВЫЙ_СЛУЧАЙНЫЙ_СЕКРЕТ
MONGO_APP_PASSWORD=ВСТАВЬТЕ_ВТОРОЙ_СЛУЧАЙНЫЙ_СЕКРЕТ
JWT_SECRET=ВСТАВЬТЕ_ТРЕТИЙ_СЛУЧАЙНЫЙ_СЕКРЕТ
ADMIN_EMAIL=vps-test@humorpedia.invalid
ADMIN_USERNAME=vps_test_admin
ADMIN_PASSWORD=ВСТАВЬТЕ_ЧЕТВЁРТЫЙ_СЛУЧАЙНЫЙ_СЕКРЕТ
```

```bash
chmod 600 .env
```

Не переносите локальный `.env` на сервер. Смена значения `MONGO_ROOT_PASSWORD` после первой инициализации сама по себе не меняет пароль уже созданного пользователя MongoDB.

### Файл mongo-init.js

Этот файл создаёт отдельного пользователя приложения при первом запуске пустой MongoDB. Его права ограничены базой Humorpedia.

```javascript
const appDb = db.getSiblingDB('humorpedia');
appDb.createUser({
  user: 'humorpedia_app',
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: [{ role: 'readWrite', db: 'humorpedia' }]
});
```

### Файл config.js

```javascript
window.__BACKEND_URL__ = window.location.origin;
```

Проект загружает этот файл до React. Он направляет публичный и административный API на тот же адрес, что и сайт. Для существующего прямого запроса старых редиректов frontend также собран с `http://localhost:8080`; поэтому открывайте стенд именно по этому адресу.

### Файл nginx.conf

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;
    client_max_body_size 20m;

    location = /config.js {
        add_header Cache-Control "no-store" always;
        try_files $uri =404;
    }

    location ~ ^/(api|media|images|uploads)(/|$) {
        proxy_pass http://backend:8001;
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location = /healthz {
        default_type application/json;
        return 200 '{"status":"ok"}';
    }

    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache" always;
    }
}
```

### Файл compose.yml

Здесь нет `build`: сервер использует уже загруженные образы. У MongoDB и backend нет опубликованных портов. Единственный веб-порт привязан к `127.0.0.1`, а не к публичному интерфейсу. [Поведение публикации портов Docker](https://docs.docker.com/engine/network/port-publishing/).

```yaml
name: humorpedia-test

x-logging: &small-logs
  driver: json-file
  options:
    max-size: "3m"
    max-file: "2"

services:
  mongodb:
    image: mongo:8.0.32
    environment:
      MONGO_INITDB_ROOT_USERNAME: root
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_ROOT_PASSWORD:?Заполните .env}
      MONGO_APP_PASSWORD: ${MONGO_APP_PASSWORD:?Заполните .env}
    command: ["mongod", "--auth", "--bind_ip_all", "--wiredTigerCacheSizeGB", "0.256"]
    volumes:
      - ./data/mongo:/data/db
      - ./mongo-init.js:/docker-entrypoint-initdb.d/10-app-user.js:ro
      - ./incoming:/incoming:ro
    healthcheck:
      test: ["CMD-SHELL", "mongosh --quiet --host localhost --username root --password \"$${MONGO_INITDB_ROOT_PASSWORD}\" --authenticationDatabase admin --eval \"db.adminCommand('ping')\""]
      interval: 30s
      timeout: 20s
      retries: 10
      start_period: 60s
    restart: unless-stopped
    logging: *small-logs

  backend:
    image: humorpedia/backend:${RELEASE_ID:?Заполните .env}
    environment:
      ENVIRONMENT: production
      PYTHONUNBUFFERED: "1"
      DB_NAME: humorpedia
      MONGO_HOST: mongodb
      MONGO_PORT: "27017"
      MONGO_USER: humorpedia_app
      MONGO_PASSWORD: ${MONGO_APP_PASSWORD:?Заполните .env}
      MONGO_AUTH_SOURCE: humorpedia
      JWT_SECRET: ${JWT_SECRET:?Заполните .env}
      ADMIN_EMAIL: ${ADMIN_EMAIL:?Заполните .env}
      ADMIN_USERNAME: ${ADMIN_USERNAME:?Заполните .env}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD:?Заполните .env}
      CORS_ORIGINS: http://localhost:8080
      UPLOAD_DIR: /app/uploads
      BACKUP_DIR: /app/backups
    command: ["gunicorn", "server:app", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8001", "--timeout", "120"]
    volumes:
      - ./data/uploads:/app/uploads
      - ./data/imported-images:/app/media/imported/images
      - ./data/images:/app/images
    depends_on:
      mongodb:
        condition: service_healthy
    restart: unless-stopped
    logging: *small-logs

  frontend:
    image: humorpedia/frontend:${RELEASE_ID:?Заполните .env}
    ports:
      - "127.0.0.1:8080:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./config.js:/usr/share/nginx/html/config.js:ro
    depends_on:
      - backend
    restart: unless-stopped
    logging: *small-logs
```

Кэш WiredTiger 0.256 ГБ — только часть памяти MongoDB, не ограничение всего процесса. Жёсткие лимиты контейнеров здесь не заданы: их следует выбирать после измерений, чтобы не провоцировать завершение БД при восстановлении.

Проверьте наличие файлов и YAML, не выводя секреты:

```bash
ls -l compose.yml mongo-init.js nginx.conf config.js
sudo docker compose config --quiet
```

Если имя файла после `nano` оказалось другим, исправьте его до запуска: отсутствующий файл bind mount может превратиться в каталог.

## 8 Запустите MongoDB и восстановите копию

**VPS, каталог `~/humorpedia-test`:**

```bash
sudo docker compose up -d mongodb
sudo docker compose ps
sudo docker compose logs --tail=50 mongodb
```

Дождитесь состояния `healthy`. Восстановление выполняйте только на новой базе этого тестового стенда, при ещё не запущенном backend. Команда содержит `--drop`: она заменяет восстанавливаемые коллекции целевой базы. Не выполняйте её на локальном рабочем стенде или на чужой базе.

```bash
sudo docker compose exec mongodb bash
```

**Внутри MongoDB контейнера VPS:**

```bash
mongorestore --host localhost --port 27017 \
  --username root --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --nsInclude='humorpedia.*' --drop \
  --archive=/incoming/humorpedia-test.archive.gz --gzip
exit
```

Проверьте отчёт: восстановление должно завершиться без ошибок. Затем:

```bash
sudo docker compose up -d backend frontend
sudo docker compose ps
sudo docker compose exec frontend nginx -t
curl --fail http://127.0.0.1:8080/api/health
curl --fail -I http://127.0.0.1:8080/
sudo docker stats --no-stream
free -h
df -h /
```

Если API ещё не готов, подождите завершения старта и создания индексов, посмотрите `sudo docker compose logs --tail=100 backend`. Не считайте возврат HTML главной страницы проверкой API: `/api/health` должен отдельно вернуть успешный JSON-ответ.

В копии БД уже могут быть администраторы. Поэтому переменные `ADMIN_EMAIL` и `ADMIN_PASSWORD` не гарантируют создание нового пользователя при старте. Создайте отдельного тестового администратора явно:

```bash
sudo docker compose exec backend python init_admin.py --email vps-test@humorpedia.invalid --username vps_test_admin
```

Пароль берётся из `ADMIN_PASSWORD`. Если такой пользователь уже есть, сначала выясните, ваш ли это предыдущий тестовый аккаунт; только для него при необходимости добавьте `--reset`. Не сбрасывайте пароли остальных импортированных пользователей.

Если контейнеры завершаются или постоянно перезапускаются, проверьте сообщения:

```bash
sudo docker compose logs --tail=100 backend mongodb
sudo journalctl -k --since '30 minutes ago' | grep -Ei 'out of memory|oom|killed process'
```

OOM означает нехватку памяти. Это не доказательство нехватки ресурсов у будущего VPS с 4 ГБ. Не пытайтесь одновременно запускать нагрузочный тест и восстановление базы на этом маленьком стенде.

## 9 Откройте сайт через SSH туннель

**Windows, отдельное окно PowerShell:**

```powershell
ssh -i "$env:USERPROFILE\.ssh\humorpedia_vps" -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -N -L 127.0.0.1:8080:127.0.0.1:8080 deploy@IP_VPS
```

Окно останется занятым, это нормально. В браузере откройте:

- `http://localhost:8080` — сайт;
- `http://localhost:8080/admin` — административный интерфейс;
- `http://localhost:8080/api/health` — проверка API.

Браузер подключается к вашему компьютеру, а дальше трафик идёт в зашифрованном SSH-туннеле. Снаружи по `http://IP_VPS:8080` сайт открываться не должен. Для завершения туннеля нажмите Ctrl+C; контейнеры на сервере продолжат работать.

Используйте этот браузерный адрес и локальный порт 8080: часть существующего frontend скомпилирована с этим адресом. Если порт занят на Windows, сначала выясните, каким приложением; не завершайте неизвестный процесс. Выбор другого порта потребует согласовать build argument и `CORS_ORIGINS`.

**Windows, другое окно:** проверьте, что порты не доступны публично:

```powershell
Test-NetConnection IP_VPS -Port 8080 -InformationLevel Quiet
Test-NetConnection IP_VPS -Port 8001 -InformationLevel Quiet
Test-NetConnection IP_VPS -Port 27017 -InformationLevel Quiet
```

Ожидается `False` во всех трёх случаях. Если есть публичный IPv6, проверьте его также. Проверка со своего компьютера подтверждает доступность с этого адреса, но не заменяет проверку правил firewall, если доступ ограничен источником.

Проверьте главную, каталоги людей/команд/шоу, поиск, страницы КВН, старый URL с перенаправлением и изображения. В админке создайте отдельную тестовую запись, загрузите картинку, сохраните её, затем удалите только эту тестовую запись. Проверяйте на копии данных, не на старом работающем сайте.

OAuth-вход через VK/Яндекс без отдельных настроек callback в этот стенд не включён. Тестируется обычный вход по email и паролю. Стенд не обслуживает почтовые ящики вашего домена.

## 10 Сохраните копию и проверьте перезагрузку

До существенных изменений стенда сделайте копию. При остановленных пишущих сервисах используйте отдельную SSH-сессию:

```bash
cd ~/humorpedia-test
sudo docker compose stop frontend backend
sudo docker compose exec mongodb bash
```

**Внутри MongoDB:**

```bash
mongodump --host localhost --port 27017 \
  --username root --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin --db humorpedia \
  --archive=/tmp/vps-test-backup.archive.gz --gzip
exit
```

**Снова на VPS:**

```bash
sudo docker compose cp mongodb:/tmp/vps-test-backup.archive.gz ./incoming/vps-test-backup.archive.gz
sudo tar -czf ./incoming/vps-test-media.tar.gz -C data imported-images images uploads
sudo chown deploy:deploy ./incoming/vps-test-backup.archive.gz ./incoming/vps-test-media.tar.gz
chmod 600 ./incoming/vps-test-backup.archive.gz ./incoming/vps-test-media.tar.gz
sudo docker compose start backend frontend
```

**Windows:** скачайте их за пределы VPS. В том же PowerShell:

```powershell
scp -i "$env:USERPROFILE\.ssh\humorpedia_vps" deploy@IP_VPS:/home/deploy/humorpedia-test/incoming/vps-test-backup.archive.gz "$releaseDir/"
scp -i "$env:USERPROFILE\.ssh\humorpedia_vps" deploy@IP_VPS:/home/deploy/humorpedia-test/incoming/vps-test-media.tar.gz "$releaseDir/"
```

Отдельно сохраните `.env` в защищённом хранилище или менеджере паролей. Файл с копией не доказывает восстановимость: восстановление проверяется в отдельной базе/окружении, не поверх работающего стенда. Ежедневное автоматическое внешнее резервирование — отдельная настройка перед длительной эксплуатацией.

Затем выполните `sudo reboot` на VPS, снова подключитесь, проверьте `sudo docker compose ps`, API, сайт и повторно откройте туннель. Данные должны сохраниться в `data`, контейнеры — подняться автоматически.

Не выполняйте `docker system prune --volumes`, удаление `data/mongo` или массовую очистку Docker. Для обычной остановки достаточно `sudo docker compose stop`; для возобновления — `sudo docker compose start`.

## 11 Как обновлять этот стенд

После выбора следующего проверенного коммита повторите сборку двух образов на Windows с новым `$releaseId` и тем же адресом frontend. Экспортируйте только новые backend/frontend, отправьте отдельный архив, загрузите образы на VPS, сделайте копию данных и измените `RELEASE_ID` в серверном `.env`.

```bash
sudo docker compose up -d --no-deps --force-recreate backend frontend
curl --fail http://127.0.0.1:8080/api/health
sudo docker compose ps
```

Команда пересоздаёт оба веб-контейнера: nginx получает актуальный адрес backend после его замены. Проверка `/api/health` через nginx должна проходить после каждого обновления. MongoDB и каталоги данных при обычном обновлении функционала не заменяются. Версия MongoDB закреплена; её обновление — отдельная операция.

Сохраните предыдущий `RELEASE_ID` и образы: для возврата к прежнему коду верните ID и пересоздайте frontend/backend. Возврат образов не отменяет выполненные изменения структуры или содержимого базы.

Эта процедура — ручной деплой готовых образов. После проверки первого запуска её можно перенести в GitHub Actions и добавить уведомления и автоматическую проверку результата.

## Что считать успешным результатом

- Войти на VPS можно по ключу, парольный SSH и root-вход отключены.
- Снаружи нет доступа к веб-порту, backend и MongoDB; сайт работает через туннель.
- API читает восстановленную базу, картинки открываются, тестовая запись сохраняется.
- Нет циклических перезапусков, OOM и постоянной интенсивной работы swap.
- После перезагрузки сайт поднимается, данные сохранены.
- Копии базы и медиа скачаны с сервера; перед длительной эксплуатацией проверены восстановление и автоматическое внешнее резервирование.

До проверки этих пунктов не переключайте домен старого сайта на новый сервер. Его доступность и данные эта инструкция не изменяет.
