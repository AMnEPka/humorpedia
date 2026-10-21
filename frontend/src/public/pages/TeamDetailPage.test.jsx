import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import TeamDetailPage from './TeamDetailPage';
import publicApi from '../utils/api';

jest.mock('../utils/api', () => ({
  __esModule: true,
  default: { getTeam: jest.fn(), getTeamByPath: jest.fn(), getTeamMembers: jest.fn(), getTeamProjects: jest.fn() },
}));
jest.mock('../utils/share', () => ({ sharePage: jest.fn() }));

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

test('renders preview membership relations through the normal roster card without API calls', async () => {
  const relations = [
    { id: 'member-current', kind: 'membership', name: 'Антон', target: { type: 'person', slug: 'anton' }, roles: ['капитан'], from_year: 2020 },
    { id: 'member-former', kind: 'membership', name: 'Сергей', roles: ['игрок'], to_year: 2019 },
  ];
  await act(async () => root.render(
    <MemoryRouter>
      <TeamDetailPage preview previewDocument={{ title: 'Команда', slug: 'komanda', modules: [], facts: {} }} previewRelations={relations} />
    </MemoryRouter>,
  ));

  expect(host.textContent).toContain('Состав команды');
  expect(host.querySelector('a[href="/people/anton"]')?.textContent).toContain('Антон');
  expect(host.textContent).toContain('Бывшие участники');
  expect(host.textContent).toContain('Сергей');
  expect(publicApi.getTeamMembers).not.toHaveBeenCalled();
  expect(publicApi.getTeam).not.toHaveBeenCalled();
});
