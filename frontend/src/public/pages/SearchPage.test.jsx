import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import SearchPage from './SearchPage';
import publicApi from '../utils/api';

jest.mock('../utils/api', () => ({
  __esModule: true,
  default: {
    search: jest.fn(),
  },
}));

let host;
let root;

beforeEach(() => {
  jest.clearAllMocks();
  publicApi.search.mockResolvedValue({ data: {} });
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

test('requests the expanded result limit for the full search page', async () => {
  await act(async () => {
    root.render(
      <MemoryRouter initialEntries={['/search?q=%D0%93%D1%83']}>
        <SearchPage />
      </MemoryRouter>
    );
  });

  expect(publicApi.search).toHaveBeenCalledWith('Гу', { limit: 100 });
});

test('filters by type and links a nested show by full_path', async () => {
  publicApi.search.mockResolvedValue({ data: {
    show: [{ _id: 's1', title: 'Сезон', slug: 'season-2', full_path: 'zvezdy-ntv/season-2' }],
  } });
  await act(async () => {
    root.render(
      <MemoryRouter initialEntries={['/search?q=%D0%97%D0%B2%D1%91%D0%B7%D0%B4%D1%8B&type=show']}>
        <SearchPage />
      </MemoryRouter>
    );
  });

  expect(publicApi.search).toHaveBeenCalledWith('Звёзды', { limit: 100, types: 'show' });
  expect(host.querySelector('a[href="/shows/zvezdy-ntv/season-2"]')).toBeTruthy();
  expect(host.querySelector('[aria-pressed="true"]')?.textContent).toBe('Шоу');
});
