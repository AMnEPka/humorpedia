/** @jest-environment node */

import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { ModuleRenderer as PersonModuleRenderer } from './PersonDetailPage';
import { ModuleRenderer as TeamModuleRenderer } from './TeamDetailPage';
import { ModuleRenderer as ShowModuleRenderer } from './ShowDetailPage';

// API requests are unrelated to rendering a supplied module and effects do not run in SSR.
jest.mock('../utils/api', () => ({ __esModule: true, default: {}, publicApi: {} }));

const renderModule = (Renderer, type, data, overrides = {}) => renderToStaticMarkup(
  <MemoryRouter>
    <Renderer module={{ id: 'contract-module', type, data, ...overrides }} index={3} />
  </MemoryRouter>
);

describe.each([
  ['person', PersonModuleRenderer],
  ['team', TeamModuleRenderer],
  ['show', ShowModuleRenderer],
])('%s page module contract', (_page, Renderer) => {
  test('renders a canonical gallery without requiring explicit visible=true', () => {
    const html = renderModule(Renderer, 'gallery', {
      title: 'Фотогалерея', images: [{ url: '/contract-image.jpg', caption: 'Сцена' }],
    });
    expect(html).toContain('src="/contract-image.jpg"');
    expect(html).toContain('alt="Сцена"');
    expect(html).toContain('Фотогалерея');
  });

  test('renders a canonical video', () => {
    const html = renderModule(Renderer, 'video', {
      url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', title: 'Выступление',
    });
    expect(html).toContain('<iframe');
    expect(html).toContain('src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"');
    expect(html).toContain('title="Выступление"');
  });

  test('renders a quote through the shared renderer', () => {
    const html = renderModule(Renderer, 'quote', { text: 'Текст цитаты', author: 'Автор цитаты' });
    expect(html).toContain('<blockquote');
    expect(html).toContain('Текст цитаты');
    expect(html).toContain('Автор цитаты');
  });

  test('renders the editor table format', () => {
    const html = renderModule(Renderer, 'table', {
      title: 'Результаты', headers: ['Команда', 'Баллы'], rows: [['Команда А', '42']], hasHeaders: true,
    });
    expect(html).toContain('<table');
    expect(html).toContain('Результаты');
    expect(html).toContain('Команда А');
    expect(html).toContain('Баллы');
    expect(html).toContain('42');
  });

  test('exposes an unknown module instead of silently dropping it', () => {
    const html = renderModule(Renderer, 'unknown_contract_module', {});
    expect(html).toContain('role="alert"');
    expect(html).toContain('unknown_contract_module');
  });

  test('preserves the page text and timeline rendering', () => {
    const textHtml = renderModule(Renderer, 'text_block', { title: 'Раздел', content: '<b>Биография</b>' });
    const timelineHtml = renderModule(Renderer, 'timeline', {
      title: 'Карьера', events: [{ year: '2007-2013', title: 'Начало', description: '<b>Событие</b>' }],
    });
    expect(textHtml).toContain('Раздел');
    expect(textHtml).toContain('<b>Биография</b>');
    expect(timelineHtml).toContain('2007-2013');
    expect(timelineHtml).toContain('<b>Событие</b>');
  });
});

test('preserves person text and timeline anchors used by the page TOC', () => {
  expect(renderModule(PersonModuleRenderer, 'text_block', { title: 'Раздел', content: 'Текст' }))
    .toContain('id="section-3"');
  const timelineHtml = renderModule(PersonModuleRenderer, 'timeline', {
    events: [{ year: '2020', title: 'Событие' }],
  });
  expect(timelineHtml).toContain('id="timeline-3"');
  expect(timelineHtml).toContain('id="timeline-3-event-0"');
});

test('preserves team text and timeline anchors used by the page TOC', () => {
  expect(renderModule(TeamModuleRenderer, 'text_block', { title: 'Раздел', content: 'Текст' }))
    .toContain('id="section-contract-module"');
  expect(renderModule(TeamModuleRenderer, 'timeline', { items: [{ year: '2020', title: 'Событие' }] }))
    .toContain('id="timeline-2020"');
});

test.each(['text_block', 'gallery', 'unknown_contract_module'])('show hides explicitly invisible %s modules', (type) => {
  expect(renderModule(ShowModuleRenderer, type, { content: 'Скрытый текст', images: [] }, { visible: false }))
    .toBe('');
});

test('keeps the specialized show participants renderer and person links', () => {
  const html = renderModule(ShowModuleRenderer, 'participants', {
    title: 'Участники шоу',
    items: [{
      name: 'Участник', person_slug: 'participant', person_url: '/people/participant',
      photo: '/participant.jpg', facts: [{ title: 'Роль', value: 'Ведущий' }],
    }],
  });
  expect(html).toContain('Участники шоу');
  expect(html).toContain('href="/people/participant"');
  expect(html).toContain('Ведущий');
});
