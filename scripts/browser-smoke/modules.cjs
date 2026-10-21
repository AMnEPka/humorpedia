const assert = require('node:assert/strict');
const path = require('node:path');
const { setTimeout: pause } = require('node:timers/promises');

// Real public pages and the actual constructor iframe, on the owned smoke database.
module.exports = async function runModuleSmoke({ browser, context, base, output, status }) {
  const baseUrl = new URL(base);
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(baseUrl.hostname));
  const response = await fetch(new URL('/__browser_smoke__/status', baseUrl));
  const live = await response.json();
  assert.equal(live.run_id, process.env.SMOKE_RUN_ID);
  assert.equal(live.database, 'humorpedia_browser_test_' + live.run_id);
  assert.deepEqual(live, status);

  const editor = await context.newPage();
  editor.setDefaultTimeout(20000);
  await editor.goto('/admin');
  const token = await editor.evaluate(() => localStorage.getItem('admin_token'));
  assert.ok(token);
  const api = async (route, method, body) => {
    const result = await context.request.fetch(new URL('/api' + route, baseUrl).href, {
      method, headers: { Authorization: 'Bearer ' + token }, data: body,
    });
    const data = await result.json();
    assert.equal(result.status(), 200, route + ': ' + JSON.stringify(data));
    return data;
  };
  const anonymous = await browser.newContext({ baseURL: baseUrl.href });
  const page = await anonymous.newPage();
  page.setDefaultTimeout(20000);
  const errors = [];
  editor.on('pageerror', error => errors.push(error.message));
  page.on('pageerror', error => errors.push(error.message));
  const block = (id, type, order, data, extra = {}) => ({ id, type, order, data, ...extra });
  const image = '/__browser_smoke__/image.png';

  async function checkEntity(scope, kind, preview) {
    await scope.getByRole('heading', { level: 1, name: 'R9 ' + kind, exact: true }).waitFor();
    await scope.getByText('R9 cell ' + kind, { exact: true }).waitFor();
    assert.equal(await scope.getByText('R9 text A ' + kind, { exact: true }).count(), 1);
    assert.equal(await scope.getByText('R9 text B ' + kind, { exact: true }).count(), 1);
    assert.equal(await scope.getByText('R9 hidden ' + kind, { exact: true }).count(), 0);
    assert.equal(await scope.getByText('R9 gallery ' + kind, { exact: true }).count(), 1);
    assert.equal(await scope.getByText('R9 cell ' + kind, { exact: true }).count(), 1);
    await scope.waitForFunction(alt => {
      const img = Array.from(document.images).find(item => item.alt === alt);
      return img?.complete && img.naturalWidth > 0;
    }, 'R9 picture ' + kind);
    assert.equal(await scope.getByText('R9 fact ' + kind, { exact: true }).count(), 1);
    const order = await scope.evaluate(() => {
      const text = document.body.textContent;
      return [text.indexOf('R9 text A'), text.indexOf('R9 text B'), text.indexOf('R9 quote')];
    });
    assert.ok(order[0] < order[1] && order[1] < order[2], kind + ': content order changed');
    if (preview) assert.equal(await scope.getByText('Оценка', { exact: true }).count(), 0);
    if (!preview) {
      assert.equal(await scope.getByRole('heading', { name: 'R9 video ' + kind, exact: true }).count(), 1);
      assert.equal(await scope.locator('a[href="https://example.invalid/r9-video"]').count(), 1);
    }
    if (kind === 'show') {
      assert.equal(await scope.getByText('R9 participant', { exact: true }).count(), 1);
      const details = scope.locator('details').filter({ hasText: 'R9 collapsed' });
      await details.locator('summary').click();
      await scope.getByText('R9 folded body', { exact: true }).waitFor();
      await details.locator('summary').click();
    }
    if (kind === 'person' || kind === 'team') {
      const target = kind === 'person' ? 'timeline-2-event-0' : 'section-text-b';
      assert.equal(await scope.locator('[id="' + target + '"]').count(), 1, 'TOC target is unique');
      const button = kind === 'person'
        ? scope.getByRole('button', { name: /2031.*R9 event/ })
        : scope.getByRole('button', { name: 'R9 title B', exact: true });
      await scope.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
      await button.click();
      // The preview intentionally forbids scripts. Chromium can suppress the
      // frame's rAF callbacks, so poll from Node instead of waitForFunction(rAF).
      const deadline = Date.now() + 5000;
      let geometry;
      do {
        geometry = await scope.evaluate(id => {
          const rect = document.getElementById(id)?.getBoundingClientRect();
          return { top: rect?.top, bottom: rect?.bottom, viewport: document.documentElement.clientHeight };
        }, target);
        if (geometry.top >= -1 && geometry.bottom <= geometry.viewport + 1) break;
        await pause(50);
      } while (Date.now() < deadline);
      assert.ok(geometry.top >= -1 && geometry.bottom <= geometry.viewport + 1,
        'TOC did not reveal ' + target + ': ' + JSON.stringify(geometry));
    }
    const layout = await scope.evaluate(() => ({
      width: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }));
    assert.ok(layout.scroll <= layout.width + 1, kind + ': horizontal overflow ' + JSON.stringify(layout));
  }

  try {
    for (const kind of ['person', 'team', 'show']) {
      const modules = [
        block('quote', 'quote', 80, { text: 'R9 quote ' + kind }),
        block('text-b', 'text_block', 30, { title: 'R9 title B', content: '<p>R9 text B ' + kind + '</p>' }),
        block('hidden', 'text_block', -1, { content: 'R9 hidden ' + kind }, { visible: false }),
        block('facts', 'facts_table', 0, {}),
        block('rating', 'rating_widget', 0, {}),
        block('timeline', 'timeline', 40, { title: 'R9 timeline', events: [
          { year: '2031', title: 'R9 event', description: '<b>R9 chronology</b>' },
        ] }),
        block('gallery', 'gallery', 50, { title: 'R9 gallery ' + kind, images: [{ url: image, caption: 'R9 picture ' + kind }] }),
        block('text-a', 'text_block', 10, { title: 'R9 title A', content: '<p>R9 text A ' + kind + '</p>' }),
        block('table', 'table', 55, { title: 'R9 table', headers: ['R9 column'], rows: [['R9 cell ' + kind]], hasHeaders: true }),
      ];
      if (kind === 'show') modules.push(
        block('participants', 'participants', 70, { items: [{ name: 'R9 participant', person_url: '/people/r9-person', photo: image }] }),
        block('folded', 'text_block', 75, { title: 'R9 collapsed', content: '<p>R9 folded body</p>', collapsed: true }),
      );
      const content = {
        title: 'R9 ' + kind, slug: 'r9-' + kind, [kind === 'person' ? 'full_name' : 'name']: 'R9 ' + kind,
        facts: { 'Контрольный факт': 'R9 fact ' + kind }, facts_order: ['Контрольный факт'], modules,
      };
      const collection = { person: 'people', team: 'teams', show: 'shows' }[kind];
      await api('/content/' + collection, 'POST', { ...content, status: 'published', modules: [
        ...modules, block('video', 'video', 60, { title: 'R9 video ' + kind, url: 'https://example.invalid/r9-video' }),
      ] });
      const publicPath = { person: '/people/', team: '/kvn/teams/', show: '/shows/' }[kind] + content.slug;
      const draft = await api('/page-builder/drafts', 'POST', { kind, materials: { name: content.title } });
      await api('/page-builder/drafts/' + draft.id, 'PUT', {
        revision: draft.revision, materials: draft.materials, page: content, relations: [],
      });
      for (const width of [390, 1120]) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(publicPath, { waitUntil: 'domcontentloaded' });
        await checkEntity(page, kind, false);
        await page.screenshot({ path: path.join(output, 'r9-public-' + kind + '-' + width + '.png'), fullPage: true });
      }
      await editor.goto('/admin/page-builder/' + draft.id);
      const previewRequests = [];
      const recordRequest = request => {
        if (/\/api\/(ratings|polls|random)\//.test(request.url())) previewRequests.push(request.url());
      };
      editor.on('request', recordRequest);
      try {
        await editor.getByRole('button', { name: 'Предпросмотр страницы', exact: true }).click();
        for (const width of [390, 1120]) {
          await editor.getByRole('button', { name: width === 390 ? 'Телефон' : 'Компьютер', exact: true }).click();
          const handle = await editor.locator('iframe[title^="Предпросмотр страницы:"]').elementHandle();
          const frame = await handle.contentFrame();
          await frame.waitForFunction(expected => window.innerWidth === expected, width);
          await checkEntity(frame, kind, true);
          await editor.locator('iframe[title^="Предпросмотр страницы:"]').screenshot({
            path: path.join(output, 'r9-preview-' + kind + '-' + width + '.png'),
          });
        }
        assert.deepEqual(previewRequests, [], 'Preview must not request ratings, polls or random content');
      } finally { editor.off('request', recordRequest); }
      console.log('PASS: R9 ' + kind + ' public + constructor preview at 390/1120');
    }

    // R8 creates the canonical season. Adding an archive module must not render it beside season_data.
    const season = await api('/content/kvn/r8-2027', 'GET');
    await api('/content/kvn/' + (season.id || season._id), 'PUT', {
      expected_updated_at: season.updated_at,
      modules: [block('archive', 'text_block', 0, { content: 'R9 archived season text' })],
    });
    await api('/content/quizzes', 'POST', {
      title: 'R9 quiz', slug: 'r9-quiz', status: 'published', modules: [
        block('after', 'quote', 2, { text: 'R9 quiz after' }),
        block('questions', 'quiz_questions', 0, { questions: [{
          question: 'R9 question', type: 'single', options: [{ text: 'R9 correct', correct: true }, { text: 'R9 wrong' }],
        }] }),
        block('results', 'quiz_results', 0, { results: [{ min_score: 0, max_score: 1, title: 'R9 result' }] }),
        block('intro', 'text_block', 1, { title: 'R9 quiz intro', content: '<p>R9 quiz before</p>' }),
        block('hidden', 'text_block', 0, { content: 'R9 quiz hidden' }, { visible: false }),
      ],
    });
    for (const width of [390, 1120]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto('/kvn/vl-kvn/r8-2027');
      await page.getByText('Комментарий после редактирования R8', { exact: true }).waitFor();
      assert.equal(await page.getByText('R9 archived season text', { exact: true }).count(), 0);
      await page.screenshot({ path: path.join(output, 'r9-season-' + width + '.png'), fullPage: true });
      await page.goto('/quizzes/r9-quiz');
      await page.getByRole('heading', { name: 'R9 quiz intro', exact: true }).waitFor();
      assert.equal(await page.getByText('R9 question', { exact: true }).count(), 0);
      assert.equal(await page.getByText('R9 result', { exact: true }).count(), 0);
      assert.equal(await page.getByText('R9 quiz hidden', { exact: true }).count(), 0);
      assert.ok(await page.evaluate(() => document.body.textContent.indexOf('R9 quiz before') < document.body.textContent.indexOf('R9 quiz after')));
      await page.getByRole('button', { name: 'Начать квиз' }).click();
      await page.getByRole('button', { name: /R9 correct/ }).click();
      await page.getByRole('button', { name: 'Завершить' }).click();
      await page.getByText('R9 result', { exact: true }).waitFor();
      await page.screenshot({ path: path.join(output, 'r9-quiz-' + width + '.png'), fullPage: true });
    }
    assert.deepEqual(errors, []);
    console.log('PASS: R9 season archive isolation and quiz gameplay at 390/1120');
  } catch (error) {
    await editor.screenshot({ path: path.join(output, 'r9-editor-failure.png'), fullPage: true }).catch(() => {});
    await page.screenshot({ path: path.join(output, 'r9-public-failure.png'), fullPage: true }).catch(() => {});
    throw error;
  } finally {
    await editor.close();
    await anonymous.close();
  }
};
