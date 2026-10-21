import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

import SourceImportsPanel from './SourceImportsPanel';
import { contentApi, editorialImportsApi } from '../utils/api';

jest.mock('../utils/api', () => ({
  contentApi: { searchPeople: jest.fn(), getPerson: jest.fn() },
  editorialImportsApi: {
    list: jest.fn(), importUrls: jest.fn(), scan: jest.fn(), getSettings: jest.fn(), updateSettings: jest.fn(),
    update: jest.fn(), approve: jest.fn(), reject: jest.fn(),
  },
  getErrorMessage: (error, fallback) => error.response?.data?.detail || fallback,
}));
jest.mock('./RichTextEditor', () => ({ content, onChange }) => <textarea aria-label="Rich text source" value={content} onChange={(event) => onChange(event.target.value)} />);
jest.mock('./ContentRelationSelector', () => ({ type }) => <div>{type} relations</div>);

let host;
let root;
const card = (patch = {}) => ({ _id: 'import-1', kind: 'news', status: 'pending', revision: 4, source: { url: 'https://24smi.org/news/1', title: 'Источник', published_at: '2026-10-20' }, payload: { title: 'Заголовок', slug: 'slug', content: '<p>Непубликованный текст</p>', excerpt: '', related_person_ids: [], related_show_ids: [] }, warnings: [], ...patch });
const tick = async () => act(async () => { await Promise.resolve(); });

