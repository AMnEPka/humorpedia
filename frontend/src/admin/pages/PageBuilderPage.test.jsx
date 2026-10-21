import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import PageBuilderPage from './PageBuilderPage';
import { pageBuilderApi } from '../utils/api';

jest.mock('../utils/api', () => ({
  pageBuilderApi: {
    listDrafts: jest.fn(), createDraft: jest.fn(), getDraft: jest.fn(), updateDraft: jest.fn(),
    generate: jest.fn(), acceptVersion: jest.fn(), exportDraft: jest.fn(), uploadAsset: jest.fn(),
    getAsset: jest.fn(), cancel: jest.fn(),
  },
  getErrorMessage: (_error, fallback) => fallback,
}));
jest.mock('../components/ModuleEditor', () => () => <div>Редактор модулей</div>);
jest.mock('../components/page-builder/PageBuilderPreview', () => () => <div>Предпросмотр</div>);

let host;
let root;
const draft = {
  id: 'draft-1', kind: 'person', revision: 1,
  materials: { name: 'Иван Комик', birth_date: '', birth_place: '', occupation: '', notes: '', achievements: '', sources: '' },
  page: { title: 'Иван Комик', slug: 'ivan-komik', full_name: 'Иван Комик', facts: { 'Место рождения': 'Москва' }, facts_order: ['Место рождения'], modules: [], tags: [], seo: {}, bio: {} },
  relations: [], assets: [], versions: [], job: null, warnings: [], worker: { status: 'online' },
};

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  pageBuilderApi.listDrafts.mockResolvedValue({ data: { items: [draft] } });
  pageBuilderApi.getDraft.mockResolvedValue({ data: draft });
  pageBuilderApi.updateDraft.mockImplementation((_id, payload) => Promise.resolve({ data: { ...draft, ...payload, revision: payload.revision + 1 } }));
  pageBuilderApi.generate.mockResolvedValue({ data: { ...draft, job: { status: 'queued' } } });
  pageBuilderApi.acceptVersion.mockResolvedValue({ data: draft });
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  jest.clearAllMocks();
  jest.useRealTimers();
});

async function render() {
  await act(async () => root.render(<MemoryRouter initialEntries={['/admin/page-builder/draft-1']}><Routes><Route path="/admin/page-builder/:id?" element={<PageBuilderPage />} /></Routes></MemoryRouter>));
  await act(async () => { await Promise.resolve(); });
}

function button(label) {
  const found = Array.from(host.querySelectorAll('button')).find((node) => node.textContent.includes(label));
  if (!found) throw new Error(`Button not found: ${label}`);
  return found;
}

function setValue(element, value) {
  const prototype = element.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, value);
  element.dispatchEvent(new Event('input', { bubbles: true }));
  element.dispatchEvent(new Event('change', { bubbles: true }));
}

test('saves a human edit before starting generation and keeps the editor page', async () => {
  await render();
  const title = host.querySelector('input[aria-label="Заголовок страницы"]');
  await act(async () => setValue(title, 'Редакторское название'));
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 800)); });
  await act(async () => button('Собрать страницу').click());

  expect(pageBuilderApi.updateDraft).toHaveBeenCalledWith('draft-1', expect.objectContaining({
    revision: 1, page: expect.objectContaining({ title: 'Редакторское название' }),
  }));
  expect(pageBuilderApi.generate).toHaveBeenCalledWith('draft-1', { revision: 2 });
  expect(host.querySelector('input[aria-label="Заголовок страницы"]').value).toBe('Редакторское название');
});

