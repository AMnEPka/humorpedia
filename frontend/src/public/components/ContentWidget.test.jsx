import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { ContentWidget } from './AdditionalModules';
import { publicApi } from '../utils/api';

jest.mock('../utils/api', () => ({ publicApi: { getArticles: jest.fn(), getRandomContent: jest.fn() } }));
let host, root;
beforeEach(() => { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host); jest.clearAllMocks(); });
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });
const mount = async (type, data = {}) => {
  await act(async () => root.render(<MemoryRouter initialEntries={['/articles/current']}><ContentWidget module={{ type, data }} /></MemoryRouter>));
};
test('лучшие статьи запрашивают рейтинг, исключают текущую, архив и дубли', async () => {
  publicApi.getArticles.mockResolvedValue({ data: { items: [
    { slug: 'current', title: 'Текущая' }, { slug: 'a', title: 'Первая' },
    { slug: 'a', title: 'Дубль' }, { slug: 'b', title: 'Архив', status: 'archived' },
  ] } });
  await mount('best_articles', { limit: 3 });
  expect(publicApi.getArticles).toHaveBeenCalledWith({ limit: 4, exclude_archived: true, sort: '-rating' });
  expect([...host.querySelectorAll('a')].map(a => a.getAttribute('href'))).toEqual(['/articles/a']);
});
test('интересные материалы используют редакционный featured', async () => {
  publicApi.getArticles.mockResolvedValue({ data: { items: [] } });
  await mount('interesting');
  expect(publicApi.getArticles).toHaveBeenCalledWith({ limit: 4, exclude_archived: true, featured: true });
  expect(host.textContent).toContain('Пока нет');
});
test('случайная страница ведёт на команду вложенного шоу', async () => {
  publicApi.getRandomContent.mockResolvedValue({ data: { slug: 'team', title: 'Команда', show_id: 'show', full_path: 'show/teams/team' } });
  await mount('random_page', { content_type: 'team' });
  expect(host.querySelector('a').getAttribute('href')).toBe('/shows/show/teams/team');
});
test('ошибка API отображается явно', async () => {
  publicApi.getArticles.mockRejectedValue(new Error('offline'));
  await mount('interesting');
  expect(host.querySelector('[role="alert"]').textContent).toContain('Не удалось');
});
test('текущая статья исключается сервером до случайной выборки', async () => {
  publicApi.getRandomContent.mockResolvedValue({ data: { slug: 'other', title: 'Другая' } });
  await mount('random_page', { content_type: 'article' });
  expect(publicApi.getRandomContent).toHaveBeenCalledWith('article', { exclude_slug: 'current' });
  expect(host.querySelector('a').getAttribute('href')).toBe('/articles/other');
});
