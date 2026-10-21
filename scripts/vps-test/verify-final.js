const expected = JSON.parse(require('fs').readFileSync('/incoming/database-manifest.json', 'utf8'));
expected.collections.users += 1; // Only the separately created VPS test administrator.
const copiedDb = db.getSiblingDB('humorpedia');
const actual = Object.fromEntries(copiedDb.getCollectionNames().sort().map(n => [n, copiedDb.getCollection(n).countDocuments({})]));
if (JSON.stringify(expected.collections) !== JSON.stringify(actual)) {
  print(JSON.stringify({expected: expected.collections, actual}));
  throw new Error('Final collection counts differ from source plus test administrator');
}
const admin = copiedDb.users.findOne({email: 'vps-test@humorpedia.invalid'});
if (!admin || admin.role !== 'admin') throw new Error('VPS test administrator missing');
const status = db.getSiblingDB('admin').serverStatus();
if (status.tcmalloc.usingPerCPUCaches !== false) throw new Error('Allocator fallback is not active');
const roles = copiedDb.getUser('humorpedia_app').roles;
if (JSON.stringify(roles) !== JSON.stringify([{role: 'readWrite', db: 'humorpedia'}])) throw new Error('Unexpected database application privileges');
print(JSON.stringify({finalCountsMatch: true, collections: Object.keys(actual).length, documents: Object.values(actual).reduce((a,b)=>a+b,0), allocatorPerCpuCaches: false, uptimeSeconds: status.uptime, version: status.version, appLeastPrivilege: true}));