test('shows a generated version without replacing manual edits until explicitly accepted', async () => {
  const version = { id: 'version-1', page: { ...draft.page, title: 'Предложение' }, warnings: [], questions: [], input_revision: 1 };
  pageBuilderApi.getDraft.mockResolvedValue({ data: { ...draft, versions: [version] } });
  pageBuilderApi.acceptVersion.mockResolvedValue({ data: { ...draft, revision: 2, page: version.page, versions: [version] } });
  await render();

  expect(host.textContent).toContain('Предложение');
  expect(host.querySelector('input[aria-label="Заголовок страницы"]').value).toBe('Иван Комик');
  await act(async () => button('Принять предложение').click());
  expect(host.textContent).toContain('Сравните');
  await act(async () => button('Заменить текущую страницу').click());
  expect(pageBuilderApi.acceptVersion).toHaveBeenCalledWith('draft-1', { revision: 1, version_id: 'version-1' });
  expect(host.querySelector('input[aria-label="Заголовок страницы"]').value).toBe('Предложение');
});

test('keeps the person birth date identical in biography and facts', async () => {
  await render();
  const pageSection = Array.from(host.querySelectorAll('section')).find((section) => section.textContent.includes('Редактируемая страница'));
  const birthDate = Array.from(pageSection.querySelectorAll('label')).find((label) => label.textContent.includes('Дата рождения'))?.querySelector('input');
  await act(async () => setValue(birthDate, '1987'));
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 650)); });

  expect(pageBuilderApi.updateDraft).toHaveBeenCalledWith('draft-1', expect.objectContaining({
    page: expect.objectContaining({
      bio: expect.objectContaining({ birth_date: '1987' }),
      facts: expect.objectContaining({ 'Дата рождения': '1987' }),
    }),
  }));
});

test('polling cannot replace an edit while its save is in flight', async () => {
  jest.useFakeTimers();
  let finishSave;
  pageBuilderApi.getDraft.mockResolvedValue({ data: { ...draft, job: { status: 'running' } } });
  pageBuilderApi.updateDraft.mockImplementation((_id, payload) => new Promise(resolve => {
    finishSave = () => resolve({ data: { ...draft, ...payload, revision: 2 } });
  }));
  await render();
  await act(async () => setValue(host.querySelector('input[aria-label="Заголовок страницы"]'), 'Последняя правка'));
  await act(async () => jest.advanceTimersByTime(600));
  await act(async () => jest.advanceTimersByTime(1600));
  expect(host.querySelector('input[aria-label="Заголовок страницы"]').value).toBe('Последняя правка');
  await act(async () => finishSave());
});

test('explicit action locks editable fields until its response arrives', async () => {
  let finishGeneration;
  pageBuilderApi.generate.mockImplementation(() => new Promise(resolve => {
    finishGeneration = () => resolve({ data: { ...draft, revision: 2, job: { status: 'queued' } } });
  }));
  await render();
  await act(async () => button('Собрать страницу').click());
  const title = host.querySelector('input[aria-label="Заголовок страницы"]');
  expect(title.closest('fieldset')?.disabled).toBe(true);
  await act(async () => finishGeneration());
  expect(title.closest('fieldset')?.disabled).toBe(false);
});

test('new draft navigation flushes pending edits and opens the creation form', async () => {
  await render();
  await act(async () => setValue(host.querySelector('input[aria-label="Заголовок страницы"]'), 'Сохранить перед уходом'));
  await act(async () => host.querySelector('a[href="/admin/page-builder/new"]').click());
  expect(pageBuilderApi.updateDraft).toHaveBeenCalledWith('draft-1', expect.objectContaining({
    page: expect.objectContaining({ title: 'Сохранить перед уходом' }),
  }));
  expect(host.textContent).toContain('Создать заготовку');
  expect(host.querySelector('input[aria-label="Заголовок страницы"]')).toBeNull();
});

test('refreshes worker status while no generation is active', async () => {
  jest.useFakeTimers();
  pageBuilderApi.getDraft.mockResolvedValueOnce({ data: { ...draft, worker: { status: 'offline' } } })
    .mockResolvedValue({ data: { ...draft, worker: { status: 'ready' } } });
  await render();
  expect(button('Собрать страницу').disabled).toBe(true);
  await act(async () => jest.advanceTimersByTime(5100));
  expect(button('Собрать страницу').disabled).toBe(false);
});

test('does not render a stray closing brace beside the preview', async () => {
  await render();
  await act(async () => button('Предпросмотр страницы').click());

  expect(host.textContent).not.toContain('}');
});
