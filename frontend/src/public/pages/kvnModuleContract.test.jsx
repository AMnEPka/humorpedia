/** @jest-environment node */

import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { LeagueSeasonsPage } from './SectionDetailPage';

jest.mock('../utils/api', () => ({ __esModule: true, default: {}, publicApi: {} }));
jest.mock('../utils/teamStorage', () => ({ teamStorage: {} }));

const seasons = [{
  id: 'season-2020', slug: 'vl-2020', full_path: 'kvn/vl-kvn/vl-2020',
  season_data: { year: 2020, winners: ['Команда-чемпион'] },
}];

const renderLeague = (modules) => renderToStaticMarkup(
  <MemoryRouter>
    <LeagueSeasonsPage section={{ modules }} seasons={seasons} leagueSlug="vl-kvn" />
  </MemoryRouter>
);

test.each(['first_league_champions', 'vl_league_champions'])(
  'league respects hidden %s marker without restoring it through the automatic fallback', (type) => {
    const html = renderLeague([
      { id: 'hidden', type, visible: false, title: 'Скрытая таблица', data: {} },
      { id: 'intro', type: 'text_block', data: { content: '<b>Описание лиги</b>' } },
    ]);
    expect(html).not.toContain('Скрытая таблица');
    expect(html).not.toContain('<table');
    expect(html).toContain('<b>Описание лиги</b>');
    expect(html).toContain('Все сезоны');
  }
);

test('a hidden legacy text champions marker also suppresses the automatic table', () => {
  const html = renderLeague([
    { id: 'legacy', type: 'text_block', visible: false, data: { title: 'Чемпионы', content: '<p>Скрытый текст</p>' } },
  ]);
  expect(html).not.toContain('<table');
  expect(html).not.toContain('Скрытый текст');
});

test('a league without a champions marker retains its automatic champions table', () => {
  const html = renderLeague([]);
  expect(html).toContain('<table');
  expect(html).toContain('Команда-чемпион');
  expect(html).toContain('Чемпионы Высшей лиги КВН');
});

test('a visible champions marker controls its title and position among content modules', () => {
  const html = renderLeague([
    { id: 'after', type: 'quote', order: 3, data: { text: 'После чемпионов' } },
    { id: 'champions', type: 'vl_league_champions', order: 2, title: 'Победители турнира', data: {} },
    { id: 'before', type: 'text_block', order: 1, data: { content: '<b>Перед чемпионами</b>' } },
  ]);
  expect(html).toContain('Победители турнира');
  expect(html).toContain('Команда-чемпион');
  expect(html.indexOf('Перед чемпионами')).toBeLessThan(html.indexOf('Победители турнира'));
  expect(html.indexOf('Победители турнира')).toBeLessThan(html.indexOf('После чемпионов'));
  expect((html.match(/<table/g) || []).length).toBe(1);
});
