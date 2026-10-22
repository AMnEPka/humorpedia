const hooks = require('eslint-plugin-react-hooks');
module.exports = [{
  files: ['src/**/*.{js,jsx}'],
  languageOptions: { ecmaVersion: 'latest', sourceType: 'module', parserOptions: { ecmaFeatures: { jsx: true } } },
  plugins: { 'react-hooks': hooks },
  rules: hooks.configs.recommended.rules,
}];
