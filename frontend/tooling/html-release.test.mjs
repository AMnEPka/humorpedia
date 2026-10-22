import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, symlink, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { writeHtmlRelease } from '../scripts/html-release.mjs';

test('release is deterministic and covers all chunks', async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'html-release-'));
  try {
    await mkdir(path.join(dir, 'assets'));
    await writeFile(path.join(dir, 'index.html'), '<div id="root"></div>');
    await writeFile(path.join(dir, 'assets', 'dynamic.js'), 'chunk');
    const first = await writeHtmlRelease(dir);
    assert.equal(first.schema_version, 1);
    assert.equal(first.release_id.length, 64);
    assert.deepEqual(Object.keys(first.files), ['assets/dynamic.js', 'index.html']);
    assert.deepEqual(await writeHtmlRelease(dir), first);
    await writeFile(path.join(dir, 'assets', 'dynamic.js'), 'changed');
    assert.notEqual((await writeHtmlRelease(dir)).release_id, first.release_id);
  } finally { await rm(dir, {recursive:true, force:true}); }
});
test('rejects symlink escape', async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'html-release-'));
  try {
    await symlink(os.tmpdir(), path.join(dir, 'escaped'), 'dir');
    await assert.rejects(writeHtmlRelease(dir), /symlink/i);
  } finally { await rm(dir, {recursive:true, force:true}); }
});
