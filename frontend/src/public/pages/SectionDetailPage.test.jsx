import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
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

function CurrentPath() {
  return <p data-testid="current-path">{useLocation().pathname}</p>;
}

async function render(path) {
  await act(async () => root.render(
    <MemoryRouter initialEntries={[path]}>
      <CurrentPath />
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


test.each(['kvn/league/lampa', '/kvn/league/lampa', undefined])('opens a child from the site root for full_path=%s', async (fullPath) => {
  publicApi.lookupRedirect.mockResolvedValue({ data: { found: false } });
  publicApi.getKvnByPath.mockResolvedValue({ data: {
    title: 'Лиги МС КВН',
    children: [{ id: 'lampa', title: 'Лампа', slug: 'lampa', full_path: fullPath }],
  } });
  await render('/kvn/league');
  const card = Array.from(host.querySelectorAll('div.font-semibold')).find(node => node.textContent === 'Лампа');
  expect(card).toBeTruthy();
  await act(async () => card.dispatchEvent(new MouseEvent('click', { bubbles: true })));
  expect(host.querySelector('[data-testid="current-path"]').textContent).toBe(fullPath ? '/kvn/league/lampa' : '/lampa');
});

test.each(['kvn/league', '/kvn/league'])('opens a breadcrumb from the site root for full_path=%s', async (fullPath) => {
  publicApi.lookupRedirect.mockResolvedValue({ data: { found: false } });
  publicApi.getKvnByPath.mockResolvedValue({ data: {
    title: 'Лампа', breadcrumbs: [{ id: 'league', title: 'Лиги МС КВН', full_path: fullPath }],
  } });
  await render('/kvn/league/lampa');
  const link = Array.from(host.querySelectorAll('a')).find(node => node.textContent === 'Лиги МС КВН');
  expect(link).toBeTruthy();
  await act(async () => link.dispatchEvent(new MouseEvent('click', { bubbles: true, button: 0 })));
  expect(host.querySelector('[data-testid="current-path"]').textContent).toBe('/kvn/league');
});
