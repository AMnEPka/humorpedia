jest.mock('axios', () => ({
  create: jest.fn(() => ({
    get: jest.fn(),
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
  })),
}));

const originalProxy = process.env.REACT_APP_USE_API_PROXY;
const originalBackend = process.env.REACT_APP_BACKEND_URL;
const originalRuntimeBackend = window.__BACKEND_URL__;

beforeEach(() => {
  delete process.env.REACT_APP_USE_API_PROXY;
  delete process.env.REACT_APP_BACKEND_URL;
  delete window.__BACKEND_URL__;
  jest.spyOn(console, 'log').mockImplementation(() => {});
});

afterEach(() => {
  for (const [key, value] of [['REACT_APP_USE_API_PROXY', originalProxy], ['REACT_APP_BACKEND_URL', originalBackend]]) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  if (originalRuntimeBackend === undefined) delete window.__BACKEND_URL__;
  else window.__BACKEND_URL__ = originalRuntimeBackend;
  jest.restoreAllMocks();
});

function loadClients() {
  let clients;
  jest.isolateModules(() => {
    const axios = require('axios');
    axios.create.mockClear();
    const admin = require('../admin/utils/api');
    const publicApi = require('../public/utils/api').default;
    clients = { axios, admin, publicApi };
  });
  return clients;
}

test.each([
  ['proxy', 'true', 'https://runtime.example', 'https://build.example', '/api'],
  ['runtime before build', 'false', 'https://runtime.example', 'https://build.example', 'https://runtime.example/api'],
  ['runtime without build', undefined, 'https://runtime.example', undefined, 'https://runtime.example/api'],
  ['build config', undefined, undefined, 'https://build.example', 'https://build.example/api'],
  ['browser fallback', undefined, undefined, undefined, `${window.location.protocol}//${window.location.hostname}:8001/api`],
  ['trailing slashes and path prefix', undefined, 'https://runtime.example/backend///', undefined, 'https://runtime.example/backend/api'],
])('admin and public clients share the %s API base', (_name, proxy, runtime, build, expected) => {
  if (proxy !== undefined) process.env.REACT_APP_USE_API_PROXY = proxy;
  if (runtime !== undefined) window.__BACKEND_URL__ = runtime;
  if (build !== undefined) process.env.REACT_APP_BACKEND_URL = build;
  const { axios, admin } = loadClients();
  expect(admin.API_BASE).toBe(expected);
  expect(axios.create).toHaveBeenCalledTimes(2);
  for (const [config] of axios.create.mock.calls) expect(config.baseURL).toBe(expected);
});

test('redirect lookup sends the original path through the configured public client', () => {
  window.__BACKEND_URL__ = 'https://runtime.example';
  const { axios, publicApi } = loadClients();
  const publicClient = axios.create.mock.results[1].value;
  const path = '/kvn/старый раздел.html';
  publicApi.lookupRedirect(path);
  expect(publicClient.get).toHaveBeenCalledWith('/redirects/lookup', { params: { path } });
});
