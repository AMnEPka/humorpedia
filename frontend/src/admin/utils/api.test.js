// CRA/Jest resolves the package's ESM entrypoint as CommonJS; use Axios's real CJS build.
jest.mock('axios', () => jest.requireActual('axios/dist/node/axios.cjs'));

import axios, { AxiosError } from 'axios';
import api from './api';

const originalApiAdapter = api.defaults.adapter;
const originalAxiosAdapter = axios.defaults.adapter;

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function response(config, data, status = 200) {
  return { data, status, statusText: status === 200 ? 'OK' : 'Unauthorized', headers: {}, config, request: {} };
}

function unauthorized(config) {
  const result = response(config, { detail: 'Unauthorized' }, 401);
  return Promise.reject(new AxiosError('Request failed with status code 401', AxiosError.ERR_BAD_REQUEST, config, null, result));
}

function networkError(config) {
  return Promise.reject(new AxiosError('Network Error', AxiosError.ERR_NETWORK, config));
}

function waitFor(predicate) {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const check = () => {
      if (predicate()) return resolve();
      if (Date.now() - started > 1000) return reject(new Error('Timed out waiting for adapter requests'));
      setTimeout(check, 0);
    };
    check();
  });
}

function installAdapter(adapter) {
  api.defaults.adapter = adapter;
  axios.defaults.adapter = adapter;
}

beforeEach(() => {
  localStorage.setItem('admin_token', 'expired-token');
  localStorage.setItem('admin_user', JSON.stringify({ id: 'user-1' }));
  window.history.replaceState({}, '', '/');
});

afterEach(() => {
  api.defaults.adapter = originalApiAdapter;
  axios.defaults.adapter = originalAxiosAdapter;
  localStorage.clear();
  jest.restoreAllMocks();
});

test('settles every concurrent request when the shared refresh is rejected', async () => {
  const refresh = deferred();
  let protectedRequests = 0;
  let refreshRequests = 0;
  installAdapter((config) => {
    if (config.url.includes('/auth/refresh')) {
      refreshRequests += 1;
      return refresh.promise;
    }
    protectedRequests += 1;
    return unauthorized(config);
  });

  const requests = [api.get('/protected/one'), api.get('/protected/two')];
  await waitFor(() => protectedRequests === 2 && refreshRequests === 1);
  refresh.reject(new Error('refresh unavailable'));
  const results = await Promise.allSettled(requests);

  expect(results.map((result) => result.status)).toEqual(['rejected', 'rejected']);
  expect(refreshRequests).toBe(1);
  expect(localStorage.getItem('admin_token')).toBeNull();
  expect(localStorage.getItem('admin_user')).toBeNull();
});

test('retries all concurrent requests with the one successful refresh result', async () => {
  const refresh = deferred();
  let refreshRequests = 0;
  let protectedRequests = 0;
  installAdapter((config) => {
    if (config.url.includes('/auth/refresh')) {
      refreshRequests += 1;
      return refresh.promise;
    }
    protectedRequests += 1;
    if (config.headers.Authorization === 'Bearer renewed-token') {
      return Promise.resolve(response(config, { ok: true }));
    }
    return unauthorized(config);
  });

  const requests = [api.get('/protected/one'), api.get('/protected/two')];
  await waitFor(() => protectedRequests === 2 && refreshRequests === 1);
  refresh.resolve(response({ url: '/auth/refresh' }, { access_token: 'renewed-token', user: { id: 'user-1' } }));
  const results = await Promise.all(requests);

  expect(results.map(({ data }) => data)).toEqual([{ ok: true }, { ok: true }]);
  expect(refreshRequests).toBe(1);
  expect(protectedRequests).toBe(4);
});

test('does not start refresh or clear the token when a request has no response', async () => {
  let refreshRequests = 0;
  installAdapter((config) => {
    if (config.url.includes('/auth/refresh')) refreshRequests += 1;
    return networkError(config);
  });

  await expect(api.get('/protected/offline')).rejects.toMatchObject({ code: AxiosError.ERR_NETWORK });

  expect(refreshRequests).toBe(0);
  expect(localStorage.getItem('admin_token')).toBe('expired-token');
});

test('does not refresh auth endpoint 401 responses', async () => {
  let refreshRequests = 0;
  let requestCount = 0;
  installAdapter((config) => {
    if (config.url.includes('/auth/refresh')) refreshRequests += 1;
    requestCount += 1;
    return unauthorized(config);
  });

  await expect(api.post('/auth/login', { email: 'editor@example.test', password: 'wrong' })).rejects.toMatchObject({ response: { status: 401 } });
  await expect(api.post('/auth/refresh')).rejects.toMatchObject({ response: { status: 401 } });

  expect(requestCount).toBe(2);
  expect(refreshRequests).toBe(1);
});

test('marks queued request retries so a second 401 cannot refresh again', async () => {
  let refreshRequests = 0;
  let protectedRequests = 0;
  installAdapter((config) => {
    if (config.url.includes('/auth/refresh')) {
      refreshRequests += 1;
      return Promise.resolve(response(config, { access_token: `renewed-${refreshRequests}` }));
    }
    protectedRequests += 1;
    return unauthorized(config);
  });

  const results = await Promise.allSettled([api.get('/protected/one'), api.get('/protected/two')]);

  expect(results.map((result) => result.status)).toEqual(['rejected', 'rejected']);
  expect(protectedRequests).toBe(4);
  expect(refreshRequests).toBe(1);
});

test('starts a fresh refresh after a previous refresh failure', async () => {
  let refreshRequests = 0;
  let failFirstRefresh = true;
  installAdapter((config) => {
    if (config.url.includes('/auth/refresh')) {
      refreshRequests += 1;
      if (failFirstRefresh) {
        failFirstRefresh = false;
        return networkError(config);
      }
      return Promise.resolve(response(config, { access_token: 'recovered-token' }));
    }
    if (config.headers.Authorization === 'Bearer recovered-token') return Promise.resolve(response(config, { ok: true }));
    return unauthorized(config);
  });

  await expect(api.get('/protected/first')).rejects.toMatchObject({ response: { status: 401 } });
  localStorage.setItem('admin_token', 'expired-again');
  await expect(api.get('/protected/second')).resolves.toMatchObject({ data: { ok: true } });

  expect(refreshRequests).toBe(2);
  expect(localStorage.getItem('admin_token')).toBe('recovered-token');
});
