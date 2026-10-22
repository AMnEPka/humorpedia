import assert from 'node:assert/strict';
import { once } from 'node:events';
import http from 'node:http';
import test from 'node:test';
import devHealthPlugin from '../plugins/health-check/vite-health-plugin.mjs';

function createHarness() {
  const middlewares = [];
  const sentMessages = [];
  const httpServer = http.createServer((req, res) => {
    let index = 0;
    const next = () => {
      const middleware = middlewares[index++];
      if (!middleware) {
        res.statusCode = 404;
        res.end('not found');
        return;
      }
      middleware(req, res, next);
    };
    next();
  });
  const viteServer = {
    httpServer,
    middlewares: { use(middleware) { middlewares.push(middleware); } },
    ws: { send(message) { sentMessages.push(message); } },
  };
  const plugin = devHealthPlugin();
  plugin.configureServer(viteServer);
  return { httpServer, plugin, sentMessages, viteServer };
}

async function listen(httpServer) {
  httpServer.listen(0, '127.0.0.1');
  await once(httpServer, 'listening');
  return `http://127.0.0.1:${httpServer.address().port}`;
}

function close(httpServer) {
  return new Promise((resolve, reject) => {
    httpServer.close((error) => error ? reject(error) : resolve());
  });
}

async function request(baseUrl, pathname, method = 'GET') {
  return new Promise((resolve, reject) => {
    const req = http.request(new URL(pathname, baseUrl), { method }, (response) => {
      const chunks = [];
      response.on('data', (chunk) => chunks.push(chunk));
      response.on('end', () => resolve({
        status: response.statusCode,
        text: Buffer.concat(chunks).toString('utf8'),
        contentType: response.headers['content-type'],
      }));
    });
    req.on('error', reject);
    req.end();
  });
}

async function json(baseUrl, pathname) {
  const response = await request(baseUrl, pathname);
  return { ...response, body: JSON.parse(response.text) };
}

test('health endpoints report idle then ready after a successful module transform', async (t) => {
  const harness = createHarness();
  const baseUrl = await listen(harness.httpServer);
  t.after(() => close(harness.httpServer));

  const idle = await request(baseUrl, '/health/simple');
  assert.equal(idle.status, 200);
  assert.equal(idle.text, 'IDLE');
  const notReady = await json(baseUrl, '/health/ready');
  assert.equal(notReady.status, 503);
  assert.equal(notReady.body.ready, false);

  await harness.plugin.transform.call({}, 'export default 1', '/src/App.jsx');

  const simpleReady = await request(baseUrl, '/health/simple');
  assert.equal(simpleReady.status, 200);
  assert.equal(simpleReady.text, 'OK');
  const ready = await json(baseUrl, '/health/ready');
  assert.equal(ready.status, 200);
  assert.equal(ready.body.ready, true);
  const health = await json(baseUrl, '/health');
  assert.equal(health.status, 200);
  assert.equal(health.body.vite.totalTransforms, 1);
  assert.equal(health.body.vite.listening, true);
  assert.equal(typeof health.body.vite.lastSuccessfulTransformAt, 'string');
  assert.equal(Object.hasOwn(health.body, 'webpack'), false);
  const stats = await json(baseUrl, '/health/stats');
  assert.equal(stats.status, 200);
  assert.equal(stats.body.totalTransforms, 1);
  assert.equal(Object.hasOwn(stats.body, 'averageCompileTime'), false);
  const live = await json(baseUrl, '/health/live');
  assert.equal(live.status, 200);
  assert.equal(live.body.alive, true);
});

test('a Vite transform error makes readiness fail and is reported without webpack metrics', async (t) => {
  const harness = createHarness();
  const baseUrl = await listen(harness.httpServer);
  t.after(() => close(harness.httpServer));

  harness.viteServer.ws.send({ type: 'error', err: { id: '/src/Broken.jsx', message: 'Unexpected token' } });

  const errors = await json(baseUrl, '/health/errors');
  assert.equal(errors.status, 200);
  assert.equal(errors.body.errorCount, 1);
  assert.equal(errors.body.errors[0].moduleId, '/src/Broken.jsx');
  assert.equal(errors.body.errors[0].message, 'Unexpected token');
  assert.equal(Object.hasOwn(errors.body, 'warningCount'), false);
  const simpleError = await request(baseUrl, '/health/simple');
  assert.equal(simpleError.status, 503);
  assert.equal(simpleError.text, 'ERROR');
  assert.equal((await json(baseUrl, '/health')).status, 200);
  assert.equal((await json(baseUrl, '/health/ready')).status, 503);
  assert.equal((await json(baseUrl, '/health/live')).status, 200);
  assert.equal(harness.sentMessages.length, 1);
});

test('a successful retransform clears only the matching module error', async (t) => {
  const harness = createHarness();
  const baseUrl = await listen(harness.httpServer);
  t.after(() => close(harness.httpServer));

  harness.viteServer.ws.send({ type: 'error', err: { id: '/src/App.jsx', message: 'first failure' } });
  harness.viteServer.ws.send({ type: 'error', err: { id: '/src/Broken.jsx', message: 'second failure' } });
  await harness.plugin.transform.call({}, 'export default 1', '/src/App.jsx?import&t=123');

  let errors = await json(baseUrl, '/health/errors');
  assert.equal(errors.body.errorCount, 1);
  assert.equal(errors.body.errors[0].moduleId, '/src/Broken.jsx');

  await harness.plugin.transform.call({}, 'export default 2', '/src/Broken.jsx?import&t=456');
  errors = await json(baseUrl, '/health/errors');
  assert.equal(errors.body.errorCount, 0);
  assert.equal((await request(baseUrl, '/health/simple')).text, 'OK');
});

test('unknown routes and methods continue to the next middleware', async (t) => {
  const harness = createHarness();
  const baseUrl = await listen(harness.httpServer);
  t.after(() => close(harness.httpServer));

  const unknown = await request(baseUrl, '/health/private');
  assert.equal(unknown.status, 404);
  assert.equal(unknown.text, 'not found');
  const method = await request(baseUrl, '/health', 'POST');
  assert.equal(method.status, 404);
  assert.equal(method.text, 'not found');
});
