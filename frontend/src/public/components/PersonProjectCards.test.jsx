import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';

jest.mock('../utils/api', () => ({
  __esModule: true,
  default: { getPersonCareer: jest.fn() },
  publicApi: { getPersonShows: jest.fn() },
}));

import { PersonCareerContent, kvnCareerTeams } from './competitions/PersonCareer';
import { ShowAppearancesCard } from './ShowAppearances';

test('person career keeps only KVN teams and hides season and year labels', () => {
  const teams = [
    {
      membership: { _id: 'kvn', roles: ['капитан'], from_year: 2015 },
      team: { name: 'Экскурсия по городу', slug: 'ekskursiya', show_id: null },
      seasons: [{ _id: 'season', season_year: 2016 }],
    },
    {
      membership: { _id: 'show', roles: [] },
      team: { name: 'Фантастические', slug: 'fantasticheskie', show_id: 'improv' },
      seasons: [],
    },
  ];

  const kvnTeams = kvnCareerTeams(teams);
  const html = renderToStaticMarkup(
    <MemoryRouter><PersonCareerContent teams={kvnTeams} roleGroups={[]} /></MemoryRouter>
  );

  expect(kvnTeams).toHaveLength(1);
  expect(html).toContain('Команды КВН');
  expect(html).toContain('Экскурсия по городу');
  expect(html).toContain('капитан');
  expect(html).not.toContain('Фантастические');
  expect(html).not.toContain('2015');
  expect(html).not.toContain('2016');
});

test('project card uses the selected target for individual and team entries', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <ShowAppearancesCard items={[
        {
          id: 'team',
          caption: 'Участник проекта «Импровизация. Команды» в составе команды «Фантастические»',
          show_url: '/shows/improv-teams',
          link_url: '/shows/improv-teams/teams/fantasticheskie',
        },
        {
          id: 'person',
          caption: 'Победитель проекта «Рассмеши комика»',
          show_url: '/shows/rassmeshi-komika',
          link_url: '/shows/rassmeshi-komika',
        },
      ]} />
    </MemoryRouter>
  );

  expect(html).toContain('Участие в других проектах');
  expect(html).toContain('href="/shows/improv-teams/teams/fantasticheskie"');
  expect(html).toContain('href="/shows/rassmeshi-komika"');
});
