import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import SeasonImportDialog from './SeasonImportDialog';
import { contentApi } from '../utils/api';

jest.mock('../utils/api', () => ({ contentApi: { previewSeasonImport: jest.fn(), importSeason: jest.fn() },
  getErrorMessage: (error) => error.response?.data?.detail || error.message }));

let root;
let host;
const onImported = jest.fn();
const packageData = { title: 'Высшая лига 2026', teams: [{ key: 'a', name: 'Команда', city: 'Омск' }], stages: [] };
const preview = { title: packageData.title, teams: [{ key: 'a', name: 'Команда', city: 'Омск', action: 'create' }],
  teams_to_create: 1, games_count: 0, results_count: 0, errors: [], preview_token: 'checked' };

beforeEach(async () => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => root.render(<MemoryRouter><SeasonImportDialog onImported={onImported} /></MemoryRouter>));
  await click('Импорт сезона');
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  jest.clearAllMocks();
});

async function click(label) {
  const button = Array.from(document.querySelectorAll('button')).find((node) => node.textContent === label);
  if (!button) throw new Error(`Нет кнопки: ${label}`);
  await act(async () => button.click());
}

async function type(value) {
  const input = document.querySelector('textarea[aria-label="Пакет сезона"]');
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}

test('проверяет пакет и применяет только с полученным подтверждением проверки', async () => {
  contentApi.previewSeasonImport.mockResolvedValue({ data: preview });
  contentApi.importSeason.mockResolvedValue({ data: { created: true, created_teams: [{ id: 'team' }], page_id: 'page', path: 'kvn/vl-kvn/vl-2026' } });
  await type(JSON.stringify(packageData));
  expect(contentApi.importSeason).not.toHaveBeenCalled();
  await click('Проверить пакет');
  expect(document.body.textContent).toContain('создать пустую команду');
  await click('Создать сезон и недостающие команды');
  expect(contentApi.importSeason).toHaveBeenCalledWith({ package: packageData, preview_token: 'checked' });
  expect(onImported).toHaveBeenCalledTimes(1);
  expect(document.querySelector('a[href="/admin/kvn/page"]')).not.toBeNull();
});

test('правка пакета отменяет предыдущую проверку', async () => {
  contentApi.previewSeasonImport.mockResolvedValue({ data: preview });
  await type(JSON.stringify(packageData));
  await click('Проверить пакет');
  await type(JSON.stringify({ ...packageData, title: 'Другое название' }));
  expect(document.body.textContent).not.toContain('Создать сезон и недостающие команды');
  expect(contentApi.importSeason).not.toHaveBeenCalled();
});

test('ошибки сопоставления блокируют создание', async () => {
  contentApi.previewSeasonImport.mockResolvedValue({ data: { ...preview, errors: ['Несколько совпадений'] } });
  await type(JSON.stringify(packageData));
  await click('Проверить пакет');
  const button = Array.from(document.querySelectorAll('button')).find((node) => node.textContent === 'Создать сезон и недостающие команды');
  expect(button.disabled).toBe(true);
  expect(document.body.textContent).toContain('Несколько совпадений');
});

test('невалидный JSON не уходит на сервер', async () => {
  await type('{broken');
  await click('Проверить пакет');
  expect(document.body.textContent).toContain('Неверный формат JSON');
  expect(contentApi.previewSeasonImport).not.toHaveBeenCalled();
});
