#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/deploy/humorpedia-test
[[ $(id -un) == deploy ]]
umask 077
test ! -e .env
printf 'RELEASE_ID=1813cf02f08c\nMONGO_ROOT_PASSWORD=%s\nMONGO_APP_PASSWORD=%s\nJWT_SECRET=%s\nADMIN_EMAIL=vps-test@humorpedia.invalid\nADMIN_USERNAME=vps_test_admin\nADMIN_PASSWORD=%s\n' \
  "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" > .env
mkdir -p data/mongo data/uploads data/imported-images data/images data/page-packages backups
chmod 700 data/page-packages
chmod 700 backups incoming
sudo -n docker compose config --quiet
echo 'Secrets generated on VPS; configuration valid'
