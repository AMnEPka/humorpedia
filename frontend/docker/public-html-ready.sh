#!/bin/sh
set -eu
nginx -t >/dev/null 2>&1
if [ "${PUBLIC_HTML_ENABLED:-false}" = false ]; then
  [ "${SEARCH_INDEXING_ENABLED:-false}" = false ]
  wget -q -O /dev/null http://127.0.0.1/healthz
  exit
fi
. /opt/public-html/gateway-configs/release.env
headers=$(wget -S -O /tmp/html-ready-body --header="X-Humorpedia-Release: $HTML_RELEASE_ID" "$HTML_BACKEND_ORIGIN/_internal/public-html/state" 2>&1) || exit 1
printf '%s\n' "$headers" | grep -iq "X-Humorpedia-Release: $HTML_RELEASE_ID"
grep -q '"status":"ready"' /tmp/html-ready-body
if [ "${SEARCH_INDEXING_ENABLED:-false}" = true ]; then expected=true; else expected=false; fi
grep -q "\"indexing_enabled\":$expected" /tmp/html-ready-body
