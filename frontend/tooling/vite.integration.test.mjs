import assert from 'node:assert/strict';
import { test } from 'node:test';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const root = fileURLToPath(new URL('../', import.meta.url));
test('real Vite preserves proxy, SPA/static/env and native health error/recovery', async () => {
  const backend = http.createServer((request, response) => {
    response.setHeader('content-type', 'application/json');
    response.end(JSON.stringify({ path: request.url }));
  });
  await new Promise(resolve => backend.listen(0, '127.0.0.1', resolve));
  const target = 'http://127.0.0.1:' + backend.address().port;
  const vars = { ENABLE_HEALTH_CHECK: 'true', DOCKER_ENV: 'false', REACT_APP_BACKEND_URL: target, REACT_APP_USE_API_PROXY: 'false', R12C_PRIVATE_SECRET: 'private-env-must-not-be-exposed' };
  const before = Object.fromEntries(Object.keys(vars).map(key => [key, process.env[key]]));
  Object.assign(process.env, vars);
  const id = 'r12c-probe-' + randomUUID() + '.jsx';
  const fixture = path.join(root, 'src', id);
  let server;
  try {
    server = await createServer({ configFile: path.join(root, 'vite.config.mjs'), server: { host: '127.0.0.1', port: 0, strictPort: true }, logLevel: 'silent' });
    await server.listen();
    const base = 'http://127.0.0.1:' + server.httpServer.address().port;
    for (const prefix of ['/api', '/media', '/images', '/uploads']) {
      const response = await fetch(base + prefix + '/probe?value=1');
      assert.equal(response.status, 200);
      assert.equal((await response.json()).path, prefix + '/probe?value=1');
    }
    const htmlResponse = await fetch(base + '/admin/people/id.with.dots', { headers: { accept: 'text/html' } });
    assert.equal(htmlResponse.status, 200);
    const html = await htmlResponse.text();
    assert.match(html, /id="root"/);
    assert.match(html, /type="module"[^>]+src="\/src\/index.jsx"/);
    assert(html.indexOf('config.js') < html.indexOf('/src/index.jsx'));
    assert.equal((await fetch(base + '/config.js')).status, 200);
    const clientCode = await fetch(base + '/src/utils/apiBase.js').then(response => response.text());
    assert.equal(server.config.define['process.env.REACT_APP_BACKEND_URL'], JSON.stringify(target));
    assert.equal(server.config.define['process.env.REACT_APP_USE_API_PROXY'], JSON.stringify('false'));
    const envEntry = await fetch(base + '/node_modules/vite/dist/client/env.mjs').then(response => response.text());
    assert(envEntry.includes(target), envEntry);
    assert(!envEntry.includes(vars.R12C_PRIVATE_SECRET));
    assert(!clientCode.includes(vars.R12C_PRIVATE_SECRET));
    const ready = await fetch(base + '/health/ready');
    assert.equal(ready.status, 200, await ready.text());
    assert((await fetch(base + '/health/stats').then(response => response.json())).totalTransforms > 0);
    assert.equal((await fetch(base + '/health/simple').then(response => response.text())), 'OK');
    await fs.writeFile(fixture, 'export const value = ;');
    const broken = await fetch(base + '/src/' + id);
    assert.equal(broken.status, 500);
    const errors = await fetch(base + '/health/errors').then(response => response.json());
    assert.equal(errors.errorCount, 1, JSON.stringify(errors));
    assert.equal((await fetch(base + '/health/ready')).status, 503);
    assert.equal((await fetch(base + '/health/live')).status, 200);
    await fs.writeFile(fixture, 'export const value = "repaired";');
    server.moduleGraph.invalidateAll();
    const repaired = await fetch(base + '/src/' + id + '?t=' + Date.now());
    assert.equal(repaired.status, 200);
    assert.equal((await fetch(base + '/health/errors').then(response => response.json())).errorCount, 0);
    assert.equal((await fetch(base + '/health/ready')).status, 200);
  } finally {
    await server?.close();
    await fs.rm(fixture, { force: true });
    await new Promise(resolve => backend.close(resolve));
    for (const [key, value] of Object.entries(before)) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  }
});
