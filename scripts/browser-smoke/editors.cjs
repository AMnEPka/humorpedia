const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async function runEditorSmoke({ context, base, output, status }) {
  const baseUrl = new URL(base);
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(baseUrl.hostname));
  const live = await fetch(new URL('/__browser_smoke__/status', baseUrl)).then(response => response.json());
  assert.equal(live.run_id, process.env.SMOKE_RUN_ID);
  assert.equal(live.database, 'humorpedia_browser_test_' + live.run_id);
  assert.deepEqual(live, status);
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto('/admin');
    const token = await page.evaluate(() => localStorage.getItem('admin_token'));
    assert.ok(token);
    const api = async (route, method = 'GET', body) => {
      const response = await context.request.fetch(new URL('/api' + route, baseUrl).href, {
        method, headers: { Authorization: 'Bearer ' + token }, data: body,
      });
      const result = await response.json();
      assert.equal(response.status(), 200, route + ': ' + JSON.stringify(result));
      return result;
    };
    const keyboardMoveUp = async (handle, activeId, targetId) => {
      const announcement = text => page.getByRole('status').filter({ hasText: text });
      await handle.scrollIntoViewIfNeeded();
      await handle.focus();
      await handle.press('Space');
      // The initial collision confirms activation AND measured droppable geometry.
      // Sending ArrowUp immediately can run before the keyboard sensor is ready.
      await announcement('Draggable item ' + activeId + ' was moved over droppable area ' + activeId + '.').waitFor();
      await handle.press('ArrowUp');
      await announcement('Draggable item ' + activeId + ' was moved over droppable area ' + targetId + '.').waitFor();
      await handle.press('Space');
      await announcement('Draggable item ' + activeId + ' was dropped over droppable area ' + targetId).waitFor();
    };
    const save = async route => {
      const response = page.waitForResponse(item => item.request().method() === 'PUT' && item.url().includes('/api' + route));
      await page.getByRole('button', { name: 'Сохранить', exact: true }).click();
      const result = await response;
      assert.equal(result.status(), 200, await result.text());
      await page.getByText('Сохранено!', { exact: true }).waitFor();
    };

    // Only the chosen gallery caption changes. The standard editor, not a fixture renderer, saves it.
    const person = await api('/content/people/r9-person');
    const personId = person.id || person._id;
    const beforeModules = person.modules;
    const galleryIndex = beforeModules.findIndex(module => module.type === 'gallery');
    assert.ok(galleryIndex >= 0);
    await page.goto('/admin/people/' + personId);
    await page.getByRole('tab', { name: /^Модули/ }).click();
    await page.getByRole('button', { name: 'Редактировать блок Галерея', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Изображение 1: подпись', { exact: true }).fill('R10 изменённая подпись');
    await dialog.getByRole('button', { name: 'Сохранить', exact: true }).click();
    const personSave = page.waitForResponse(item => item.request().method() === 'PUT' && item.url().includes('/api/content/people/'));
    await page.getByTestId('save-btn').click();
    assert.equal((await personSave).status(), 200);
    const afterGallery = await api('/content/people/' + personId);
    const expectedModules = structuredClone(beforeModules);
    expectedModules[galleryIndex].data.images[0].caption = 'R10 изменённая подпись';
    assert.deepEqual(afterGallery.modules, expectedModules, 'A gallery edit changed unrelated module JSON');
    await page.reload();
    await page.getByRole('tab', { name: /^Модули/ }).click();
    await page.getByRole('button', { name: 'Редактировать блок Галерея', exact: true }).click();
    assert.equal(await page.getByLabel('Изображение 1: подпись', { exact: true }).inputValue(), 'R10 изменённая подпись');
    await page.getByRole('dialog').getByRole('button', { name: 'Сохранить', exact: true }).click();

    // Real dnd-kit keyboard sensor and the same serialized order as the pure operation.
    const drag = page.getByRole('button', { name: 'Переместить блок Галерея', exact: true });
    await keyboardMoveUp(drag, beforeModules[galleryIndex].id, beforeModules[galleryIndex - 1].id);
    const movedSave = page.waitForResponse(item => item.request().method() === 'PUT' && item.url().includes('/api/content/people/'));
    await page.getByTestId('save-btn').click();
    assert.equal((await movedSave).status(), 200);
    const afterDrag = await api('/content/people/' + personId);
    const expectedOrder = structuredClone(expectedModules);
    const [gallery] = expectedOrder.splice(galleryIndex, 1);
    expectedOrder.splice(galleryIndex - 1, 0, gallery);
    expectedOrder.forEach((module, order) => { module.order = order; });
    assert.deepEqual(afterDrag.modules, expectedOrder, 'Keyboard drag changed module data or missed its destination');
    await page.screenshot({ path: path.join(output, 'r10-module-editor.png'), fullPage: true });
    console.log('PASS: R10 module edit/save/reopen and real keyboard DnD preserve unrelated JSON');

    const league = await api('/content/kvn/vl-kvn');
    const participant = await api('/content/people/r8-person');
    const personRef = { person_id: participant.id || participant._id, slug: 'r8-person', name: 'R8 participant', custom_ref: 'keep' };
    const seasonPage = await api('/content/kvn', 'POST', {
      title: 'R10 сезон', name: 'R10 сезон', slug: 'r10-2032', parent_id: league.id || league._id, status: 'published',
      season_data: {
        league_name: 'R10 league', league_slug: 'vl-kvn', year: 2032, season_number: 2,
        all_teams: [personRef], winners: [personRef], hosts: ['R10 ведущий'], editors: ['R10 редактор'],
        intro_html: '<p>R10 вступление</p>', custom_season: { keep: true }, stages: [
          { name: 'R10 Этап', order: 1, comment: 'R10 комментарий', custom_stage: 'keep', games: [
            { id: 'r10-game', name: 'R10 Финал', order: 1, date: '2032-05-10', custom_game: { keep: true },
              contests: ['Приветствие', 'Разминка'], jury: ['R10 жюри'], notes: '<p>R10 игра</p>',
              teams: [{ ...personRef, team_name: 'R8 participant', team_slug: 'r8-person', place: 1,
                scores: { Приветствие: 4.5, Разминка: 5 }, total: 9.5, passed: true, is_winner: true, custom_result: 'keep' }],
            },
          ] },
          { name: 'R10 Другой этап', order: 2, games: [{ name: 'R10 другая игра', order: 1, contests: [], teams: [] }], custom_stage: 'second' },
        ],
      },
    });
    const pageId = seasonPage.id || seasonPage._id;
    const canonicalPath = '/competitions/seasons/by-page/' + pageId;
    const before = await api(canonicalPath);
    await page.goto('/admin/kvn/' + pageId);
    await page.getByRole('tab', { name: 'Сезон', exact: true }).click();
    // Existing destructive template confirmation is kept; cancellation must preserve the season.
    await page.getByRole('button', { name: 'Создать шаблон', exact: true }).click();
    await page.getByRole('alertdialog').getByRole('button', { name: 'Отмена', exact: true }).click();
    await page.getByRole('button', { name: 'Развернуть стадию R10 Этап', exact: true }).click();
    await page.getByRole('button', { name: 'Развернуть игру R10 Финал', exact: true }).click();
    const score = page.getByRole('textbox', { name: 'Баллы: R8 participant — Приветствие', exact: true });
    await score.fill('6.25'); await score.blur();
    await save('/competitions/seasons/' + before._id);
    const afterScore = await api(canonicalPath);
    const expected = structuredClone(before.editor_data);
    expected.stages[0].games[0].teams[0].scores.Приветствие = 6.25;
    expected.stages[0].games[0].teams[0].total = 11.25;
    assert.deepEqual(afterScore.editor_data, expected, 'A score edit lost unknown fields, IDs or unrelated season data');
    await page.reload();
    await page.getByRole('tab', { name: 'Сезон', exact: true }).click();
    await page.getByRole('button', { name: 'Развернуть стадию R10 Этап', exact: true }).click();
    await page.getByRole('button', { name: 'Развернуть игру R10 Финал', exact: true }).click();
    assert.equal(await page.getByRole('textbox', { name: 'Баллы: R8 participant — Приветствие', exact: true }).inputValue(), '6.25');

    // Move the source stage behind the destination, then copy its legacy-id game backwards.
    await page.getByRole('button', { name: 'Свернуть стадию R10 Этап', exact: true }).first().click();
    const stageDrag = page.getByRole('button', { name: 'Переместить стадию R10 Другой этап', exact: true });
    await keyboardMoveUp(stageDrag, 'stage-1', 'stage-0');
    await save('/competitions/seasons/' + before._id);
    const afterStageDrag = await api(canonicalPath);
    const expectedStageOrder = structuredClone(expected);
    expectedStageOrder.stages.reverse().forEach((stage, index) => { stage.order = index + 1; });
    assert.deepEqual(afterStageDrag.editor_data, expectedStageOrder, 'Stage keyboard drag changed season content');

    await page.reload(); await page.getByRole('tab', { name: 'Сезон', exact: true }).click();
    await page.getByRole('button', { name: 'Развернуть стадию R10 Этап', exact: true }).click();
    const gameHeader = page.getByRole('button', { name: 'Переместить игру R10 Финал', exact: true }).locator('..').locator('..');
    await gameHeader.getByRole('button').last().click();
    await page.getByRole('menuitem', { name: 'R10 Другой этап', exact: true }).first().click();
    await save('/competitions/seasons/' + before._id);
    const copied = await api(canonicalPath);
    const original = copied.editor_data.stages[1].games[0];
    const copy = copied.editor_data.stages[0].games[1];
    assert.equal(original._canonical_id, before.editor_data.stages[0].games[0]._canonical_id);
    assert.notEqual(copy._canonical_id, original._canonical_id);
    const copyPayload = { ...copy }; delete copyPayload._canonical_id; delete copyPayload.id; delete copyPayload.order;
    const originalPayload = { ...original, name: original.name + ' (копия)' }; delete originalPayload._canonical_id; delete originalPayload.id; delete originalPayload.order;
    assert.deepEqual(copyPayload, originalPayload, 'Game copy lost metadata or person references');
    // A second same-name copy is reordered before its saved predecessor, before saving.
    // Its missing sidecar must not steal the existing copy's canonical identity via name fallback.
    await page.reload(); await page.getByRole('tab', { name: 'Сезон', exact: true }).click();
    await page.getByRole('button', { name: 'Развернуть стадию R10 Этап', exact: true }).click();
    const originalHeader = page.getByRole('button', { name: 'Переместить игру R10 Финал', exact: true }).locator('..').locator('..');
    await originalHeader.getByRole('button').last().click();
    await page.getByRole('menuitem', { name: 'R10 Другой этап', exact: true }).first().click();
    await page.getByRole('button', { name: 'Развернуть стадию R10 Другой этап', exact: true }).click();
    const repeatedCopyDrag = page.getByRole('button', { name: 'Переместить игру R10 Финал (копия)', exact: true }).last();
    await keyboardMoveUp(repeatedCopyDrag, 'game-0-2', 'game-0-1');
    await save('/competitions/seasons/' + before._id);
    const repeated = await api(canonicalPath);
    const freshCopy = repeated.editor_data.stages[0].games[1];
    const savedCopy = repeated.editor_data.stages[0].games[2];
    assert.equal(savedCopy._canonical_id, copy._canonical_id);
    assert.notEqual(freshCopy._canonical_id, copy._canonical_id);
    assert.notEqual(freshCopy._canonical_id, original._canonical_id);
    assert.equal(repeated.editor_data.stages[1].games[0]._canonical_id, original._canonical_id);
    for (const game of [freshCopy, savedCopy]) {
      const payload = { ...game }; delete payload._canonical_id; delete payload.id; delete payload.order;
      assert.deepEqual(payload, originalPayload, 'Repeated copy lost metadata or participant references');
    }
    await page.screenshot({ path: path.join(output, 'r10-season-editor.png'), fullPage: true });
    assert.deepEqual(errors, []);
    console.log('PASS: R10 score save/reopen, stage keyboard DnD and backwards/repeated same-name game copies preserve identities/JSON');
  } catch (error) {
    await page.screenshot({ path: path.join(output, 'r10-editor-failure.png'), fullPage: true }).catch(() => {});
    throw error;
  } finally { await page.close(); }
};
