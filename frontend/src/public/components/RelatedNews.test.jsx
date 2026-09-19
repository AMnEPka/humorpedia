import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import RelatedNews from './RelatedNews';
import { publicApi } from '../utils/api';

jest.mock('../utils/api', () => ({ publicApi: { getRelatedNews: jest.fn() } }));

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
    root.render(
      <MemoryRouter>
        <RelatedNews entityType="person" entityId="person-1" />
      </MemoryRouter>
    );
  });
};

test('показывает не более трёх свежих новостей в компактном списке', async () => {
  publicApi.getRelatedNews.mockResolvedValue({
    data: {
      enabled: true,
      items: [1, 2, 3, 4].map((id) => ({
        id: String(id),
        slug: `news-${id}`,
        title: `Новость ${id}`,
        excerpt: `Краткое описание ${id}`,
        published_at: '2026-09-18T12:00:00Z',
      })),
    },
  });

  await mount();

  expect(publicApi.getRelatedNews).toHaveBeenCalledWith('person', 'person-1');
  expect(host.textContent).toContain('Свежие новости');
  expect(host.querySelectorAll('a')).toHaveLength(3);
  expect(host.querySelector('a').getAttribute('href')).toBe('/news/news-1');
  expect(host.textContent).not.toContain('Новость 4');
});

test('не показывает блок при пустом ответе или ошибке API', async () => {
  publicApi.getRelatedNews.mockResolvedValue({ data: { enabled: false, items: [] } });
  await mount();
  expect(host.textContent).toBe('');

  publicApi.getRelatedNews.mockRejectedValue(new Error('offline'));
  await act(async () => {
    root.render(
      <MemoryRouter>
        <RelatedNews entityType="show" entityId="show-1" />
      </MemoryRouter>
    );
  });
  expect(host.textContent).toBe('');
});
