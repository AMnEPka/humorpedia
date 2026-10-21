#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID == 0 ]]
cd /home/deploy/humorpedia-test
# First-time setup only. Do not overwrite another existing host nginx deployment.
test ! -e /etc/nginx/sites-enabled/humorpedia-test
test ! -e /opt/humorpedia-certbot
test -z "$(ss -lnt '( sport = :80 or sport = :443 )' | tail -n +2)"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends nginx python3-venv
python3 -m venv /opt/humorpedia-certbot
/opt/humorpedia-certbot/bin/pip install --no-cache-dir 'certbot==5.8.0'
/opt/humorpedia-certbot/bin/certbot --version
install -d -m 755 /var/lib/humorpedia-acme/.well-known/acme-challenge
install -d -m 700 /root/humorpedia-provision-backups
if [[ -L /etc/nginx/sites-enabled/default ]]; then
    mv /etc/nginx/sites-enabled/default /root/humorpedia-provision-backups/nginx-default.disabled
fi
test -z "$(find /etc/nginx/sites-enabled -mindepth 1 -maxdepth 1 -print -quit)"
install -m 644 -o root -g root https-bootstrap.conf /etc/nginx/sites-available/humorpedia-test
ln -s /etc/nginx/sites-available/humorpedia-test /etc/nginx/sites-enabled/humorpedia-test
nginx -t
systemctl enable --now nginx
systemctl reload nginx
ufw allow 80/tcp comment 'ACME and HTTPS redirect'
apt-get clean
echo 'HTTP challenge endpoint prepared; app is not served publicly yet'
