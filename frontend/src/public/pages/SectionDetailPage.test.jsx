import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SectionDetailPage from './SectionDetailPage';
import publicApi from '../utils/api';

jest.mock('../utils/api', () => ({
  __esModule: true,
  default: { getSectionByPath: jest.fn(), getKvnByPath: jest.fn(), lookupRedirect: jest.fn() },
}));
jest.mock('../components/ModuleRenderer', () => ({ __esModule: true, default: () => null, ModuleList: () => null }));
jest.mock('../components/RelatedArticles', () => () => null);
jest.mock('../components/LeagueSeasonsNav', () => ({ LeagueSeasonsNav: () => null }));
jest.mock('./SeasonDetailPage', () => () => null);
jest.mock('@/utils/pageTitle', () => ({ usePageTitle: jest.fn() }));

let host;
let root;
const originalFetch = global.fetch;

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  publicApi.getSectionByPath.mockRejectedValue(new Error('Not found'));
  publicApi.getKvnByPath.mockRejectedValue(new Error('Not found'));
  publicApi.lookupRedirect.mockResolvedValue({ data: { found: true, new_path: '/current-section' } });
  global.fetch = jest.fn().mockResolvedValue({ ok: false });
  jest.spyOn(console, 'error').mockImplementation(() => {});
  jest.spyOn(console, 'warn').mockImplementation(() => {});
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  global.fetch = originalFetch;
  jest.resetAllMocks();
  jest.restoreAllMocks();
});

async function render(path) {
  await act(async () => root.render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/current-section" element={<p>Актуальный раздел</p>} />
        <Route path="*" element={<SectionDetailPage />} />
      </Routes>
    </MemoryRouter>
  ));
}

test.each(['/legacy.html', '/kvn/старый-раздел.html'])('resolves %s through the public API client', async (path) => {
  await render(path);
  expect(publicApi.lookupRedirect).toHaveBeenCalledWith(path);
  expect(host.textContent).toContain('Актуальный раздел');
  expect(global.fetch).not.toHaveBeenCalled();
});

test.each(['missing', 'failed'])('shows not found when redirect lookup is %s', async (outcome) => {
  if (outcome === 'missing') publicApi.lookupRedirect.mockResolvedValue({ data: { found: false } });
  else publicApi.lookupRedirect.mockRejectedValue(new Error('Lookup unavailable'));
  await render('/legacy.html');
  expect(publicApi.lookupRedirect).toHaveBeenCalledWith('/legacy.html');
  expect(host.textContent).toContain('Раздел не найден');
  expect(host.textContent).not.toContain('Актуальный раздел');
});
