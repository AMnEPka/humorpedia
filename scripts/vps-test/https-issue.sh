#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID == 0 ]]
certbot=/opt/humorpedia-certbot/bin/certbot
if [[ ${1:-} == staging ]]; then
    install -d -m 700 /var/lib/humorpedia-certbot-staging
    "$certbot" certonly --staging --non-interactive --agree-tos --register-unsafely-without-email \
        --config-dir /var/lib/humorpedia-certbot-staging/config \
        --work-dir /var/lib/humorpedia-certbot-staging/work \
        --logs-dir /var/lib/humorpedia-certbot-staging/logs \
        --preferred-profile shortlived --webroot -w /var/lib/humorpedia-acme \
        --ip-address 77.105.139.231 --cert-name humorpedia-vps-ip-staging --key-type ecdsa
elif [[ ${1:-} == production ]]; then
    "$certbot" certonly --non-interactive --agree-tos --register-unsafely-without-email \
        --preferred-profile shortlived --webroot -w /var/lib/humorpedia-acme \
        --ip-address 77.105.139.231 --cert-name humorpedia-vps-ip --key-type ecdsa
else
    printf 'Usage: %s staging|production\n' "$0" >&2
    exit 2
fi
