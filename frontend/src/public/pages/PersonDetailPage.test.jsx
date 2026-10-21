import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import PersonDetailPage from './PersonDetailPage';
import publicApi from '../utils/api';

jest.mock('../utils/api', () => ({
  __esModule: true,
  default: { getPerson: jest.fn(), getPersonCareer: jest.fn(), getPersonShows: jest.fn() },
}));

let host;
let root;

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  jest.clearAllMocks();
});

test('renders preview appearance relations using the public show card contract without API calls', async () => {
  const relations = [{
    id: 'appearance-1',
    kind: 'appearance',
    achievement: 'winner',
    target: { type: 'show', slug: 'show-title', path: 'league/show-title' },
  }];
  await act(async () => root.render(
    <MemoryRouter>
      <PersonDetailPage preview previewDocument={{ title: 'Комик', slug: 'komik', modules: [] }} previewRelations={relations} />
    </MemoryRouter>,
  ));

  expect(host.textContent).toContain('Участие в других проектах');
  expect(host.textContent).toContain('Победитель проекта «show-title»');
  expect(host.querySelector('a[href="/shows/league/show-title"]')).not.toBeNull();
  expect(publicApi.getPersonShows).not.toHaveBeenCalled();
  expect(publicApi.getPersonCareer).not.toHaveBeenCalled();
  expect(publicApi.getPerson).not.toHaveBeenCalled();
});
