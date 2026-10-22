import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { renderGatewayConfigs } from './public-html-gateway.mjs';
const options={releaseId:'a'.repeat(64),backendOrigin:'http://backend:8001'};
test('disabled config preserves original SPA and API upload limits', () => {
  const {disabled}=renderGatewayConfigs(options);
  assert.match(disabled,/client_max_body_size 20m/);
  assert.match(disabled,/location = \/api\/page-packages\/preview[\s\S]*?client_max_body_size 52m/);
  assert.match(disabled,/proxy_read_timeout 120s/);
  assert.doesNotMatch(disabled,/public-html\/dispatch|people\|articles/);
  assert.match(disabled,/try_files \$uri \$uri\/ \/index.html/);
});
test('enabled proxy and sentinel are scoped', () => {
  for (const mode of ['enabled_noindex','enabled_index']) {
    const config=renderGatewayConfigs(options)[mode];
    assert.match(config,/proxy_intercept_errors off/);
    assert.match(config,/X-Humorpedia-Release "[a-f0-9]{64}"/);
    assert.match(config,/X-Humorpedia-Original-URI \$request_uri/);
    assert.match(config,/location @legacy[\s\S]*?error_page 418 = @spa/);
    assert.equal((config.match(/proxy_intercept_errors on/g)||[]).length,1);
    assert.doesNotMatch(config,/error_page 404/);
    assert.match(config,/location.*_internal.*return 404/);
  }
});
test('rejects backend config injection', () => {
  for (const backendOrigin of ['https://backend:8001','http://u:p@backend:8001','http://backend:8001/x','http://backend:8001;\nfoo','http://backend:8001?x']) {
    assert.throws(()=>renderGatewayConfigs({...options,backendOrigin}));
  }
  assert.throws(()=>renderGatewayConfigs({...options,releaseId:'bad'}));
});
test('release context excludes secrets snapshots and media', async () => {
  const ignore=await readFile(new URL('../../Dockerfile.public-html.dockerignore',import.meta.url),'utf8');
  for (const value of ['**/.env*','**/uploads/**','**/media/**','**/backups/**','**/node_modules/**']) assert.ok(ignore.includes(value));
  assert.ok(ignore.startsWith('**'));
  const docker=await readFile(new URL('../../Dockerfile.public-html',import.meta.url),'utf8');
  assert.match(docker,/COPY --from=public_html_release/);
  assert.doesNotMatch(docker,/yarn build|npm install|mongo.*tools/);
});
