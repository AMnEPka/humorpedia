/** @jest-environment node */

import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import CitiesListPage from './CitiesListPage';
import PeopleListPage from './PeopleListPage';
import TeamsListPage from './TeamsListPage';
import ShowsListPage from './ShowsListPage';

jest.mock('../utils/api', () => ({
  __esModule: true,
  default: {
    getCities: jest.fn(),
    getPeople: jest.fn(),
    getTeamsByCategory: jest.fn(),
    getShows: jest.fn(),
  },
}));

const renderPage = (Page, path) => renderToStaticMarkup(
  <MemoryRouter initialEntries={[path]}>
    <Page />
  </MemoryRouter>
);

test('geography provides both text and alphabet search', () => {
  const html = renderPage(CitiesListPage, '/city');

  expect(html).toContain('href="/"');
  expect(html).toContain('>Главная</a>');
  expect(html).toContain('<li class="text-gray-900">География</li>');
  expect(html).toContain('placeholder="Поиск города..."');
  expect(html).toContain('aria-label="Фильтр по первой букве"');
});

test('geography keeps legacy search URLs readable', () => {
  const html = renderPage(CitiesListPage, '/city?search=Белгород');

  expect(html).toContain('value="Белгород"');
});

test.each([
  ['people', PeopleListPage, '/people', 'Поиск человека...'],
  ['KVN teams', TeamsListPage, '/kvn/teams', 'Поиск команды...'],
  ['shows', ShowsListPage, '/shows', 'Поиск шоу...'],
])('%s provide both text and alphabet search', (_name, Page, path, placeholder) => {
  const html = renderPage(Page, path);

  expect(html).toContain('aria-label="Фильтр по первой букве"');
  expect(html).toContain(`placeholder="${placeholder}"`);
});

test('teams list highlights KVN and Stars first and omits removed categories', () => {
  const html = renderPage(TeamsListPage, '/kvn/teams');

  expect(html).toContain('aria-label="Тип команд"');
  expect(html).toContain('aria-current="page"');
  expect(html.indexOf('href="/teams"')).toBeLessThan(html.indexOf('href="/teams/zvezdy-ntv"'));
  expect(html.indexOf('href="/teams/zvezdy-ntv"')).toBeLessThan(html.indexOf('href="/teams/igra"'));
  expect(html).toContain('Другие шоу:');
  expect(html).toContain('href="/teams/liga-gorodov"');
  expect(html).toContain('href="/teams/improv-teams"');
  expect(html).not.toContain('href="/teams/superliga"');
  expect(html).not.toContain('href="/teams/ls"');
});
