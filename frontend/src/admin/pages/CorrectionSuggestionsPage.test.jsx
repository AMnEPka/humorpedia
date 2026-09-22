import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

import CorrectionSuggestionsPage from './CorrectionSuggestionsPage';
import { correctionSuggestionsApi } from '../utils/api';


jest.mock('../utils/api', () => ({
  correctionSuggestionsApi: {
    list: jest.fn(),
    review: jest.fn(),
  },
}));


let host;
let root;

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  jest.clearAllMocks();
});


async function renderItem(item) {
  correctionSuggestionsApi.list.mockResolvedValue({ data: { items: [item], total: 1 } });
  await act(async () => {
    root.render(<CorrectionSuggestionsPage />);
  });
  await act(async () => {
    await Promise.resolve();
  });
}


test('shows editorial actions for a new suggestion', async () => {
  await renderItem({
    _id: 'suggestion-1',
    page_title: 'Тестовая страница',
    page_path: '/people/test-person',
    section: 'Биография / основной текст',
    message: 'Новая биография',
    source: null,
    email: null,
    status: 'new',
    admin_comment: null,
    created_at: '2026-09-20T09:00:00+00:00',
  });

  const labels = Array.from(host.querySelectorAll('button')).map((button) => button.textContent);
  expect(host.textContent).toContain('Новая биография');
  expect(labels).toContain('Взять в работу');
  expect(labels).toContain('Исправлено');
  expect(labels).toContain('Отклонить');
});


test('renders a terminal decision without impossible review actions', async () => {
  await renderItem({
    _id: 'suggestion-2',
    page_title: 'Тестовая страница',
    page_path: '/people/test-person',
    section: 'Личная жизнь',
    message: 'Уточнить факт',
    source: null,
    email: null,
    status: 'fixed',
    admin_comment: 'Исправлено в карточке',
    created_at: '2026-09-20T09:00:00+00:00',
  });

  const labels = Array.from(host.querySelectorAll('button')).map((button) => button.textContent);
  expect(host.textContent).toContain('Комментарий редакции: Исправлено в карточке');
  expect(labels).not.toContain('Исправлено');
  expect(labels).not.toContain('Отклонить');
});
