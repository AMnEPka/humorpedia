import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import legacy from '@vitejs/plugin-legacy';
import devHealthPlugin from './plugins/health-check/vite-health-plugin.mjs';

const root = fileURLToPath(new URL(".", import.meta.url));
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, root, '');
  const docker = env.DOCKER_ENV === 'true';
  const backend = docker ? 'http://backend:8001' : (env.REACT_APP_BACKEND_URL || 'http://localhost:8001');
  return {
    root,
    base: env.PUBLIC_URL || '/',
    plugins: [react(), legacy(), env.ENABLE_HEALTH_CHECK === "true" && devHealthPlugin()],
    resolve: { alias: { '@': path.join(root, 'src') } },
    // Preserve only CRA public variables used by the app; never inline the server environment.
    define: {
      'process.env.REACT_APP_BACKEND_URL': JSON.stringify(env.REACT_APP_BACKEND_URL || ''),
      'process.env.REACT_APP_USE_API_PROXY': JSON.stringify(env.REACT_APP_USE_API_PROXY || ''),
    },
    server: {
      host: docker ? '0.0.0.0' : 'localhost',
      port: Number(env.PORT || 3000),
      strictPort: true,
      hmr: { path: '/ws', ...(Number(env.WDS_SOCKET_PORT) > 0 ? { clientPort: Number(env.WDS_SOCKET_PORT) } : {}) },
      watch: {
        usePolling: docker || env.CHOKIDAR_USEPOLLING === 'true',
        interval: 1000,
        ignored: ['**/public/media/**', '**/build/**', '**/dist/**', '**/.cache/**', '**/.git/**', '**/coverage/**'],
      },
      proxy: Object.fromEntries(['/api', '/media', '/images', '/uploads'].map(prefix =>
        [prefix, { target: backend, changeOrigin: true, secure: false }])),
    },
    build: { outDir: env.BUILD_PATH || 'build', emptyOutDir: true },
  };
});
