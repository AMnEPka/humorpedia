/** @jest-environment node */
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import ModuleRenderer from './ModuleRenderer';
import definitions from '@/moduleContract.json';
import { videoEmbedUrl, contentHref } from './AdditionalModules';

jest.mock('../utils/api', () => ({ __esModule: true, publicApi: {}, default: {} }));

const fixtures = {
  hero_card: { image: '/photo.jpg', caption: 'Подпись' },
  image: { url: '/photo.jpg' }, text_block: { content: 'Текст' },
  timeline: { events: [{ year: '2000–2005', title: 'Событие' }] },
  tags: { tags: ['КВН'] }, table: { headers: ['Год'], rows: [['2000']] },
  gallery: { images: [{ url: '/photo.jpg', caption: 'Фото' }] },
  video: { url: 'https://youtu.be/dQw4w9WgXcQ' }, quote: { text: 'Цитата' },
  team_members: { members: [{ name: 'Участник' }] },
  tv_appearances: { items: [{ show: 'Передача' }] },
  games_list: { games: [{ opponent: 'Команда' }] },
  episodes_list: { episodes: [{ title: 'Выпуск' }] },
  poll: { poll_id: 'poll-1' },
  person_card: { name: 'Человек' }, related_links: { links: [{ title: 'Материал', url: '/articles/a' }] },
  html: { content: '<b>Материал</b>' }, divider: {},
};
const render = (type, data = {}, visible = true) => renderToStaticMarkup(<MemoryRouter>
  <ModuleRenderer module={{ id: 'test', type, data, visible }} />
</MemoryRouter>);

test.each(definitions.filter(item => item.kind === 'content'))('$type имеет настоящий общий рендер', item => {
  expect(fixtures).toHaveProperty(item.type);
  const html = render(item.type, fixtures[item.type]);
  expect(html).not.toBe('');
  expect(html).not.toContain('role="alert"');
});
test.each(definitions.filter(item => ['system', 'special'].includes(item.kind)))('$type имеет явного внешнего владельца', item => {
  expect(item.owners.length).toBeGreaterThan(0);
  expect(render(item.type)).toBe('');
});
test.each(['unknown', 'image_gallery', 'video_embed'])('неизвестный или устаревший %s не исчезает молча', type => {
  expect(render(type)).toContain('role="alert"');
});
test.each(definitions)('$type соблюдает visible=false', item => {
  expect(render(item.type, {}, false)).toBe('');
});
test('пустая таблица имеет явное пустое состояние', () => expect(render('table')).toContain('Пока нет строк таблицы'));
test('обычная ссылка YouTube преобразуется в embed', () => {
  expect(videoEmbedUrl('https://www.youtube.com/watch?v=dQw4w9WgXcQ')).toBe('https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ');
  expect(videoEmbedUrl('javascript:alert(1)')).toBeNull();
  expect(render('video', { url: 'https://example.org/video' })).toContain('href="https://example.org/video"');
  expect(render('video', { url: 'javascript:alert(1)' })).not.toContain('href=');
});
test('адреса вложенных шоу и команд сохраняют путь', () => {
  expect(contentHref({ slug: 'one', full_path: 'show/season' }, 'show')).toBe('/shows/show/season');
  expect(contentHref({ slug: 'one', full_path: 'show/teams/one', show_id: 'show' }, 'team')).toBe('/shows/show/teams/one');
});
