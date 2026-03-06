// Backend URL: always derive from current page (host:8001)
(function() {
  var h = window.location.hostname;
  var p = window.location.protocol;
  window.__BACKEND_URL__ = (h === 'localhost' || h === '127.0.0.1')
    ? p + '//localhost:8001'
    : p + '//' + h + ':8001';
})();
