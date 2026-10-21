#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/deploy/humorpedia-test
[[ ${1:-} =~ ^[[:xdigit:]]{64}$ ]]
printf '%s  incoming/images.tar.gz\n' "$1" | sha256sum -c -
tar -xOzf incoming/images.tar.gz images.tar | sudo -n docker load
sudo -n docker image inspect humorpedia/backend:1813cf02f08c humorpedia/frontend:1813cf02f08c mongo:8.0.32 --format '{{.RepoTags}}'
# Only the verified temporary transfer file; the original remains on Windows.
rm -- /home/deploy/humorpedia-test/incoming/images.tar.gz
df -h /
