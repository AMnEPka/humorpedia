// craco.config.js
const path = require("path");
require("dotenv").config();

// Check if we're in development/preview mode (not production build)
// Craco sets NODE_ENV=development for start, NODE_ENV=production for build
const isDevServer = process.env.NODE_ENV !== "production";

// Environment variable overrides
const config = {
  enableHealthCheck: process.env.ENABLE_HEALTH_CHECK === "true",
  enableVisualEdits: isDevServer, // Only enable during dev server
};

// Conditionally load visual edits modules only in dev mode
let setupDevServer;
let babelMetadataPlugin;

if (config.enableVisualEdits) {
  setupDevServer = require("./plugins/visual-edits/dev-server-setup");
  babelMetadataPlugin = require("./plugins/visual-edits/babel-metadata-plugin");
}

// Conditionally load health check modules only if enabled
let WebpackHealthPlugin;
let setupHealthEndpoints;
let healthPluginInstance;

if (config.enableHealthCheck) {
  WebpackHealthPlugin = require("./plugins/health-check/webpack-health-plugin");
  setupHealthEndpoints = require("./plugins/health-check/health-endpoints");
  healthPluginInstance = new WebpackHealthPlugin();
}

const webpackConfig = {
  eslint: {
    configure: {
      extends: ["plugin:react-hooks/recommended"],
      rules: {
        "react-hooks/rules-of-hooks": "error",
        "react-hooks/exhaustive-deps": "warn",
      },
    },
  },
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig) => {
      const isDocker = process.env.DOCKER_ENV === 'true';
      
      // In Docker, use minimal file watching to prevent ENOMEM errors
      if (isDocker) {
        // Ignore everything - effectively disable file watching
        webpackConfig.watchOptions = {
          ignored: /./,  // Ignore all files
          poll: false,
          followSymlinks: false,
        };
      } else {
        // Local development - normal file watching
        webpackConfig.watchOptions = {
          ...webpackConfig.watchOptions,
          ignored: /node_modules|\.git|build|dist|coverage|public[\\/]media|backups|migration|\.cache|\.tmp|\.log$|\.swp$|\.swo$|\.DS_Store/,
          aggregateTimeout: 500,
          poll: false,
          followSymlinks: false,
        };
      }
      
      // Configure webpack to use less aggressive file watching
      // This helps prevent ENOMEM errors when there are many files
      if (!webpackConfig.snapshot) {
        webpackConfig.snapshot = {};
      }
      webpackConfig.snapshot.managedPaths = [
        path.resolve(__dirname, 'node_modules'),
      ];
      webpackConfig.snapshot.immutablePaths = [
        path.resolve(__dirname, 'node_modules'),
      ];

      // Optimize module resolution with caching
      if (!webpackConfig.resolve) {
        webpackConfig.resolve = {};
      }
      webpackConfig.resolve.unsafeCache = true;

      // Enable filesystem caching for faster rebuilds
      if (isDevServer) {
        webpackConfig.cache = {
          type: 'filesystem',
          buildDependencies: {
            config: [__filename],
          },
          cacheDirectory: path.resolve(__dirname, 'node_modules/.cache/webpack'),
        };
      }

      // Add health check plugin to webpack if enabled
      if (config.enableHealthCheck && healthPluginInstance) {
        webpackConfig.plugins.push(healthPluginInstance);
      }
      return webpackConfig;
    },
  },
};

// Only add babel metadata plugin during dev server
if (config.enableVisualEdits && babelMetadataPlugin) {
  webpackConfig.babel = {
    plugins: [babelMetadataPlugin],
  };
}

webpackConfig.devServer = (devServerConfig) => {
  // Note: public/media is excluded via volume in docker-compose.yml
  // This prevents webpack from scanning 3000+ images on startup
  // Media files are served by backend at /media/imported/*
  
  // In Docker, disable hot reload to prevent ENOMEM errors from inotify limits
  // Manual browser refresh required to see changes
  const isDocker = process.env.DOCKER_ENV === 'true';
  devServerConfig.hot = !isDocker;
  devServerConfig.liveReload = !isDocker;
  devServerConfig.client = {
    ...devServerConfig.client,
    webSocketURL: {
      hostname: 'localhost',
      pathname: '/ws',
      port: 3000,
    },
    overlay: {
      errors: true,
      warnings: false,
    },
  };
  
  // Proxy media requests to backend
  // Frontend makes requests to /media/imported/... which should go to backend
  // In Docker, use service name 'backend' for internal network communication
  // For client-side code, REACT_APP_BACKEND_URL is used (localhost:8001)
  const backendUrl = process.env.DOCKER_ENV === 'true'
    ? 'http://backend:8001'  // Docker internal network
    : (process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001');  // Local development
  
  if (!devServerConfig.proxy) {
    devServerConfig.proxy = [];
  }
  if (!Array.isArray(devServerConfig.proxy)) {
    devServerConfig.proxy = [devServerConfig.proxy];
  }
  
  // Add proxy for media files to backend
  devServerConfig.proxy.push({
    context: ['/media'],
    target: backendUrl,
    changeOrigin: true,
    secure: false,
    logLevel: 'debug',
  });
  
  // Add proxy for uploads to backend
  devServerConfig.proxy.push({
    context: ['/uploads'],
    target: backendUrl,
    changeOrigin: true,
    secure: false,
    logLevel: 'debug',
  });
  
  // Add proxy for images to backend
  devServerConfig.proxy.push({
    context: ['/images'],
    target: backendUrl,
    changeOrigin: true,
    secure: false,
    logLevel: 'debug',
  });

  // Apply visual edits dev server setup only if enabled
  if (config.enableVisualEdits && setupDevServer) {
    devServerConfig = setupDevServer(devServerConfig);
  }

  // Add health check endpoints if enabled
  if (config.enableHealthCheck && setupHealthEndpoints && healthPluginInstance) {
    const originalSetupMiddlewares = devServerConfig.setupMiddlewares;

    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      // Call original setup if exists
      if (originalSetupMiddlewares) {
        middlewares = originalSetupMiddlewares(middlewares, devServer);
      }

      // Setup health endpoints
      setupHealthEndpoints(devServer, healthPluginInstance);

      return middlewares;
    };
  }

  return devServerConfig;
};

module.exports = webpackConfig;
