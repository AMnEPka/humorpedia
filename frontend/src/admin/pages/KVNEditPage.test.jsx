import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import KVNEditPage from './KVNEditPage';
import { contentApi } from '../utils/api';

jest.mock('../utils/api', () => ({
  contentApi: { getKvn: jest.fn(), updateKvn: jest.fn(), listKvnHierarchy: jest.fn() },
  getErrorMessage: (error, fallback) => error.response?.data?.detail || fallback,
}));
jest.mock('../components/ModuleEditor', () => () => null);
jest.mock('../components/TagSelector', () => () => null);
jest.mock('../components/PersonSelector', () => () => null);
jest.mock('../components/MediaSelector', () => () => null);
jest.mock('../components/FactsEditor', () => () => null);
jest.mock('../components/SeasonModulesArchive', () => () => null);
jest.mock('../components/SeasonDataEditor', () => ({ seasonData, onChange }) => (
  <div>
    <output>{seasonData.description}</output>
    <button type="button" onClick={() => onChange({ ...seasonData, description: 'Локальная правка' })}>Изменить сезон</button>
  </div>
));
jest.mock('@/components/ui/tabs', () => {
  const Container = ({ children }) => <div>{children}</div>;
  return { Tabs: Container, TabsContent: Container, TabsList: Container, TabsTrigger: Container };
});
jest.mock('@/components/ui/select', () => {
  const Container = ({ children }) => <div>{children}</div>;
  return { Select: Container, SelectContent: Container, SelectItem: Container, SelectTrigger: Container, SelectValue: () => null };
});

const firstVersion = '2026-10-21T10:00:00+00:00';
const secondVersion = '2026-10-21T10:01:00+00:00';
const page = {
  _id: 'page-1', id: 'page-1', slug: 'vl-2026', name: 'Сезон', updated_at: firstVersion,
  season_data: { year: 2026, league_slug: 'vl-kvn', description: 'Исходный текст', all_teams: [],
    stages: [{ games: [{ teams: [{ person_id: 'person-42', team_slug: 'team' }] }] }] },
};
let host;
let root;

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  contentApi.listKvnHierarchy.mockResolvedValue({ data: { tree: [], items: [] } });
  contentApi.getKvn.mockResolvedValue({ data: page });
  contentApi.updateKvn.mockResolvedValue({ data: { ...page, updated_at: secondVersion } });
  jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  jest.resetAllMocks();
  jest.restoreAllMocks();
});

async function renderPage() {
  await act(async () => root.render(
    <MemoryRouter initialEntries={['/admin/kvn/page-1']}>
      <Routes><Route path="/admin/kvn/:id" element={<KVNEditPage />} /></Routes>
    </MemoryRouter>
  ));
}

async function click(label) {
  const button = Array.from(host.querySelectorAll('button')).find(node => node.textContent.trim() === label);
  if (!button) throw new Error(`Button not found: ${label}`);
  await act(async () => button.click());
}

test('sends the loaded page version and preserves person_id when saving a season', async () => {
  await renderPage();
  await click('Изменить сезон');
  await click('Сохранить');
  expect(contentApi.updateKvn).toHaveBeenCalledWith('page-1', expect.objectContaining({
    expected_updated_at: firstVersion,
    season_data: expect.objectContaining({ description: 'Локальная правка' }),
  }));
  expect(contentApi.updateKvn.mock.calls[0][1].season_data.stages[0].games[0].teams[0].person_id).toBe('person-42');
});

test('sends an explicit null version for a legacy page without updated_at', async () => {
  const { updated_at, ...legacyPage } = page;
  contentApi.getKvn.mockResolvedValue({ data: legacyPage });
  await renderPage();
  await click('Сохранить');
  expect(contentApi.updateKvn).toHaveBeenCalledWith('page-1', expect.objectContaining({ expected_updated_at: null }));
});

test('keeps local edits and the loaded version when save returns a conflict', async () => {
  contentApi.updateKvn.mockRejectedValue({ response: { status: 409, data: { detail: 'Версия сезона изменилась' } } });
  await renderPage();
  await click('Изменить сезон');
  await click('Сохранить');
  expect(host.textContent).toContain('Версия сезона изменилась');
  expect(host.querySelector('output').textContent).toBe('Локальная правка');
  expect(contentApi.getKvn).toHaveBeenCalledTimes(1);
});

test('uses the saved version on the next save even when the follow-up reload failed', async () => {
  contentApi.getKvn.mockResolvedValueOnce({ data: page }).mockRejectedValue(new Error('Reload failed'));
  await renderPage();
  await click('Сохранить');
  await click('Сохранить');
  expect(contentApi.updateKvn).toHaveBeenLastCalledWith('page-1', expect.objectContaining({ expected_updated_at: secondVersion }));
});
