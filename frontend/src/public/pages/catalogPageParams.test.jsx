import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import publicApi from '../utils/api';
import PeopleListPage from './PeopleListPage';
import TeamsListPage from './TeamsListPage';
import ShowsListPage from './ShowsListPage';

jest.mock('../utils/api', () => ({
  __esModule: true,
  default: {
    getPeople: jest.fn(),
    getTeamsByCategory: jest.fn(),
    getShows: jest.fn(),
  },
}));

const emptyList = { data: { items: [], total: 0, available_letters: [], filters: {} } };

let host;
let root;

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  publicApi.getPeople.mockResolvedValue(emptyList);
  publicApi.getTeamsByCategory.mockResolvedValue(emptyList);
  publicApi.getShows.mockResolvedValue(emptyList);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  jest.clearAllMocks();
});

const renderCatalog = async (path, route, Page) => {
  await act(async () => root.render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path={route} element={<Page />} /></Routes>
    </MemoryRouter>
  ));
};

test('people deep link sends structured filters to the API', async () => {
  await renderCatalog('/people?city=Томск&role=Комик&team=Прима&show=stand-up&sort=popular', '/people', PeopleListPage);
  expect(publicApi.getPeople).toHaveBeenCalledWith(expect.objectContaining({
    city: 'Томск', role: 'Комик', team: 'Прима', show: 'stand-up', sort: 'popular',
  }));
});

test('KVN team deep link sends league and year to the API', async () => {
  await renderCatalog('/teams?city=Томск&league=vl-kvn&year=2024&sort=popular', '/teams', TeamsListPage);
  expect(publicApi.getTeamsByCategory).toHaveBeenCalledWith('kvn', expect.objectContaining({
    city: 'Томск', league: 'vl-kvn', year: '2024', sort: 'popular',
  }));
});

test('show deep link sends popularity sorting to the API', async () => {
  await renderCatalog('/shows?sort=popular', '/shows', ShowsListPage);
  expect(publicApi.getShows).toHaveBeenCalledWith(expect.objectContaining({ sort: 'popular' }));
});
