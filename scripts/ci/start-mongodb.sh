#!/usr/bin/env bash
set -Eeuo pipefail

image='mongo:8.0.32'
container_id=''

cleanup_failed_start() {
  local status=$?
  trap - EXIT
  if (( status != 0 )) && [[ -n "$container_id" ]]; then
    printf 'MongoDB не запустилась; последние строки журнала контейнера %s:\n' "$container_id" >&2
    docker logs --tail 60 "$container_id" >&2 || true
    docker rm -fv "$container_id" >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap cleanup_failed_start EXIT

if [[ -z "${GITHUB_WORKSPACE:-}" || ! -d "$GITHUB_WORKSPACE" ]]; then
  printf 'Не задан существующий GITHUB_WORKSPACE\n' >&2
  exit 1
fi
seccomp_profile="$GITHUB_WORKSPACE/scripts/vps-test/seccomp-mongodb.json"
if [[ ! -f "$seccomp_profile" ]]; then
  printf 'Не найден seccomp-профиль MongoDB: %s\n' "$seccomp_profile" >&2
  exit 1
fi

requested_port="${CI_MONGO_PORT:-27017}"
if [[ ! "$requested_port" =~ ^[0-9]+$ ]] || (( requested_port > 65535 )); then
  printf 'CI_MONGO_PORT должен быть числом от 0 до 65535\n' >&2
  exit 1
fi

for env_file in "${GITHUB_ENV:-}" "${GITHUB_OUTPUT:-}"; do
  if [[ -n "$env_file" && ( ! -f "$env_file" || ! -w "$env_file" ) ]]; then
    printf 'Файл GitHub Actions недоступен для записи: %s\n' "$env_file" >&2
    exit 1
  fi
done

docker pull "$image"
container_id="$(docker create \
  --security-opt "seccomp=$seccomp_profile" \
  --publish "127.0.0.1:${requested_port}:27017/tcp" \
  "$image")"
if [[ -z "$container_id" ]]; then
  printf 'Docker не вернул идентификатор MongoDB-контейнера\n' >&2
  exit 1
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  printf 'container_id=%s\n' "$container_id" >> "$GITHUB_OUTPUT"
else
  printf 'container_id=%s\n' "$container_id"
fi

docker start "$container_id" >/dev/null
# mongosh writes config/telemetry under HOME. The image uses /data/db by default;
# racing entrypoint's initial chown with those lock files can kill mongod.
mongo_ready() {
  timeout 2s docker exec --user mongodb --env HOME=/tmp "$container_id" \
    mongosh --norc --quiet --eval 'db.adminCommand("ping").ok' >/dev/null 2>&1
}

deadline=$((SECONDS + 60))
published_port=''
while (( SECONDS < deadline )); do
  published_port="$(docker port "$container_id" 27017/tcp 2>/dev/null | sed -n '1s/.*://p' || true)"
  if [[ "$published_port" =~ ^[0-9]+$ ]] && mongo_ready; then
    break
  fi
  running="$(docker inspect --format '{{.State.Running}}' "$container_id" 2>/dev/null || true)"
  if [[ "$running" != 'true' ]]; then
    printf 'MongoDB-контейнер завершился до readiness-check\n' >&2
    exit 1
  fi
  sleep 1
done

if [[ ! "$published_port" =~ ^[0-9]+$ ]] || ! mongo_ready; then
  printf 'MongoDB не стала готова за 60 секунд\n' >&2
  exit 1
fi

mongo_url="mongodb://127.0.0.1:${published_port}"
if [[ -n "${GITHUB_ENV:-}" ]]; then
  printf 'MONGO_URL=%s\nMONGO_TOOLS_CONTAINER=%s\n' "$mongo_url" "$container_id" >> "$GITHUB_ENV"
else
  printf 'MONGO_URL=%s\nMONGO_TOOLS_CONTAINER=%s\n' "$mongo_url" "$container_id"
fi
