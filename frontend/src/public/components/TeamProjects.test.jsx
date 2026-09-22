import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';

import TeamProjects, {
  TEAM_PROJECTS_TITLE,
  hasManualTeamProjects,
  isProjectTeamUrl,
  isTeamProjectsModule,
  projectMemberCaption,
} from './TeamProjects';

const manualModule = {
  id: 'manual-projects',
  type: 'text_block',
  data: {
    title: 'Сторонние проекты команды после/во время игры в КВН',
    content: '<p>Авторское дополнение</p>',
  },
};

test('recognizes the legacy and current manual project block titles', () => {
  expect(isTeamProjectsModule(manualModule)).toBe(true);
  expect(isTeamProjectsModule({
    type: 'text_block',
    data: { title: TEAM_PROJECTS_TITLE },
  })).toBe(true);
  expect(isTeamProjectsModule({ type: 'text_block', data: { title: 'История команды' } })).toBe(false);
  expect(hasManualTeamProjects([manualModule])).toBe(true);
});

test('renders automatic projects and manual text in one section', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <TeamProjects
        manualModules={[manualModule]}
        items={[{
          show_id: 'improv',
          show_title: 'Импровизация. Команды',
          show_url: '/shows/improv-teams',
          members: [
            {
              person_id: 'person',
              person_name: 'Антон Остерников',
              person_url: '/people/anton-osternikov',
              caption: 'Участник проекта «Импровизация. Команды»',
              appearance_url: '/shows/improv-teams',
            },
            {
              person_id: 'second-person',
              person_name: 'Второй участник',
              person_url: '/people/second-person',
              caption: 'Финалист проекта «Импровизация. Команды»',
              appearance_url: '/shows/improv-teams',
            },
          ],
        }]}
      />
    </MemoryRouter>
  );

  expect(html).toContain(TEAM_PROJECTS_TITLE);
  expect(html).toContain('href="/shows/improv-teams"');
  expect(html).not.toContain('href="/people/anton-osternikov"');
  expect(html).toContain('Антон Остерников<span> — участник</span></span><span>, Второй участник');
  expect(html).toContain('Авторское дополнение');
  expect(html).not.toContain('По составу команды');
  expect(html).not.toContain('Дополнительная информация');
  expect(html).toContain('border-t');
  expect((html.match(new RegExp(TEAM_PROJECTS_TITLE, 'g')) || [])).toHaveLength(1);
});

test('uses the project page label for a legacy team appearance link', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <TeamProjects items={[{
        show_id: 'superliga',
        show_title: 'Суперлига',
        show_url: '/shows/superliga',
        members: [{
          person_id: 'person', person_name: 'Участник',
          caption: 'Участник проекта «Суперлига»',
          appearance_url: '/shows/superliga/teams/team',
        }],
      }]} />
    </MemoryRouter>
  );

  expect(html).toContain('к странице проекта');
  expect(html).not.toContain('к составу проекта');
});

test('keeps a manual-only section and hides a fully empty section', () => {
  const manualHtml = renderToStaticMarkup(
    <MemoryRouter><TeamProjects manualModules={[manualModule]} /></MemoryRouter>
  );
  const emptyHtml = renderToStaticMarkup(
    <MemoryRouter><TeamProjects manualModules={[]} items={[]} /></MemoryRouter>
  );

  expect(manualHtml).toContain('Авторское дополнение');
  expect(emptyHtml).toBe('');
});

test('offers a composition link only when it belongs to the displayed show', () => {
  const project = { show_url: '/shows/superliga' };
  expect(isProjectTeamUrl(project, { appearance_url: '/shows/superliga/teams/vyatka' })).toBe(true);
  expect(isProjectTeamUrl(project, { appearance_url: '/kvn/teams/vyatka' })).toBe(false);
  expect(isProjectTeamUrl(project, { appearance_url: '/shows/another-project' })).toBe(false);
});

test('shortens a person caption inside an already named project group', () => {
  expect(projectMemberCaption({ caption: 'Победитель проекта «Comedy Баттл»' })).toBe('победитель');
  expect(projectMemberCaption({
    caption: 'Участник проекта «Импровизация. Команды» в составе команды «Несносные»',
  })).toBe('участник в составе команды «Несносные»');
});
