import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import KVNEditPage from './KVNEditPage';
import { contentApi } from '../utils/api';

jest.mock('../utils/api', () => ({
  contentApi: {
    getKvn: jest.fn(), updateKvn: jest.fn(), createKvn: jest.fn(), listKvnHierarchy: jest.fn(),
    getSeasonByPage: jest.fn(), updateSeason: jest.fn(), retrySeasonProjection: jest.fn(),
  },
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
    <output>{JSON.stringify(seasonData)}</output>
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
const firstPageVersion = '2026-10-21T09:59:00+00:00';
const secondPageVersion = '2026-10-21T10:02:00+00:00';
const page = {
  _id: 'page-1', id: 'page-1', title: 'Сезон', slug: 'vl-2026', name: 'Сезон', updated_at: firstPageVersion,
  season_data: { year: 2026, league_slug: 'vl-kvn', description: 'Исходный текст', all_teams: [],
    stages: [{ games: [{ teams: [{ person_id: 'person-42', team_slug: 'team' }] }] }] },
};
const editorData = {
  year: 2026, league_slug: 'vl-kvn', description: 'Исходный текст', all_teams: [],
  unknown_season_field: { preserve: true },
  stages: [{ _canonical_id: 'stage-7', games: [{ _canonical_id: 'game-9', teams: [
    { person_id: 'person-42', team_id: 'team-5', team_slug: 'team', team_name: 'Команда', result_extra: 'keep' },
  ] }] }],
};
const season = {
  _id: 'season-1', updated_at: firstVersion, page_updated_at: firstPageVersion,
  editor_data: editorData, projection_status: 'ready',
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
  contentApi.getSeasonByPage.mockResolvedValue({ data: season });
  contentApi.updateSeason.mockResolvedValue({ data: { ...season, updated_at: secondVersion, page_updated_at: secondPageVersion } });
  contentApi.retrySeasonProjection.mockResolvedValue({ data: { ...season, updated_at: secondVersion, page_updated_at: secondPageVersion } });
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

test('loads canonical editor data after the page and saves season plus page metadata with distinct versions', async () => {
  await renderPage();
  expect(contentApi.getSeasonByPage).toHaveBeenCalledWith('page-1');
  expect(contentApi.getKvn.mock.invocationCallOrder[0]).toBeLessThan(contentApi.getSeasonByPage.mock.invocationCallOrder[0]);
  expect(host.querySelector('output').textContent).toContain('"_canonical_id":"stage-7"');
  await click('Изменить сезон');
  await click('Сохранить');
  expect(contentApi.updateSeason).toHaveBeenCalledWith('season-1', expect.objectContaining({
    expected_updated_at: firstVersion,
    expected_page_updated_at: firstPageVersion,
    editor_data: expect.objectContaining({
      description: 'Локальная правка',
      unknown_season_field: { preserve: true },
      stages: [{ _canonical_id: 'stage-7', games: [{ _canonical_id: 'game-9', teams: [
        { person_id: 'person-42', team_id: 'team-5', team_slug: 'team', team_name: 'Команда', result_extra: 'keep' },
      ] }] }],
    }),
    page_update: expect.objectContaining({ title: 'Сезон', slug: 'vl-2026', name: 'Сезон', status: 'draft' }),
  }));
  expect(contentApi.updateSeason.mock.calls[0][1].page_update).not.toHaveProperty('season_data');
  expect(contentApi.updateKvn).not.toHaveBeenCalled();
});

test('shows missing canonical season instead of enabling the legacy season editor', async () => {
  contentApi.getSeasonByPage.mockRejectedValue({ response: { status: 404, data: { detail: 'Канонический сезон не найден' } } });
  await renderPage();
  await click('Сохранить');
  expect(host.textContent).toContain('Канонический сезон не найден');
  expect(host.textContent).not.toContain('Исходный текст');
  expect(Array.from(host.querySelectorAll('button')).find(node => node.textContent.includes('Сохранить')).disabled).toBe(true);
  expect(contentApi.updateKvn).not.toHaveBeenCalled();
  expect(contentApi.updateSeason).not.toHaveBeenCalled();
});

test('keeps the editor visible but blocks save while a projection is already applying', async () => {
  contentApi.getSeasonByPage.mockResolvedValue({ data: { ...season, projection_status: 'applying' } });
  await renderPage();
  expect(host.querySelector('output')).not.toBeNull();
  expect(Array.from(host.querySelectorAll('button')).find(node => node.textContent.includes('Сохранить')).disabled).toBe(true);
  expect(host.textContent).toContain('выполняется');
  expect(host.textContent).not.toContain('Повторить синхронизацию');
  expect(contentApi.retrySeasonProjection).not.toHaveBeenCalled();
});

test('keeps canonical editor draft and both loaded versions when save returns a conflict', async () => {
  contentApi.updateSeason.mockRejectedValue({ response: { status: 409, data: { detail: 'Версия сезона изменилась' } } });
  await renderPage();
  await click('Изменить сезон');
  await click('Сохранить');
  expect(host.textContent).toContain('Версия сезона изменилась');
  expect(host.querySelector('output').textContent).toContain('Локальная правка');
  expect(contentApi.updateSeason).toHaveBeenCalledWith('season-1', expect.objectContaining({
    expected_updated_at: firstVersion, expected_page_updated_at: firstPageVersion,
  }));
  expect(contentApi.getKvn).toHaveBeenCalledTimes(1);
  expect(contentApi.getSeasonByPage).toHaveBeenCalledTimes(1);
});

test('shows projection error and retries only projection with the new season version', async () => {
  contentApi.updateSeason.mockResolvedValueOnce({ data: { ...season, updated_at: secondVersion, page_updated_at: secondPageVersion, projection_status: 'error' } });
  contentApi.getKvn.mockResolvedValueOnce({ data: page });
  await renderPage();
  await click('Изменить сезон');
  await click('Сохранить');
  expect(host.textContent).toContain('проекц');
  expect(host.querySelector('output')).not.toBeNull();
  expect(Array.from(host.querySelectorAll('button')).find(node => node.textContent.includes('Сохранить')).disabled).toBe(true);
  const bodyBeforeRetry = host.querySelector('output').textContent;
  await click('Повторить синхронизацию');
  expect(contentApi.retrySeasonProjection).toHaveBeenCalledWith('season-1', { expected_updated_at: secondVersion });
  expect(contentApi.updateSeason).toHaveBeenCalledTimes(1);
  expect(host.querySelector('output').textContent).toBe(bodyBeforeRetry);
});

test('uses returned versions and preserves the saved editor data when reload fails', async () => {
  contentApi.updateSeason.mockResolvedValueOnce({ data: { ...season, updated_at: secondVersion, page_updated_at: secondPageVersion, editor_data: { ...editorData, description: 'Сохранено' } } });
  contentApi.getKvn.mockResolvedValueOnce({ data: page }).mockRejectedValueOnce(new Error('Reload failed'));
  await renderPage();
  await click('Изменить сезон');
  await click('Сохранить');
  expect(host.querySelector('output').textContent).toContain('Сохранено');
  expect(host.textContent).toContain('не удалось обновить');
  await click('Изменить сезон');
  await click('Сохранить');
  expect(contentApi.updateSeason).toHaveBeenLastCalledWith('season-1', expect.objectContaining({
    expected_updated_at: secondVersion, expected_page_updated_at: secondPageVersion,
  }));
});

test.each([null, {}])('keeps the legacy page save path for a non-season page (%j)', async (seasonData) => {
  const nonSeasonPage = { ...page };
  delete nonSeasonPage.season_data;
  contentApi.getKvn.mockResolvedValue({ data: nonSeasonPage });
  contentApi.getSeasonByPage.mockRejectedValue({ response: { status: 404, data: { detail: 'Сезон не найден' } } });
  await renderPage();
  await click('Сохранить');
  expect(contentApi.updateKvn).toHaveBeenCalledWith('page-1', expect.not.objectContaining({ season_data: expect.anything() }));
  expect(contentApi.updateSeason).not.toHaveBeenCalled();
});

test('creates a season on a non-season page through the legacy adapter with an explicit missing-season token', async () => {
  const nonSeasonPage = { ...page };
  delete nonSeasonPage.season_data;
  contentApi.getKvn.mockResolvedValue({ data: nonSeasonPage });
  contentApi.getSeasonByPage.mockRejectedValue({ response: { status: 404, data: { detail: 'Сезон не найден' } } });
  await renderPage();
  await click('Создать шаблон сезона');
  await click('Сохранить');

  expect(contentApi.updateKvn).toHaveBeenCalledWith('page-1', expect.objectContaining({
    expected_updated_at: firstPageVersion,
    expected_season_updated_at: null,
    season_data: expect.objectContaining({ year: expect.any(Number), stages: [] }),
  }));
});
