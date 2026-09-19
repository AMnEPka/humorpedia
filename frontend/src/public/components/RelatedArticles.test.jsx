import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import RelatedArticles from './RelatedArticles';
import { publicApi } from '../utils/api';

jest.mock('../utils/api', () => ({ publicApi: { getRecommendations: jest.fn() } }));

let host;
let root;

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  jest.clearAllMocks();
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

const mount = async () => {
  await act(async () => {
    root.render(<MemoryRouter><RelatedArticles contentType="person" contentId="person-1" /></MemoryRouter>);
  });
};

test('показывает смешанные типы страниц с готовыми ссылками API', async () => {
  publicApi.getRecommendations.mockResolvedValue({
    data: {
      enabled: true,
      items: [
        { id: 'a1', type: 'article', type_label: 'Статья', title: 'История команды', url: '/articles/history' },
        { id: 't1', type: 'kvn_team', type_label: 'Команда КВН', title: 'Союз', url: '/kvn/teams/soyuz' },
        { id: 's1', type: 'show', type_label: 'Шоу', title: 'Импровизация', url: '/shows/improv' },
      ],
    },
  });

  await mount();

  expect(publicApi.getRecommendations).toHaveBeenCalledWith('person', 'person-1');
  expect(host.querySelectorAll('a')).toHaveLength(3);
  expect([...host.querySelectorAll('a')].map((item) => item.getAttribute('href'))).toEqual([
    '/articles/history', '/kvn/teams/soyuz', '/shows/improv',
  ]);
  expect(host.textContent).toContain('Команда КВН');
  expect(host.textContent).toContain('Читайте также');
});

test('скрывает блок при пустом ответе или ошибке', async () => {
  publicApi.getRecommendations.mockResolvedValue({ data: { enabled: false, items: [] } });
  await mount();
  expect(host.textContent).toBe('');

  publicApi.getRecommendations.mockRejectedValue(new Error('offline'));
  await act(async () => {
    root.render(<MemoryRouter><RelatedArticles contentType="show" contentId="show-1" /></MemoryRouter>);
  });
  expect(host.textContent).toBe('');
});
