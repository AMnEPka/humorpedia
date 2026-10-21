const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

module.exports = async function runSeasonSmoke({ browser, context, base, output, status }) {
  const baseUrl = new URL(base.href || String(base));
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(baseUrl.hostname), 'Проверка сезона разрешена только на loopback');
  await fs.mkdir(output, { recursive: true });

  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));

  const browserStatus = async () => page.evaluate(async () => {
    const response = await fetch('/__browser_smoke__/status');
    return { status: response.status, body: await response.json() };
  });

  const api = async (token, route, method = 'GET', body) => page.evaluate(async ({ url, requestMethod, bearer, payload }) => {
    const response = await fetch(url, {
      method: requestMethod,
      headers: {
        Authorization: `Bearer ${bearer}`,
        ...(payload === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
    });
    const text = await response.text();
    let data;
    try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    return { status: response.status, data };
  }, {
    url: new URL(`/api${route}`, baseUrl).href,
    requestMethod: method,
    bearer: token,
    payload: body,
  });

  const requireOk = (result, action) => {
    assert.equal(result.status, 200, `${action}: HTTP ${result.status}: ${JSON.stringify(result.data)}`);
    return result.data;
  };

  try {
    await page.goto(new URL('/admin', baseUrl).href);
    const token = await page.evaluate(() => localStorage.getItem('admin_token'));
    assert.ok(token, 'В текущем browser context нет токена администратора');

    const statusResponse = await browserStatus();
    assert.equal(statusResponse.status, 200, 'Не удалось прочитать status browser-smoke');
    const liveStatus = statusResponse.body;
    assert.match(liveStatus.run_id || '', /^[0-9a-f]{32}$/);
    assert.equal(liveStatus.database, `humorpedia_browser_test_${liveStatus.run_id}`);
    assert.equal(liveStatus.run_id, process.env.SMOKE_RUN_ID, 'run_id сервера не совпадает с окружением smoke');
    if (process.env.DB_NAME) assert.equal(liveStatus.database, process.env.DB_NAME, 'Сервер смотрит не в ожидаемую тестовую БД');
    if (status) {
      assert.equal(liveStatus.run_id, status.run_id, 'Повторный status отличается от переданного run_id');
      assert.equal(liveStatus.database, status.database, 'Повторный status отличается от переданной БД');
    }

    const rootPage = requireOk(await api(token, '/content/kvn', 'POST', {
      title: 'КВН', name: 'КВН', slug: 'kvn', status: 'published',
    }), 'Создание корневой страницы КВН');
    const rootId = rootPage.id || rootPage._id;
    assert.ok(rootId, 'API не вернул ID корневой страницы КВН');

    const leaguePage = requireOk(await api(token, '/content/kvn', 'POST', {
      title: 'Высшая лига КВН', name: 'Высшая лига КВН', slug: 'vl-kvn',
      parent_id: rootId, status: 'published',
    }), 'Создание страницы лиги');
    const leagueId = leaguePage.id || leaguePage._id;
    assert.ok(leagueId, 'API не вернул ID лиги');

    const participant = requireOk(await api(token, '/content/people', 'POST', {
      title: 'R8 participant', full_name: 'R8 participant', slug: 'r8-person', status: 'published',
    }), 'Создание участника');
    const personId = participant.id || participant._id;
    assert.ok(personId, 'API не вернул ID участника');

    const personRef = { person_id: personId, name: 'R8 participant', slug: 'r8-person' };
    const seasonPage = requireOk(await api(token, '/content/kvn', 'POST', {
      title: 'Сезон 2027', name: 'Сезон 2027', slug: 'r8-2027',
      parent_id: leagueId, status: 'published',
      season_data: {
        year: 2027,
        league_slug: 'vl-kvn',
        all_teams: [personRef],
        winners: [personRef],
        jury: ['R8 participant'],
        stages: [
          {
            name: 'Проверочный финал', order: 1, comment: 'Исходный комментарий',
            games: [{
              id: 'r8-game', name: 'Проверочная игра',
              teams: [{
                person_id: personId, team_name: 'R8 participant', team_slug: 'r8-person',
                place: 1, total: 10, scores: {},
              }],
            }],
          },
          { name: 'Другой этап', order: 2, games: [] },
        ],
      },
    }), 'Создание страницы сезона');
    const pageId = seasonPage.id || seasonPage._id;
    assert.ok(pageId, 'API не вернул ID страницы сезона');

    const canonicalPath = `/competitions/seasons/by-page/${encodeURIComponent(pageId)}`;
    const initialSeason = requireOk(await api(token, canonicalPath), 'Чтение канонического сезона');
    assert.ok(initialSeason._id && initialSeason.updated_at, 'Канонический сезон не содержит версии');
    assert.equal(initialSeason.projection_status, 'ready');
    const initialPageVersion = initialSeason.page_updated_at;
    assert.ok(initialPageVersion, 'Канонический ответ не содержит версию страницы');
    const initialStageId = initialSeason.editor_data.stages[0]._canonical_id;
    const initialGameId = initialSeason.editor_data.stages[0].games[0]._canonical_id;
    assert.ok(initialStageId && initialGameId, 'Не получены sidecar ID стадии и игры');

    await page.goto(new URL(`/admin/kvn/${encodeURIComponent(pageId)}`, baseUrl).href);
    await page.getByRole('tab', { name: 'Сезон', exact: true }).click();
    await page.getByText('Проверочный финал', { exact: true }).locator('..').locator('..')
      .getByRole('button').nth(1).click();
    await page.locator('input[value="Проверочный финал"]').fill('Проверочный финал R8');
    await page.locator('textarea[placeholder="Краткий текст перед сеткой игр этой стадии"]')
      .fill('Комментарий после редактирования R8');
    const saveResponse = page.waitForResponse(response =>
      response.request().method() === 'PUT'
      && response.url().includes(`/api/competitions/seasons/${initialSeason._id}`));
    await page.getByRole('button', { name: 'Сохранить', exact: true }).click();
    assert.equal((await saveResponse).status(), 200, 'Сохранение canonical-сезона через UI не прошло');
    await page.getByText('Сохранено!', { exact: true }).waitFor();

    const afterUiSave = requireOk(await api(token, canonicalPath), 'Повторное чтение после UI save');
    assert.equal(afterUiSave.projection_status, 'ready');
    const editedStage = afterUiSave.editor_data.stages.find(stage => stage._canonical_id === initialStageId);
    assert.ok(editedStage, 'Потерян canonical ID стадии');
    assert.equal(editedStage.name, 'Проверочный финал R8');
    assert.equal(editedStage.comment, 'Комментарий после редактирования R8');
    assert.equal(editedStage.games[0]._canonical_id, initialGameId, 'Потерян canonical ID игры');
    assert.equal(editedStage.games[0].teams[0].person_id, personId, 'Потеряна person-ссылка игры');
    assert.ok(afterUiSave.editor_data.all_teams.some(item => item.person_id === personId), 'Потеряна person-ссылка all_teams');
    assert.ok(afterUiSave.editor_data.winners.some(item => item.person_id === personId), 'Потеряна person-ссылка winners');

    const reorderedData = {
      ...afterUiSave.editor_data,
      hosts: ['R8 ведущий'],
      editors: ['R8 редактор'],
      jury: ['R8 жюри'],
      stages: [...afterUiSave.editor_data.stages].reverse(),
    };
    const currentPage = requireOk(await api(token, `/content/kvn/${encodeURIComponent(pageId)}`), 'Чтение страницы перед API save');
    const afterApiSave = requireOk(await api(token, `/competitions/seasons/${afterUiSave._id}`, 'PUT', {
      expected_updated_at: afterUiSave.updated_at,
      expected_page_updated_at: currentPage.updated_at,
      editor_data: reorderedData,
      page_update: {},
    }), 'API сохранение с изменённым порядком и справочными полями');
    assert.equal(afterApiSave.projection_status, 'ready');
    assert.deepEqual(afterApiSave.editor_data.stages.map(stage => stage._canonical_id),
      [...reorderedData.stages.map(stage => stage._canonical_id)], 'API save изменил порядок стадий');
    assert.deepEqual(afterApiSave.editor_data.hosts, ['R8 ведущий']);
    assert.deepEqual(afterApiSave.editor_data.editors, ['R8 редактор']);
    assert.deepEqual(afterApiSave.editor_data.jury, ['R8 жюри']);

    const staleAttempt = await api(token, `/competitions/seasons/${afterApiSave._id}`, 'PUT', {
      expected_updated_at: afterUiSave.updated_at,
      expected_page_updated_at: currentPage.updated_at,
      editor_data: { ...reorderedData, hosts: ['Устаревшая запись'] },
      page_update: {},
    });
    assert.equal(staleAttempt.status, 409, `Устаревшее сохранение должно вернуть 409, пришло ${staleAttempt.status}`);
    const afterConflict = requireOk(await api(token, `/competitions/seasons/${afterApiSave._id}`), 'Проверка после stale 409');
    assert.deepEqual(afterConflict.editor_data.hosts, ['R8 ведущий'], 'Stale PUT перезаписал canonical-данные');

    const publicPage = await context.newPage();
    publicPage.setDefaultTimeout(20000);
    publicPage.on('pageerror', error => pageErrors.push(error.message));
    try {
      await publicPage.goto(new URL('/kvn/vl-kvn/r8-2027', baseUrl).href);
      await publicPage.getByText('Комментарий после редактирования R8', { exact: true }).waitFor();
      await publicPage.screenshot({ path: path.join(output, 'r8-public-season.png'), fullPage: true });
    } finally {
      await publicPage.close();
    }

    assert.deepEqual(pageErrors, [], 'В browser context возникли необработанные ошибки страницы');
    console.log('PASS: R8 season UI/API roundtrip, canonical IDs/person refs, stale 409, public projection');
  } catch (error) {
    await page.screenshot({ path: path.join(output, 'r8-season-failure.png'), fullPage: true }).catch(() => {});
    throw error;
  } finally {
    await page.close();
  }
};
