import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';

import EditorialProposalsPage from './EditorialProposalsPage';
import { contentApi, editorialProposalsApi } from '../utils/api';

jest.mock('../utils/api', () => ({
  contentApi: { searchPeople: jest.fn() },
  editorialProposalsApi: { list: jest.fn(), create: jest.fn(), decide: jest.fn() },
  getErrorMessage: (_error, fallback) => fallback,
}));

let host;
let root;

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  contentApi.searchPeople.mockResolvedValue({ data: [] });
  editorialProposalsApi.decide.mockResolvedValue({ data: {} });
  editorialProposalsApi.create.mockResolvedValue({ data: {} });
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  jest.clearAllMocks();
});

async function renderProposal(item) {
  editorialProposalsApi.list.mockResolvedValue({ data: { items: [item], total: 1 } });
  await act(async () => root.render(<MemoryRouter><EditorialProposalsPage /></MemoryRouter>));
  await act(async () => { await Promise.resolve(); });
}

function click(label) {
  const button = Array.from(host.querySelectorAll('button')).find((element) => element.textContent === label);
  if (!button) throw new Error(`Button not found: ${label}`);
  return act(async () => { button.click(); });
}

test('sends edited acceptance and rejection as separate decisions', async () => {
  await renderProposal({
    _id: 'proposal-1', kind: 'update_person', person_id: 'person-1', person_title: 'Комик', status: 'new',
    changes: [
      { id: 'bio-1', field: 'bio.birth_place', old_value: '', proposed_value: 'Москва', status: 'pending', sources: [{ url: 'https://example.org/interview', title: 'Интервью' }] },
      { id: 'fact-1', field: 'facts.Профессия', old_value: 'Актёр', proposed_value: 'Комик', status: 'pending', sources: [{ url: 'https://example.org/profile', title: 'Профиль' }] },
    ],
  });

  expect(host.textContent).toContain('Интервью');
  const edit = host.querySelector('textarea[aria-label="Предлагаемое значение: Место рождения"]');
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(edit, 'Санкт-Петербург');
    edit.dispatchEvent(new Event('input', { bubbles: true }));
  });
  const groups = host.querySelectorAll('[aria-label^="Решение:"]');
  await act(async () => { groups[0].querySelector('button').click(); });
  await act(async () => { groups[1].querySelectorAll('button')[1].click(); });
  await click('Сохранить решения');

  expect(editorialProposalsApi.decide).toHaveBeenCalledWith('proposal-1', {
    decisions: [
      { change_id: 'bio-1', decision: 'accept', edited_value: 'Санкт-Петербург' },
      { change_id: 'fact-1', decision: 'reject' },
    ],
  });
});

test('new candidate stays outside people until an explicit accepted decision', async () => {
  editorialProposalsApi.list.mockResolvedValue({ data: { items: [], total: 0 } });
  await renderProposal({
    _id: 'candidate-1', kind: 'new_person', candidate_name: 'Николай Андреев', slug: 'nikolay-andreev', status: 'new',
    changes: [{ id: 'occupation-1', field: 'bio.occupation', old_value: null, proposed_value: ['стендап-комик'], status: 'pending', sources: [{ url: 'https://example.org/comedian', title: 'Клуб' }] }],
  });
  await click('Новые люди');
  expect(host.textContent).toContain('Николай Андреев');
  expect(editorialProposalsApi.decide).not.toHaveBeenCalled();
  const choice = host.querySelector('[aria-label="Решение: Профессии"] button');
  await act(async () => { choice.click(); });
  await click('Сохранить решения и создать страницу');
  expect(editorialProposalsApi.decide).toHaveBeenCalledWith('candidate-1', {
    decisions: [{ change_id: 'occupation-1', decision: 'accept' }],
    person: { title: 'Николай Андреев', full_name: 'Николай Андреев', slug: 'nikolay-andreev' },
  });
});

test('imports a research JSON file into the review queue', async () => {
  editorialProposalsApi.list.mockResolvedValue({ data: { items: [], total: 0 } });
  await act(async () => root.render(<MemoryRouter><EditorialProposalsPage /></MemoryRouter>));
  await act(async () => { await Promise.resolve(); });

  const input = host.querySelector('input[type="file"]');
  const proposal = { kind: 'new_person', candidate_name: 'Комик', changes: [] };
  Object.defineProperty(input, 'files', {
    configurable: true,
    value: [{ text: async () => JSON.stringify({ proposals: [proposal] }) }],
  });
  await act(async () => { input.dispatchEvent(new Event('change', { bubbles: true })); });
  await click('Загрузить в очередь');

  expect(editorialProposalsApi.create).toHaveBeenCalledWith(proposal);
  expect(host.textContent).toContain('Обработано предложений: 1');
});
