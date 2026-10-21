#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/deploy/humorpedia-test
[[ ${1:-} =~ ^[[:xdigit:]]{64}$ && ${2:-} =~ ^[[:xdigit:]]{64}$ ]]
test ! -e .restore-complete
printf '%s  incoming/humorpedia-test.archive.gz\n' "$1" | sha256sum -c -
chmod 600 incoming/*
if [[ ! -f .media-restored ]]; then
printf '%s  incoming/media.tar.gz\n' "$2" | sha256sum -c -
# Expected archive paths are only media directories, with no absolute/traversal names.
tar -tzf incoming/media.tar.gz | awk '
  /^\// || /(^|\/)\.\.($|\/)/ { bad=1 }
  !/^(imported-images|images|uploads)(\/|$)/ { bad=1 }
  END { exit bad ? 1 : 0 }
'
tar -xzf incoming/media.tar.gz -C data
touch .media-restored
# The original media archive remains off-server; do not keep a duplicate on a 10 GB VPS.
rm -- /home/deploy/humorpedia-test/incoming/media.tar.gz
fi
sudo -n docker compose up -d --wait --wait-timeout 240 mongodb
sudo -n docker compose exec -T mongodb bash -lc 'mongosh --quiet --host localhost --username root --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --eval '\''if(db.getSiblingDB("humorpedia").getCollectionNames().length) quit(2)'\'''
sudo -n docker compose exec -T mongodb bash -lc 'exec mongorestore --host localhost --username root --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --nsInclude="humorpedia.*" --numParallelCollections=1 --numInsertionWorkersPerCollection=1 --archive=/incoming/humorpedia-test.archive.gz --gzip' > restore.log 2>&1
tail -n 4 restore.log
touch .restore-complete
# Keep the small DB archive; media original is preserved off-server.
df -h /
