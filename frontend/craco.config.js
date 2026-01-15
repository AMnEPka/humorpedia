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
      // Critical: Exclude large media directory from file watching
      // This prevents webpack from scanning 3000+ image files on startup
      const publicMediaPath = path.resolve(__dirname, 'public/media');
      const publicPath = path.resolve(__dirname, 'public');
      
      // Build comprehensive ignore list to prevent ENOMEM errors
      const ignoredPatterns = [
        '**/node_modules/**',
        '**/.git/**',
        '**/build/**',
        '**/dist/**',
        '**/coverage/**',
        // Explicitly exclude the large media directory
        publicMediaPath,
        '**/public/media/**',
        // Exclude all image files in public folder
        '**/public/**/*.jpg',
        '**/public/**/*.jpeg',
        '**/public/**/*.png',
        '**/public/**/*.gif',
        '**/public/**/*.webp',
        '**/public/**/*.svg',
        '**/public/**/*.ico',
        '**/public/**/*.bmp',
        // Exclude entire public directory from watchpack initial scan
        // Only watch public/index.html and public/manifest.json if needed
        /^[\\/]?public[\\/](?!index\.html|manifest\.json|robots\.txt)/,
        // Exclude cache and temp directories
        '**/.cache/**',
        '**/.tmp/**',
        '**/tmp/**',
        '**/*.log',
        '**/*.swp',
        '**/*.swo',
        '**/.DS_Store',
        // Exclude backup and migration directories if they exist
        '**/backups/**',
        '**/migration/**',
      ];
      
      // Configure watchpack to ignore large directories
      // This is critical to prevent ENOMEM errors when scanning thousands of files
      webpackConfig.watchOptions = {
        ...webpackConfig.watchOptions,
        ignored: [
          ...ignoredPatterns,
          // Additional patterns for watchpack
          /node_modules/,
          /\.git/,
          /build/,
          /dist/,
          /coverage/,
          // Exclude entire public directory - it's served separately
          // Only essential files (index.html, manifest.json) are needed
          (filePath) => {
            try {
              // Convert to normalized path for comparison
              const normalizedPath = path.normalize(filePath);
              const publicDir = path.normalize('public');
              
              // Exclude public directory except essential files
              if (normalizedPath.includes(publicDir)) {
                const relativePath = path.relative(
                  path.resolve(__dirname, publicDir),
                  normalizedPath
                );
                const fileName = path.basename(normalizedPath);
                // Only allow index.html, manifest.json, robots.txt in public root
                if (relativePath === fileName) {
                  return !['index.html', 'manifest.json', 'robots.txt'].includes(fileName);
                }
                // Exclude all subdirectories and files in public
                return true;
              }
              return false;
            } catch (e) {
              // If path comparison fails, exclude by default
              return false;
            }
          },
        ],
        aggregateTimeout: 500,
        // Use polling in Docker for better file change detection, but with longer interval
        // Longer interval reduces file descriptor usage
        poll: process.env.CHOKIDAR_USEPOLLING === 'true' ? 3000 : false,
        // Limit the number of files watched to prevent ENOMEM errors
        followSymlinks: false,
      };
      
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
      
      // Exclude public directory from snapshot to prevent initial scan
      if (!webpackConfig.snapshot.ignored) {
        webpackConfig.snapshot.ignored = [];
      }
      webpackConfig.snapshot.ignored.push(
        /public[\\/](?!index\.html|manifest\.json|robots\.txt)/
      );

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
  
  // Enable Hot Module Replacement (HMR) for fast development
  devServerConfig.hot = true;
  devServerConfig.liveReload = true;
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