beforeEach(() => {
  host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host);
  editorialImportsApi.list.mockResolvedValue({ data: { items: [card()], total: 1 } });
  editorialImportsApi.getSettings.mockResolvedValue({ data: { enabled: false, hour_moscow: 10, running: false, last_result: null } });
  editorialImportsApi.updateSettings.mockResolvedValue({ data: { enabled: true, hour_moscow: 10, running: false } });
  editorialImportsApi.update.mockImplementation(async (_id, request) => ({ data: { ...card(), revision: request.revision + 1, payload: request.payload } }));
  editorialImportsApi.approve.mockResolvedValue({ data: {} });
  editorialImportsApi.scan.mockResolvedValue({ status: 202, data: { started: true } });
  editorialImportsApi.importUrls.mockResolvedValue({ data: { results: [] } });
  contentApi.searchPeople.mockResolvedValue({ data: [] });
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); jest.clearAllMocks(); jest.useRealTimers(); });
async function render() { await act(async () => root.render(<SourceImportsPanel />)); await tick(); }
function click(label) { const button = [...host.querySelectorAll('button')].find((node) => node.textContent.trim() === label); if (!button) throw new Error(`Missing button ${label}`); return act(async () => button.click()); }
function changeInput(label, value) { const input = host.querySelector(`[aria-label="${label}"]`); const setter = Object.getOwnPropertyDescriptor(input.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value').set; act(() => { setter.call(input, value); input.dispatchEvent(new Event('input', { bubbles: true })); }); }

test('shows unpublished source text in the pending import card', async () => {
  await render();
  expect(host.textContent).toContain('Непубликованный текст');
  expect(host.textContent).toContain('Источник');
  expect(host.textContent).toContain('Отобрано карточек: 1');
});

test('retries interrupted publication without changing its revision', async () => {
  editorialImportsApi.list.mockResolvedValue({ data: { items: [card({ status: 'publishing' })], total: 1 } });
  await render();
  await click('Завершить утверждение');
  expect(editorialImportsApi.update).not.toHaveBeenCalled();
  expect(editorialImportsApi.approve).toHaveBeenCalledWith('import-1', { revision: 4 });
});

test('renders accepted content as a sanitized read only preview', async () => {
  editorialImportsApi.list.mockResolvedValue({ data: { items: [card({ status: 'accepted', payload: { ...card().payload, content: '<p>Утверждённый текст</p><script>alert(1)</script>' } })], total: 1 } });
  await render();
  expect(host.textContent).toContain('Утверждённый текст');
  expect(host.querySelector('script')).toBeNull();
  expect(host.querySelector('button')?.textContent).not.toContain('Сохранить');
});

test('saves edits before approving with the exact returned revision', async () => {
  await render();
  changeInput('Заголовок', 'Исправленный заголовок');
  changeInput('Rich text source', '<p>Отредактированный текст</p>');
  await click('Утвердить и опубликовать');
  expect(editorialImportsApi.update).toHaveBeenCalledWith('import-1', expect.objectContaining({ revision: 4, payload: expect.objectContaining({ title: 'Исправленный заголовок', content: '<p>Отредактированный текст</p>' }), target_id: null }));
  expect(editorialImportsApi.approve).toHaveBeenCalledWith('import-1', { revision: 5 });
});

test('shows a conflict when approval returns HTTP 409', async () => {
  editorialImportsApi.approve.mockRejectedValue({ response: { status: 409, data: { detail: 'Конфликт версии' } } });
  await render(); await click('Утвердить и опубликовать');
  expect(host.textContent).toContain('Конфликт версии');
});

test('keeps the new revision after approval validation fails, then saves edits and approves', async () => {
  editorialImportsApi.list.mockResolvedValue({ data: { items: [card({ revision: 1 })], total: 1 } });
  editorialImportsApi.update.mockImplementation(async (_id, request) => ({ data: { ...card(), revision: request.revision + 1, payload: request.payload } }));
  editorialImportsApi.approve.mockRejectedValueOnce({ response: { status: 422, data: { detail: 'Добавьте два шоу' } } }).mockResolvedValueOnce({ data: {} });
  await render();
  changeInput('Заголовок', 'Черновик до проверки');
  await click('Утвердить и опубликовать');
  expect(editorialImportsApi.update).toHaveBeenNthCalledWith(1, 'import-1', expect.objectContaining({ revision: 1 }));
  expect(editorialImportsApi.approve).toHaveBeenNthCalledWith(1, 'import-1', { revision: 2 });
  expect(host.textContent).toContain('Добавьте два шоу');
  changeInput('Заголовок', 'Исправленный заголовок');
  await click('Утвердить и опубликовать');
  expect(editorialImportsApi.update).toHaveBeenNthCalledWith(2, 'import-1', expect.objectContaining({ revision: 2, payload: expect.objectContaining({ title: 'Исправленный заголовок' }) }));
  expect(editorialImportsApi.approve).toHaveBeenNthCalledWith(2, 'import-1', { revision: 3 });
});

test('retries approve with the saved revision after a post write error without another patch', async () => {
  editorialImportsApi.list.mockResolvedValue({ data: { items: [card({ revision: 1 })], total: 1 } });
  editorialImportsApi.update.mockResolvedValue({ data: { ...card(), revision: 2 } });
  editorialImportsApi.approve.mockRejectedValueOnce({ response: { status: 500, data: { detail: 'Ошибка ответа после записи' } } }).mockResolvedValueOnce({ data: {} });
  await render();
  changeInput('Заголовок', 'Исправленный материал');
  await click('Утвердить и опубликовать');
  expect(editorialImportsApi.update).toHaveBeenCalledTimes(1);
  expect(editorialImportsApi.approve).toHaveBeenNthCalledWith(1, 'import-1', { revision: 2 });
  await click('Утвердить и опубликовать');
  expect(editorialImportsApi.update).toHaveBeenCalledTimes(1);
  expect(editorialImportsApi.approve).toHaveBeenNthCalledWith(2, 'import-1', { revision: 2 });
});

test('offers an explicit target refresh after an approve conflict', async () => {
  const biography = card({ kind: 'biography', target_id: 'person-1', target_title: 'Человек', matches: [{ id: 'person-1', title: 'Человек' }], payload: { ...card().payload, full_name: 'Человек', bio: {} } });
  editorialImportsApi.list.mockResolvedValue({ data: { items: [biography], total: 1 } });
  editorialImportsApi.approve.mockRejectedValue({ response: { status: 409, data: { detail: 'Целевая страница изменилась' } } });
  editorialImportsApi.update.mockResolvedValue({ data: { ...biography, revision: 5 } });
  await render();
  await click('Утвердить и опубликовать');
  expect(host.querySelector('a[href="/admin/people/person-1"]')).not.toBeNull();
  await click('Я сверил страницу — обновить версию');
  expect(editorialImportsApi.update).toHaveBeenCalledWith('import-1', expect.objectContaining({ revision: 4, target_id: 'person-1', refresh_target: true }));
  expect(host.textContent).not.toContain('Проверьте актуальную целевую страницу перед продолжением.');
});

test('rejects with the current revision without patching unsaved content', async () => {
  await render();
  changeInput('Заголовок', 'Невалидный незасохранённый заголовок');
  await click('Отклонить');
  expect(editorialImportsApi.update).not.toHaveBeenCalled();
  expect(editorialImportsApi.reject).toHaveBeenCalledWith('import-1', { revision: 4 });
});

test('starts a three day scan and updates schedule settings', async () => {
  editorialImportsApi.list.mockResolvedValue({ data: { items: [], total: 0 } });
  await render(); await click('Собрать новости за 3 дня');
  expect(editorialImportsApi.scan).toHaveBeenCalledWith({ source_id: '24smi', days: 3, limit: 100 });
  const toggle = host.querySelector('input[aria-label="Ежедневный сбор в 10:00 по Москве"]');
  await act(async () => { toggle.click(); });
  expect(editorialImportsApi.updateSettings).toHaveBeenCalledWith({ source_id: '24smi', enabled: true });
  expect(editorialImportsApi.getSettings).toHaveBeenCalled();
});

test('switches the queue, scan and schedule to the selected source', async () => {
  editorialImportsApi.list.mockResolvedValue({ data: { items: [], total: 0 } });
  await render();
  await click('GoStandup');
  expect(editorialImportsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ source_id: 'gostandup' }));
  expect(editorialImportsApi.getSettings).toHaveBeenLastCalledWith('gostandup');
  expect(host.textContent).toContain('Импорт материалов GoStandup');
  await click('Собрать новости за 3 дня');
  expect(editorialImportsApi.scan).toHaveBeenLastCalledWith({ source_id: 'gostandup', days: 3, limit: 100 });
  const toggle = host.querySelector('input[aria-label="Ежедневный сбор в 10:00 по Москве"]');
  await act(async () => { toggle.click(); });
  expect(editorialImportsApi.updateSettings).toHaveBeenLastCalledWith({ source_id: 'gostandup', enabled: true });
  await click('Вокруг ТВ');
  expect(editorialImportsApi.getSettings).toHaveBeenLastCalledWith('vokrugtv');
  expect(editorialImportsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ source_id: 'vokrugtv' }));
});

