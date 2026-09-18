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

test('geography uses a text search without an alphabet filter', () => {
  const html = renderPage(CitiesListPage, '/city');

  expect(html).toContain('placeholder="Поиск города..."');
  expect(html).not.toContain('aria-label="Фильтр по первой букве"');
});

test('geography keeps legacy search URLs readable', () => {
  const html = renderPage(CitiesListPage, '/city?search=Белгород');

  expect(html).toContain('value="Белгород"');
});

test.each([
  ['people', PeopleListPage, '/people'],
  ['KVN teams', TeamsListPage, '/kvn/teams'],
  ['shows', ShowsListPage, '/shows'],
])('%s use the common alphabet filter without a text search', (_name, Page, path) => {
  const html = renderPage(Page, path);

  expect(html).toContain('aria-label="Фильтр по первой букве"');
  expect(html).not.toContain('type="search"');
});

test('KVN teams list has no unrelated category tabs', () => {
  const html = renderPage(TeamsListPage, '/kvn/teams');

  expect(html).toContain('Команды КВН');
  expect(html).not.toContain('Лига смеха');
  expect(html).not.toContain('Импровизация');
});
