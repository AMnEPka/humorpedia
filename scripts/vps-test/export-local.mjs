// Export the existing local stack without recreating any container.
// Database bytes are streamed directly to a host file, never through text decoding.
import { execFileSync, spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, createReadStream, createWriteStream, writeFileSync, statSync, lstatSync, readdirSync } from 'node:fs';
import { pipeline } from 'node:stream/promises';
import { resolve, join } from 'node:path';

const destination = resolve(process.argv[2] || '');
if (!process.argv[2] || !destination.includes('humorpedia-vps-')) throw new Error('Dedicated release directory required');
const run = (args, options = {}) => execFileSync('docker', args, { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024, ...options });
const privatePackageManifest = async root => {
  const entries = {};
  const walk = async (directory, relative = '') => {
    for (const entry of readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const absolute = join(directory, entry.name);
      const stat = lstatSync(absolute);
      const path = relative ? join(relative, entry.name) : entry.name;
      if (stat.isDirectory()) {
        await walk(absolute, path);
      } else if (stat.isFile()) {
        const hash = createHash('sha256');
        for await (const chunk of createReadStream(absolute)) hash.update(chunk);
        entries[`page-packages/${path.replaceAll('\\', '/')}`] = hash.digest('hex');
      } else {
        throw new Error(`Unsupported private page-package entry: ${absolute}`);
      }
    }
  };
  await walk(root);
  return Object.fromEntries(Object.entries(entries).sort(([a], [b]) => a.localeCompare(b)));
};
const names = ['humorpedia-frontend', 'humorpedia-backend', 'humorpedia-mongodb'];
const state = () => JSON.parse(run(['inspect', ...names])).map(c => ({ name: c.Name, id: c.Id, startedAt: c.State.StartedAt, status: c.State.Status, restartCount: c.RestartCount }));
const before = state();
if (before.some(c => c.status !== 'running')) throw new Error('All original containers must be running');
writeFileSync(join(destination, 'local-containers-before.json'), JSON.stringify(before, null, 2));
const mongoInfo = () => JSON.parse(run(['exec', 'humorpedia-mongodb', 'bash', '-lc',
  'mongosh --quiet --host localhost --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --eval \'const d=db.getSiblingDB("humorpedia"); const s=d.stats(); print(JSON.stringify({dataSize:s.dataSize,storageSize:s.storageSize,indexSize:s.indexSize,collections:Object.fromEntries(d.getCollectionNames().sort().map(n=>[n,d.getCollection(n).countDocuments({})]))}));\''
]));
let stopped = false;
const restartOriginalWriters = () => {
  if (!stopped) return;
  run(['start', 'humorpedia-backend', 'humorpedia-frontend']);
  stopped = false;
};
for (const [signal, exitCode] of [['SIGINT', 130], ['SIGTERM', 143]]) {
  process.once(signal, () => {
    try {
      restartOriginalWriters();
    } catch (error) {
      console.error('Could not restart original writers after interruption:', error.message);
    }
    process.exit(exitCode);
  });
}
try {
  // Only the two writing/web services are stopped, not MongoDB or other projects.
  stopped = true;
  run(['stop', 'humorpedia-frontend', 'humorpedia-backend']);
  const dbInfo = mongoInfo();
  writeFileSync(join(destination, 'database-manifest.json'), JSON.stringify(dbInfo, null, 2));
  const output = createWriteStream(join(destination, 'humorpedia-test.archive.gz'), { flags: 'wx' });
  const child = spawn('docker', ['exec', 'humorpedia-mongodb', 'bash', '-lc',
    'exec mongodump --host localhost --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db humorpedia --archive --gzip'
  ], { stdio: ['ignore', 'pipe', 'pipe'] });
  let diagnostics = '';
  child.stderr.on('data', chunk => { diagnostics = (diagnostics + chunk.toString()).slice(-8192); });
  const exit = new Promise((resolveExit, reject) => { child.once('error', reject); child.once('close', code => resolveExit(code)); });
  await pipeline(child.stdout, output);
  if (await exit !== 0) throw new Error(`mongodump failed: ${diagnostics}`);
  if (statSync(join(destination, 'humorpedia-test.archive.gz')).size < 1000) throw new Error('Unexpected empty archive');
  const mediaRoot = join(destination, 'media');
  for (const [containerPath, folder] of [
    ['/app/media/imported/images/.', 'imported-images'], ['/app/images/.', 'images'], ['/app/uploads/.', 'uploads']
  ]) {
    mkdirSync(join(mediaRoot, folder), { recursive: true });
    run(['cp', `humorpedia-backend:${containerPath}`, join(mediaRoot, folder)]);
  }
  const packagesRoot = join(mediaRoot, 'page-packages');
  mkdirSync(packagesRoot, { recursive: true });
  run(['cp', 'humorpedia-backend:/app/private/page-packages/.', packagesRoot]);
  const packageManifest = await privatePackageManifest(packagesRoot);
  writeFileSync(join(mediaRoot, 'page-packages-manifest.json'), JSON.stringify(packageManifest, null, 2), { flag: 'wx', mode: 0o600 });
  const afterDb = mongoInfo();
  if (JSON.stringify(dbInfo.collections) !== JSON.stringify(afterDb.collections)) throw new Error('Collection counts changed during snapshot; inspect other writers');
  console.log(JSON.stringify({ databaseBytes: dbInfo.dataSize, storageBytes: dbInfo.storageSize, indexBytes: dbInfo.indexSize, collections: Object.keys(dbInfo.collections).length, dumpBytes: statSync(join(destination, 'humorpedia-test.archive.gz')).size }));
} finally {
  restartOriginalWriters();
  const after = state();
  writeFileSync(join(destination, 'local-containers-after.json'), JSON.stringify(after, null, 2));
  for (const original of before) {
    const current = after.find(c => c.name === original.name);
    if (!current || current.id !== original.id || current.status !== 'running') throw new Error(`Original container not restored: ${original.name}`);
  }
  console.log('Original local container IDs preserved; all running');
}
execFileSync('tar', ['-czf', join(destination, 'media.tar.gz'), '-C', join(destination, 'media'), 'imported-images', 'images', 'uploads', 'page-packages', 'page-packages-manifest.json']);
console.log(`Media archive: ${statSync(join(destination, 'media.tar.gz')).size} bytes`);