test('hides old source cards immediately and ignores a late response from another source', async () => {
  await render();
  let resolveGo;
  editorialImportsApi.list.mockImplementationOnce(() => new Promise((resolve) => { resolveGo = resolve; }));
  await click('GoStandup');
  expect(host.querySelector('[aria-label="Заголовок"]')).toBeNull();
  editorialImportsApi.list.mockResolvedValueOnce({ data: { items: [card({ _id: 'vokrug', payload: { ...card().payload, title: 'Вокруг ТВ материал' } })], total: 1 } });
  await click('Вокруг ТВ');
  expect(host.querySelector('[aria-label="Заголовок"]').value).toBe('Вокруг ТВ материал');
  await act(async () => { resolveGo({ data: { items: [card({ payload: { ...card().payload, title: 'Запоздалый GoStandup' } })], total: 1 } }); await Promise.resolve(); });
  expect(host.querySelector('[aria-label="Заголовок"]').value).toBe('Вокруг ТВ материал');
});

test('silently refreshes the completed scan without discarding an open card draft', async () => {
  jest.useFakeTimers();
  editorialImportsApi.list.mockResolvedValue({ data: { items: [card()], total: 1 } });
  editorialImportsApi.getSettings.mockResolvedValue({ data: { enabled: false, hour_moscow: 10, running: false } });
  await render();
  changeInput('Заголовок', 'Черновик без сохранения');
  await click('Собрать новости за 3 дня');
  await act(async () => { jest.advanceTimersByTime(5000); await Promise.resolve(); await Promise.resolve(); });
  expect(host.querySelector('[aria-label="Заголовок"]').value).toBe('Черновик без сохранения');
  expect(editorialImportsApi.list).toHaveBeenCalledTimes(2);
});

