// Backend URL: use REACT_APP_BACKEND_URL (injected at build time) when available.
// Fallback to deriving from current page (host:8001) for local dev only.
(function() {
  // REACT_APP_BACKEND_URL is embedded by CRA at build time via process.env.
  // We do NOT override it here — api.js reads it directly from process.env.
  // This config.js only sets __BACKEND_URL__ as a last-resort fallback for localhost.
  if (typeof window.__BACKEND_URL__ === 'undefined') {
    var h = window.location.hostname;
    var p = window.location.protocol;
    if (h === 'localhost' || h === '127.0.0.1') {
      window.__BACKEND_URL__ = p + '//localhost:8001';
    }
    // For non-localhost environments, do NOT set __BACKEND_URL__
    // so that api.js correctly uses REACT_APP_BACKEND_URL from .env
  }
})();
