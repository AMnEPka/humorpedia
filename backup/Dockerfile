# Минимальный образ для бэкапа MongoDB (mongodump).
# Debian + официальный репозиторий MongoDB (надёжнее, чем скачивать tgz на Alpine).
FROM debian:bullseye-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
  && wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-6.0.gpg \
  && echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/debian bullseye/mongodb-org/6.0 main" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list \
  && apt-get update \
  && apt-get install -y --no-install-recommends mongodb-database-tools \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /backup

COPY backup.sh /backup/backup.sh
COPY run-loop.sh /backup/run-loop.sh
# Убираем CRLF (Windows), иначе exec выдаёт "no such file or directory"
RUN sed -i 's/\r$//' /backup/backup.sh /backup/run-loop.sh && chmod +x /backup/backup.sh /backup/run-loop.sh

# По умолчанию — цикл (бэкап каждый BACKUP_INTERVAL с). Один раз: docker compose run -e BACKUP_INTERVAL=0 backup
ENTRYPOINT ["/backup/run-loop.sh"]
