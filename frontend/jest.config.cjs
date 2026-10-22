module.exports = {
  roots: ['<rootDir>/src'],
  testMatch: ['<rootDir>/src/**/__tests__/**/*.{js,jsx}', '<rootDir>/src/**/*.{spec,test}.{js,jsx}'],
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
  resetMocks: true,
  transform: {
    '^.+\\.(js|jsx|mjs|cjs)$': ['babel-jest', { presets: [
      ['@babel/preset-env', { targets: { node: 'current' } }],
      ['@babel/preset-react', { runtime: 'automatic' }],
    ] }],
  },
  transformIgnorePatterns: ["[/\\\\]node_modules[/\\\\].+\\.(js|jsx|mjs|cjs)$"],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '^react-router-dom$': '<rootDir>/node_modules/react-router-dom/dist/index.js',
    '^react-router$': '<rootDir>/node_modules/react-router/dist/development/index.js',
    '^react-router/dom$': '<rootDir>/node_modules/react-router/dist/development/dom-export.js',
    '\\.(css|less|scss|sass)$': '<rootDir>/tooling/style-mock.cjs',
    '\\.(gif|ttf|eot|svg|png|jpe?g|webp|woff2?)$': '<rootDir>/tooling/file-mock.cjs',
  },
  moduleFileExtensions: ['web.js', 'js', 'json', 'web.jsx', 'jsx', 'node'],
  collectCoverageFrom: ['src/**/*.{js,jsx}'],
};
