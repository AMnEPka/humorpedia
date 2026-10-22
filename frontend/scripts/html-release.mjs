import { createHash } from 'node:crypto';
import { lstat, readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
export const RELEASE_MANIFEST = 'public-html-release.json';
const hash = value => createHash('sha256').update(value).digest('hex');
export async function writeHtmlRelease(buildDir) {
  const entries = [];
  async function visit(dir, prefix = '') {
    for (const name of await readdir(dir)) {
      const relative = prefix + name;
      const full = path.join(dir, name);
      const stat = await lstat(full);
      if (stat.isSymbolicLink()) throw new Error('Release symlink is forbidden: ' + relative);
      if (stat.isDirectory()) await visit(full, relative + '/');
      else if (stat.isFile() && relative !== RELEASE_MANIFEST) entries.push([relative, hash(await readFile(full))]);
      else if (!stat.isFile()) throw new Error('Unsupported release entry: ' + relative);
    }
  }
  if ((await lstat(buildDir)).isSymbolicLink()) throw new Error('Release symlink is forbidden');
  await visit(buildDir);
  entries.sort(([a], [b]) => Buffer.compare(Buffer.from(a), Buffer.from(b)));
  const files = Object.fromEntries(entries);
  if (!files['index.html']) throw new Error('Release index.html is missing');
  const manifest = {schema_version:1, release_id:hash(JSON.stringify(files)), files};
  await writeFile(path.join(buildDir, RELEASE_MANIFEST), JSON.stringify(manifest, null, 2) + '\n');
  return manifest;
}
