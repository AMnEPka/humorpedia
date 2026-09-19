import { TEAM_PROJECTS_TITLE } from '../components/TeamProjects';

jest.mock('../utils/api', () => ({ __esModule: true, default: {} }));

import { teamTocItems } from './TeamDetailPage';

const modules = [
  { id: 'history', type: 'text_block', data: { title: 'История команды' } },
  {
    id: 'legacy-projects',
    type: 'text_block',
    data: { title: 'Сторонние проекты команды после/во время игры в КВН' },
  },
  { id: 'facts', type: 'text_block', data: { title: 'Интересные факты' } },
];

test('replaces the legacy TOC item with one dynamic project section at the same position', () => {
  expect(teamTocItems(modules, 'auto', true)).toEqual([
    { id: 'section-history', label: 'История команды', title: 'История команды' },
    { id: 'section-team-projects', label: TEAM_PROJECTS_TITLE, title: TEAM_PROJECTS_TITLE },
    { id: 'section-facts', label: 'Интересные факты', title: 'Интересные факты' },
  ]);
});

test('adds an automatic-only project section and omits an empty legacy item', () => {
  const withoutLegacy = modules.filter((module) => module.id !== 'legacy-projects');
  expect(teamTocItems(withoutLegacy, 'auto', true).at(-1)).toEqual({
    id: 'section-team-projects',
    label: TEAM_PROJECTS_TITLE,
    title: TEAM_PROJECTS_TITLE,
  });
  expect(teamTocItems(modules, 'auto', false).map((item) => item.label)).not.toContain(TEAM_PROJECTS_TITLE);
});
