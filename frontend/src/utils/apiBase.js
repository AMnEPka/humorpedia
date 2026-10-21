/** Shared API routing: dev proxy, runtime config, build config, browser fallback. */
export function getApiBase() {
  if (process.env.REACT_APP_USE_API_PROXY === 'true') return '/api';

  const backendUrl = (typeof window !== 'undefined' && window.__BACKEND_URL__)
    || process.env.REACT_APP_BACKEND_URL
    || (typeof window !== 'undefined'
      ? `${window.location.protocol}//${window.location.hostname}:8001`
      : 'http://localhost:8001');
  return `${backendUrl.replace(/\/+$/, '')}/api`;
}
