#!/bin/sh
set -eu
serving="${PUBLIC_HTML_ENABLED:-false}"
indexing="${SEARCH_INDEXING_ENABLED:-false}"
case "$serving/$indexing" in
  false/false) mode=disabled ;;
  true/false) mode=enabled_noindex ;;
  true/true) mode=enabled_index ;;
  *) echo "Invalid public HTML flags" >&2; exit 1 ;;
esac
cp "/opt/public-html/gateway-configs/$mode.conf" /etc/nginx/conf.d/default.conf
cp "/opt/public-html/gateway-configs/$mode.js" /usr/share/nginx/html/config.js
