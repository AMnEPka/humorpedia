#!/usr/bin/env bash
# Run only on the dedicated, empty test VPS, as root.
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
[[ $EUID == 0 ]] || { echo 'Root required' >&2; exit 1; }
source /etc/os-release
[[ $ID == ubuntu && $(dpkg --print-architecture) == amd64 ]]
grep -qw avx /proc/cpuinfo
id deploy >/dev/null
test -s /home/deploy/.ssh/authorized_keys

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl openssl ufw python3
apt-get upgrade -y

if ! swapon --show=NAME --noheadings | grep -q .; then
  test ! -e /swapfile
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || printf '\n/swapfile none swap sw 0 0\n' >> /etc/fstab
fi
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: %s\nComponents: stable\nArchitectures: amd64\nSigned-By: /etc/apt/keyrings/docker.asc\n' "${UBUNTU_CODENAME:-$VERSION_CODENAME}" > /etc/apt/sources.list.d/docker.sources
apt-get update
apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
docker version --format '{{.Server.Version}}'
docker compose version
apt-get clean
free -h
df -h /
