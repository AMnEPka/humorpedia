const HEALTH_PATHS = new Set([
  '/health',
  '/health/simple',
  '/health/ready',
  '/health/live',
  '/health/errors',
  '/health/stats',
]);

function moduleKey(value) {
  if (typeof value !== 'string' || value.length === 0) return null;
  return value.replace(/[?#].*$/, '');
}

function sendJson(response, status, value) {
  response.statusCode = status;
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.end(JSON.stringify(value));
}

function formatError(payload) {
  const error = payload?.err ?? payload?.error ?? {};
  const moduleId = moduleKey(error.id) ?? moduleKey(error.loc?.file);
  const message = typeof error.message === 'string'
    ? error.message
    : String(error || 'Unknown Vite transform error');
  return {
    key: moduleId ?? `unmatched:${message}`,
    value: { moduleId, message },
  };
}

export default function devHealthPlugin() {
  const state = {
    listening: false,
    listeningSince: null,
    totalTransforms: 0,
    lastSuccessfulTransformAt: null,
    errors: new Map(),
  };

  function isReady() {
    return state.listening
      && state.totalTransforms > 0
      && state.errors.size === 0;
  }

  function simpleState() {
    if (state.errors.size > 0) return 'ERROR';
    return state.totalTransforms > 0 ? 'OK' : 'IDLE';
  }

  function healthMiddleware(request, response, next) {
    const pathname = new URL(request.url, 'http://vite.local').pathname;
    if (request.method !== 'GET' || !HEALTH_PATHS.has(pathname)) {
      next();
      return;
    }

    const now = Date.now();
    const uptimeSeconds = state.listeningSince
      ? Math.floor((now - state.listeningSince) / 1000)
      : 0;
    const errors = [...state.errors.values()];
    const simple = simpleState();
    const ready = isReady();

    switch (pathname) {
      case '/health':
        sendJson(response, 200, {
          status: state.errors.size ? 'unhealthy' : ready ? 'healthy' : 'starting',
          timestamp: new Date(now).toISOString(),
          uptime: { seconds: uptimeSeconds },
          vite: {
            state: state.errors.size ? 'error' : ready ? 'ready' : 'idle',
            listening: state.listening,
            ready,
            totalTransforms: state.totalTransforms,
            lastSuccessfulTransformAt: state.lastSuccessfulTransformAt,
            errorCount: errors.length,
          },
        });
        return;
      case '/health/simple':
        response.statusCode = simple === 'ERROR' ? 503 : 200;
        response.setHeader('Content-Type', 'text/plain; charset=utf-8');
        response.end(simple);
        return;
      case '/health/ready':
        sendJson(response, ready ? 200 : 503, {
          ready,
          state: simple.toLowerCase(),
          reason: ready ? null : state.errors.size
            ? 'Transform errors are present'
            : !state.listening
              ? 'Vite HTTP server is not listening'
              : 'No successful module transform has completed',
        });
        return;
      case '/health/live':
        sendJson(response, 200, { alive: true, timestamp: new Date(now).toISOString() });
        return;
      case '/health/errors':
        sendJson(response, 200, {
          errorCount: errors.length,
          errors,
          state: simple.toLowerCase(),
        });
        return;
      case '/health/stats':
        sendJson(response, 200, {
          totalTransforms: state.totalTransforms,
          lastSuccessfulTransformAt: state.lastSuccessfulTransformAt,
          serverUptimeSeconds: uptimeSeconds,
          listening: state.listening,
        });
        return;
      default:
        next();
    }
  }

  return {
    name: 'vite-health-check',
    apply: 'serve',
    enforce: 'post',
    configureServer(server) {
      const httpServer = server.httpServer;
      const markListening = () => {
        state.listening = true;
        state.listeningSince = Date.now();
      };
      if (httpServer?.listening) markListening();
      else httpServer?.once('listening', markListening);

      server.middlewares.use(healthMiddleware);

      const ws = server.ws;
      if (typeof ws?.send === 'function') {
        const originalSend = ws.send;
        const wrappedSend = function sendWithHealthTracking(payload, ...args) {
          const messages = Array.isArray(payload) ? payload : [payload];
          for (const message of messages) {
            if (message?.type === 'error' && (message.err || message.error)) {
              const { key, value } = formatError(message);
              state.errors.set(key, value);
            }
          }
          return originalSend.call(this, payload, ...args);
        };
        ws.send = wrappedSend;
        httpServer?.once('close', () => {
          if (ws.send === wrappedSend) ws.send = originalSend;
        });
      }
    },
    transform(_code, id) {
      state.totalTransforms += 1;
      state.lastSuccessfulTransformAt = new Date().toISOString();
      const key = moduleKey(id);
      if (key) state.errors.delete(key);
      return null;
    },
  };
}
