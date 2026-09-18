// Backend JSON — единственный редактируемый реестр; frontend получает точную копию.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'backend/models/module_contract.json'), 'utf8');
const target = path.join(root, 'frontend/src/moduleContract.json');
if (process.argv.includes('--check')) {
  if (JSON.stringify(JSON.parse(source)) !== JSON.stringify(JSON.parse(fs.readFileSync(target, 'utf8')))) {
    throw new Error('Реестры модулей расходятся. Запустите node scripts/sync-module-contract.cjs');
  }
} else {
  fs.writeFileSync(target, source);
}
