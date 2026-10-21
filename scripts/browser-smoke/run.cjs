// Реальные browser/API запросы; моков transport и DOM здесь нет.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { setTimeout: pause } = require('node:timers/promises');
const { chromium } = require('playwright');

async function main() {
  const base = new URL(process.env.SMOKE_BASE_URL || 'http://127.0.0.1:18001');
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname), 'Smoke работает только на loopback');
  let status;
  for (let attempt = 0; attempt < 60; attempt++) {
    try {
      status = await fetch(new URL('/__browser_smoke__/status', base), { signal: AbortSignal.timeout(1000) }).then(r => r.json());
      break;
    } catch (error) {
      if (attempt === 59) throw error;
      await pause(500);
    }
  }
  assert.match(status.run_id, /^[0-9a-f]{32}$/);
  assert.equal(status.database, 'humorpedia_browser_test_' + status.run_id);
  assert.equal(status.run_id, process.env.SMOKE_RUN_ID, 'Не совпал идентификатор тестового сервера');
  const output = process.env.SMOKE_ARTIFACT_DIR || await fs.mkdtemp(path.join(os.tmpdir(), 'humorpedia-browser-result-'));
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, ...(process.env.SMOKE_BROWSER_CHANNEL ? { channel: process.env.SMOKE_BROWSER_CHANNEL } : {}) });
  let page;
  const browserErrors = [];
  const slug = 'browser-smoke-' + status.run_id;
  const title = 'Браузерная проверка ' + status.run_id.slice(0, 8);
  try {
    const context = await browser.newContext({ baseURL: base.href, acceptDownloads: true });
    context.on('page', tab => tab.on('pageerror', error => browserErrors.push(error.message)));
    page = await context.newPage();
    page.setDefaultTimeout(20000);
    await page.goto('/admin/login');
    await page.getByTestId('login-email').fill('browser@example.invalid');
    await page.getByTestId('login-password').fill('Browser-smoke-only-2026');
    await page.getByTestId('login-submit').click();
    await page.waitForURL(/\/admin\/?$/);
    await page.goto('/admin/page-builder/new');
    await page.getByLabel('Имя или название', { exact: true }).fill(title);
    await page.getByRole('button', { name: 'Создать заготовку', exact: true }).click();
    await page.getByLabel('Заголовок страницы', { exact: true }).fill(title);
    await page.getByLabel('Адрес (slug)', { exact: false }).fill(slug);
    await page.getByLabel('Полное имя', { exact: true }).fill(title);
    await page.getByRole('button', { name: 'Предпросмотр страницы', exact: true }).click();
    await page.frameLocator('iframe[title="Предпросмотр страницы: компьютер"]').getByRole('heading', { name: title, exact: true }).waitFor();
    await page.getByLabel('Я проверил итоговую страницу вручную', { exact: true }).check();
    const downloaded = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Скачать пакет страницы', exact: true }).click();
    const archive = path.join(output, 'page.zip');
    await (await downloaded).saveAs(archive);
    assert.equal((await fetch(new URL('/api/content/people/' + slug, base))).status, 404, 'Экспорт не должен публиковать страницу');
    console.log('PASS: вход, редактура заготовки, preview и ZIP export');

    await page.goto('/admin/page-import');
    await page.locator('input[type=file]').setInputFiles(archive);
    await page.getByRole('button', { name: 'Проверить архив', exact: true }).click();
    await page.getByRole('heading', { name: 'Проверка пакета', exact: true }).waitFor();
    assert.equal((await fetch(new URL('/api/content/people/' + slug, base))).status, 404, 'Preflight не должен публиковать страницу');
    await page.getByLabel('Я проверил страницу и связи', { exact: true }).check();
    await page.getByRole('button', { name: 'Создать и опубликовать', exact: true }).click();
    await page.getByRole('heading', { name: 'Страница импортирована', exact: true }).waitFor();
    await page.getByRole('link', { name: 'Открыть редактор страницы', exact: true }).click();
    const editedTitle = title + ' после редактуры';
    await page.getByTestId('title-input').fill(editedTitle);
    const saved = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().includes('/api/content/people/'));
    await page.getByTestId('save-btn').click();
    assert.equal((await saved).status(), 200);
    await page.reload();
    await page.getByTestId('title-input').waitFor();
    assert.equal(await page.getByTestId('title-input').inputValue(), editedTitle);
    const popup = page.waitForEvent('popup');
    await page.getByRole('button', { name: 'Предпросмотр', exact: true }).click();
    const preview = await popup;
    await preview.getByRole('heading', { name: editedTitle, exact: true }).waitFor();
    await preview.close();
    console.log('PASS: ZIP preflight, apply, обычная форма, сохранение и публичный preview');

    const anonymous = await browser.newContext({ baseURL: base.href });
    const publicPage = await anonymous.newPage();
    publicPage.on('pageerror', error => browserErrors.push(error.message));
    await publicPage.goto('/search?q=' + encodeURIComponent(title));
    const card = publicPage.locator('a[href="/people/' + slug + '"]').first();
    await card.waitFor();
    await card.click();
    await publicPage.waitForURL('**/people/' + slug);
    await publicPage.getByRole('heading', { name: editedTitle, exact: true }).waitFor();
    await publicPage.screenshot({ path: path.join(output, 'public-page.png'), fullPage: true });
    await publicPage.goBack();
    await publicPage.waitForURL('**/search?**');
    await publicPage.locator('a[href="/people/' + slug + '"]').first().waitFor();
    await anonymous.close();
    assert.deepEqual(browserErrors, [], 'В браузере возникли необработанные ошибки');
    console.log('PASS: анонимный поиск, карточка и возврат назад');
    console.log('Browser smoke passed; artifacts: ' + output);
  } catch (error) {
    await page?.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {});
    throw error;
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
