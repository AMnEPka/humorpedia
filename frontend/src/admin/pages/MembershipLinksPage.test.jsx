import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import MembershipLinksPage from './MembershipLinksPage';
import { contentApi } from '../utils/api';

jest.mock('../utils/api', () => ({
  contentApi: {
    listMembershipLinkReviews: jest.fn(),
    reviewMembershipLink: jest.fn(),
  },
  getErrorMessage: (_error, fallback) => fallback,
}));

jest.mock('../components/PersonSelector', () => function PersonSelectorMock({ onChange }) {
  return <button type="button" onClick={() => onChange(['person-2'])}>Выбрать Анну</button>;
});

const response = {
  items: [{
    membership: {
      _id: 'membership-1',
      person_name: 'Анна Иванова',
      person_slug: 'anna-ivanova',
      roles: ['Автор', 'Актриса'],
      from_year: 2020,
      to_year: 2022,
    },
    team: { id: 'team-1', name: 'Сборная тестов' },
    person: { id: 'person-1', name: 'Анна И. Иванова' },
    source_person: { id: 'person-source', name: 'Анна Иванова из исходной ссылки' },
    reason: 'slug_conflict',
    review_status: 'pending',
    public_active: true,
  }],
  total: 1,
  skip: 0,
  limit: 50,
  counts: { pending: 1, confirmed: 2, rejected: 3 },
};

let container;
let root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  contentApi.listMembershipLinkReviews.mockResolvedValue({ data: response });
  contentApi.reviewMembershipLink.mockResolvedValue({ data: { ok: true } });
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  jest.clearAllMocks();
});

async function renderPage() {
  await act(async () => {
    root.render(<MemoryRouter><MembershipLinksPage /></MemoryRouter>);
  });
  await act(async () => { await Promise.resolve(); });
}

function findButton(text) {
  return [...container.querySelectorAll('button')].find(button => button.textContent === text);
}

async function click(text) {
  const button = findButton(text);
  expect(button).toBeDefined();
  await act(async () => { button.click(); });
  await act(async () => { await Promise.resolve(); });
}

test('показывает данные проверки и объясняет публичное поведение pending-связей', async () => {
  await renderPage();

  expect(contentApi.listMembershipLinkReviews).toHaveBeenCalledWith({
    q: undefined,
    status: 'pending',
    reason: undefined,
    skip: 0,
    limit: 50,
  });
  expect(container.textContent).toContain('Анна Иванова');
  expect(container.textContent).toContain('Сборная тестов');
  expect(container.textContent).toContain('Анна И. Иванова');
  expect(container.querySelector('a[href="/admin/teams/team-1"]')).not.toBeNull();
  expect(container.querySelector('a[href="/admin/people/person-1"]')).not.toBeNull();
  expect(container.querySelector('a[href="/admin/people/person-source"]')).not.toBeNull();
  expect(container.textContent).toContain('Страница по исходной ссылке');
  expect(container.textContent).toContain('Конфликт slug');
  expect(container.textContent).toContain('Роли: Автор, Актриса');
  expect(container.textContent).toContain('Годы: 2020–2022');
  expect(container.textContent).toContain('Source slug: anna-ivanova');
  expect(container.textContent).toContain('Связь сейчас публична');
  expect(container.textContent).toContain('остаются публичными до решения');
  expect(container.textContent).toContain('имя участника сохранится в составе');
  expect(container.textContent).toContain('Ожидают: 1');
});

test('подтверждает, отклоняет и вручную меняет страницу человека', async () => {
  await renderPage();

  await click('Подтвердить');
  expect(contentApi.reviewMembershipLink).toHaveBeenCalledWith('membership-1', { action: 'confirm' });

  await click('Некорректная связь — отвязать');
  expect(contentApi.reviewMembershipLink).toHaveBeenCalledWith('membership-1', { action: 'reject' });

  await click('Выбрать другого');
  await click('Выбрать Анну');
  expect(contentApi.reviewMembershipLink).toHaveBeenCalledWith('membership-1', { action: 'link', person_id: 'person-2' });
  expect(contentApi.listMembershipLinkReviews.mock.calls.length).toBeGreaterThan(1);
  expect(container.querySelector('[role="status"]')?.textContent).toContain('Решение сохранено');
});

test('передаёт поиск, фильтры и следующую страницу в API', async () => {
  contentApi.listMembershipLinkReviews.mockResolvedValue({ data: { ...response, total: 120 } });
  await renderPage();

  const search = container.querySelector('[aria-label="Поиск связи"]');
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(search, 'Анна');
    search.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(resolve => setTimeout(resolve, 300));
  });

  const status = container.querySelector('[aria-label="Статус проверки"]');
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(status, 'all');
    status.dispatchEvent(new Event('change', { bubbles: true }));
  });

  const reason = container.querySelector('[aria-label="Причина проверки"]');
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(reason, 'name_only');
    reason.dispatchEvent(new Event('change', { bubbles: true }));
  });

  await click('Далее');
  expect(contentApi.listMembershipLinkReviews).toHaveBeenLastCalledWith({
    q: 'Анна',
    status: 'all',
    reason: 'name_only',
    skip: 50,
    limit: 50,
  });
});

test('показывает ошибку загрузки', async () => {
  contentApi.listMembershipLinkReviews.mockRejectedValueOnce(new Error('offline'));
  await renderPage();

  expect(container.querySelector('[role="alert"]')?.textContent).toBe('Не удалось загрузить связи состава');
});
