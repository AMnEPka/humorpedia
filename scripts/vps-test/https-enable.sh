#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID == 0 ]]
cd /home/deploy/humorpedia-test
test -s /etc/letsencrypt/live/humorpedia-vps-ip/fullchain.pem
test -s /etc/letsencrypt/live/humorpedia-vps-ip/privkey.pem
openssl x509 -in /etc/letsencrypt/live/humorpedia-vps-ip/fullchain.pem -checkend 86400 -noout
install -m 644 -o root -g root https-proxy.conf /etc/nginx/snippets/humorpedia-proxy.conf
cp -a /etc/nginx/sites-available/humorpedia-test /root/humorpedia-provision-backups/nginx-http-bootstrap.conf
install -m 644 -o root -g root https-public.conf /etc/nginx/sites-available/humorpedia-test
nginx -t
systemctl reload nginx
ufw allow 443/tcp comment 'Humorpedia public HTTPS'
install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
install -m 755 -o root -g root certbot-reload.sh /etc/letsencrypt/renewal-hooks/deploy/humorpedia-nginx
install -m 644 -o root -g root humorpedia-certbot.service humorpedia-certbot.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now humorpedia-certbot.timer
systemctl list-timers humorpedia-certbot.timer --no-pager
ufw status
