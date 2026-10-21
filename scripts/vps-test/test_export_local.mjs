// Run the real exporter body against fake Docker/process boundaries. This
// exercises its filesystem and stream handling without invoking Docker.
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { test } from 'node:test';
import { createHash } from 'node:crypto';
import {
  cpSync, createReadStream, createWriteStream, lstatSync, mkdirSync,
  mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';

const exporterPath = new URL('./export-local.mjs', import.meta.url);
const source = readFileSync(exporterPath, 'utf8').replace(/^import .*?;\r?\n/gm, '');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

function fixture({ failCopy = false, signal = null } = {}) {
  const work = mkdtempSync(join(tmpdir(), 'humorpedia-export-test-'));
  const destination = join(work, 'humorpedia-vps-fixture');
  const privateSource = join(work, 'private-source');
  mkdirSync(destination);
  mkdirSync(join(privateSource, 'nested'), { recursive: true });
  writeFileSync(join(privateSource, 'demo.zip'), Buffer.from([0, 1, 2, 255]));
  writeFileSync(join(privateSource, 'nested', 'manifest.json'), '{"ok":true}\n');

  const states = new Map(['humorpedia-frontend', 'humorpedia-backend', 'humorpedia-mongodb']
    .map(name => [name, { Name: `/${name}`, Id: `id-${name}`, State: { StartedAt: '2026-01-01T00:00:00Z', Status: 'running' }, RestartCount: 0 }]));
  const calls = [];
  const handlers = new Map();
  const fakeProcess = {
    argv: ['node', 'export-local.mjs', destination],
    once(name, handler) {
      const registered = handlers.get(name) || [];
      registered.push(handler);
      handlers.set(name, registered);
      return this;
    },
    exit(code) {
      calls.push(['process.exit', code]);
    },
    emit(name) {
      const registered = handlers.get(name) || [];
      handlers.set(name, registered.slice(1));
      if (!registered.length) throw new Error(`No handler registered for ${name}`);
      return registered[0]();
    },
  };

  function execFileSync(command, args) {
    calls.push([command, ...args]);
    if (command === 'tar') {
      writeFileSync(args[1], 'fixture archive');
      return '';
    }
    assert.equal(command, 'docker');
    if (args[0] === 'inspect') return JSON.stringify(args.slice(1).map(name => states.get(name)));
    if (args[0] === 'stop') {
      for (const name of args.slice(1)) states.get(name).State.Status = 'exited';
      return '';
    }
    if (args[0] === 'start') {
      for (const name of args.slice(1)) states.get(name).State.Status = 'running';
      return args.slice(1).join('\n');
    }
    if (args[0] === 'exec' && args[1] === 'humorpedia-mongodb' && args[2] === 'bash') {
      return JSON.stringify({ dataSize: 12, storageSize: 34, indexSize: 5, collections: { pages: 2 } });
    }
    if (args[0] === 'cp') {
      if (failCopy) throw new Error('fixture copy failure');
      const containerPath = args[1].split(':')[1];
      const target = args[2];
      const sourceRoot = containerPath.startsWith('/app/private/page-packages')
        ? privateSource
        : join(work, 'public-source', containerPath.includes('imported/images') ? 'imported-images' : containerPath.includes('/images') ? 'images' : 'uploads');
      mkdirSync(sourceRoot, { recursive: true });
      copyTreeContents(sourceRoot, target);
      return '';
    }
    throw new Error(`Unexpected docker call: ${args.join(' ')}`);
  }

  function spawn(command, args) {
    calls.push(['spawn', command, ...args]);
    assert.equal(command, 'docker');
    const child = new EventEmitter();
    child.stdout = new PassThrough();
    child.stderr = new PassThrough();
    setImmediate(() => {
      try {
        if (signal) fakeProcess.emit(signal);
      } catch (error) {
        child.emit('error', error);
      }
      child.stdout.end(Buffer.alloc(1024, 0x41));
      child.stderr.end();
      child.emit('close', 0);
    });
    return child;
  }

  const execute = new AsyncFunction(
    'execFileSync', 'spawn', 'createHash', 'mkdirSync', 'createReadStream',
    'createWriteStream', 'writeFileSync', 'statSync', 'lstatSync', 'readdirSync',
    'pipeline', 'resolve', 'join', 'process',
    source,
  );
  return {
    work, destination, calls, states, fakeProcess,
    run: () => execute(execFileSync, spawn, createHash, mkdirSync, createReadStream,
      createWriteStream, writeFileSync, statSync, lstatSync, readdirSync,
      pipeline,
      resolve, join, fakeProcess),
    cleanup: () => {
      assert.equal(dirname(resolve(work)), resolve(tmpdir()));
      assert.ok(work.startsWith(join(resolve(tmpdir()), 'humorpedia-export-test-')));
      rmSync(work, { recursive: true, force: true });
    },
  };
}

function copyTreeContents(sourceRoot, targetRoot) {
  for (const entry of readdirSync(sourceRoot, { withFileTypes: true })) {
    const from = join(sourceRoot, entry.name);
    const to = join(targetRoot, entry.name);
    if (entry.isDirectory()) {
      mkdirSync(to, { recursive: true });
      copyTreeContents(from, to);
    } else {
      mkdirSync(dirname(to), { recursive: true });
      cpSync(from, to);
    }
  }
}

function startCalls(calls) {
  return calls.filter(call => call[0] === 'docker' && call[1] === 'start');
}

test('exports private package hashes and includes package data and manifest in tar', async () => {
  const testFixture = fixture();
  try {
    await testFixture.run();
    const manifest = JSON.parse(readFileSync(join(testFixture.destination, 'media', 'page-packages-manifest.json'), 'utf8'));
    assert.deepEqual(manifest, {
      'page-packages/demo.zip': createHash('sha256').update(Buffer.from([0, 1, 2, 255])).digest('hex'),
      'page-packages/nested/manifest.json': createHash('sha256').update('{"ok":true}\n').digest('hex'),
    });
    const tar = testFixture.calls.find(call => call[0] === 'tar');
    assert.ok(tar, 'exporter should create the media archive');
    assert.deepEqual(tar.slice(-5), ['imported-images', 'images', 'uploads', 'page-packages', 'page-packages-manifest.json']);
    assert.equal(startCalls(testFixture.calls).length, 1);
  } finally {
    testFixture.cleanup();
  }
});

test('restores both writers after ordinary media-copy failure, exactly once', async () => {
  const testFixture = fixture({ failCopy: true });
  try {
    await assert.rejects(testFixture.run(), /fixture copy failure/);
    assert.equal(startCalls(testFixture.calls).length, 1);
    assert.equal(testFixture.states.get('humorpedia-backend').State.Status, 'running');
    assert.equal(testFixture.states.get('humorpedia-frontend').State.Status, 'running');
  } finally {
    testFixture.cleanup();
  }
});

for (const [signal, exitCode] of [['SIGINT', 130], ['SIGTERM', 143]]) {
  test(`${signal} restores writers exactly once before exiting ${exitCode}`, async () => {
    const testFixture = fixture({ signal });
    try {
      await testFixture.run();
      assert.equal(startCalls(testFixture.calls).length, 1);
      assert.equal(testFixture.states.get('humorpedia-backend').State.Status, 'running');
      assert.equal(testFixture.states.get('humorpedia-frontend').State.Status, 'running');
      const startIndex = testFixture.calls.findIndex(call => call[0] === 'docker' && call[1] === 'start');
      const exitIndex = testFixture.calls.findIndex(call => call[0] === 'process.exit' && call[1] === exitCode);
      assert.ok(exitIndex >= 0 && startIndex >= 0 && startIndex < exitIndex, 'writers must restart before process.exit');
    } finally {
      testFixture.cleanup();
    }
  });
}