test('isolates the Zhaba queue and uses source-specific scan and schedule parameters', async () => {
  editorialImportsApi.list.mockResolvedValue({ data: { items: [], total: 0 } });
  await render();
  await click('ЖАБА — медиа-болото');
  expect(editorialImportsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ source_id: 'zhaba' }));
  expect(editorialImportsApi.getSettings).toHaveBeenLastCalledWith('zhaba');
  expect(host.textContent).toContain('Импорт материалов ЖАБА — медиа-болото');
  const urls = host.querySelector('[aria-label="Ссылки для импорта"]');
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
  act(() => { setter.call(urls, 'https://t.me/zhabqua/123'); urls.dispatchEvent(new Event('input', { bubbles: true })); });
  await click('Собрать новые посты');
  expect(editorialImportsApi.scan).toHaveBeenCalledWith({ source_id: 'zhaba', days: 3, limit: 100 });
  const toggle = host.querySelector('input[aria-label="Ежедневный сбор в 10:00 по Москве"]');
  await act(async () => { toggle.click(); });
  expect(editorialImportsApi.updateSettings).toHaveBeenLastCalledWith({ source_id: 'zhaba', enabled: true });
  await click('24СМИ');
  expect(editorialImportsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ source_id: '24smi' }));
  expect(host.querySelector('[aria-label="Ссылки для импорта"]').value).toBe('');
});

test('imports text-post URLs and labels Zhaba cards as posts with a wrapping source badge', async () => {
  const post = card({ source_id: 'zhaba', source: { url: 'https://t.me/zhabqua/123', title: 'Пост ЖАБЫ' } });
  editorialImportsApi.list.mockResolvedValue({ data: { items: [post], total: 1 } });
  await render();
  await click('ЖАБА — медиа-болото');
  expect(host.textContent).toContain('Пост ЖАБЫ');
  expect(host.textContent).toContain('Пост');
  expect(host.textContent).not.toContain('Новость');
  await click('Посты');
  expect(editorialImportsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ source_id: 'zhaba', kind: 'news' }));
  const sourceLabel = [...host.querySelectorAll('p')].find((node) => node.textContent === 'ЖАБА — медиа-болото');
  expect(sourceLabel.className).toContain('break-words');
  const urls = host.querySelector('[aria-label="Ссылки для импорта"]');
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
  act(() => { setter.call(urls, 'https://t.me/zhabqua/123'); urls.dispatchEvent(new Event('input', { bubbles: true })); });
  await click('Импортировать ссылки');
  expect(editorialImportsApi.importUrls).toHaveBeenCalledWith(['https://t.me/zhabqua/123']);
});

test('reports Zhaba posts without text and explains continuation after truncation', async () => {
  editorialImportsApi.list.mockResolvedValue({ data: { items: [], total: 0 } });
  editorialImportsApi.getSettings.mockResolvedValue({ data: { enabled: false, hour_moscow: 10, running: false, last_result: { checked: 12, created: 4, duplicates: 2, unrelated: 1, errors: [], without_text: 5, pages: 2, truncated: true } } });
  await render();
  await click('ЖАБА — медиа-болото');
  expect(host.textContent).toContain('без текста 5');
  expect(host.textContent).toContain('страниц 2');
  expect(host.textContent).toContain('Следующий запуск продолжит сбор');
});
