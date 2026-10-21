#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID == 0 ]]
test -s /home/deploy/.ssh/authorized_keys
unexpected_rules=$(ufw show added | grep '^ufw ' | grep -Ev '^ufw allow 22/tcp( comment .*)?$' || true)
if [[ -n $unexpected_rules ]]; then
  echo 'Unexpected existing UFW rules; inspect before changing firewall' >&2
  exit 1
fi
backup_dir=/root/humorpedia-provision-backups
install -d -m 700 "$backup_dir"
if [[ -f /etc/ssh/sshd_config.d/00-humorpedia-test.conf ]]; then
  cp -a /etc/ssh/sshd_config.d/00-humorpedia-test.conf "$backup_dir/ssh-$(date +%Y%m%d%H%M%S).conf"
fi
printf 'PubkeyAuthentication yes\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\nMaxAuthTries 3\nLoginGraceTime 30\n' > /etc/ssh/sshd_config.d/00-humorpedia-test.conf
sshd -t
effective=$(sshd -T)
for expected in 'port 22' 'pubkeyauthentication yes' 'passwordauthentication no' 'kbdinteractiveauthentication no' 'permitrootlogin no'; do
  grep -qx "$expected" <<< "$effective"
done
systemctl reload ssh
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH key access'
ufw --force enable
ufw status verbose
sshd -T | grep -E '^(port|pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication|permitrootlogin) '
