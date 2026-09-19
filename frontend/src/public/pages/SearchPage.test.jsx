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
