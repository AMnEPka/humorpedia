const expected = JSON.parse(require('fs').readFileSync('/incoming/database-manifest.json', 'utf8'));
const copiedDb = db.getSiblingDB('humorpedia');
const actual = Object.fromEntries(copiedDb.getCollectionNames().sort().map(n => [n, copiedDb.getCollection(n).countDocuments({})]));
if (JSON.stringify(expected.collections) !== JSON.stringify(actual)) throw new Error('Restored collection counts differ from source');
const status = db.getSiblingDB('admin').serverStatus();
if (status.tcmalloc.usingPerCPUCaches !== false) throw new Error('Allocator fallback is not active');
print(JSON.stringify({ restoreCountsMatch: true, collections: Object.keys(actual).length, allocatorPerCpuCaches: status.tcmalloc.usingPerCPUCaches, uptimeSeconds: status.uptime, version: status.version }));
