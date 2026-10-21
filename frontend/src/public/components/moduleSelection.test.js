import { selectVisibleModules, selectPageModules } from './moduleSelection';

const block = (id, type, order, extra = {}) => ({ id, type, order, data: {}, ...extra });

test('visible ordering is stable, keeps omitted visibility/order and never mutates the input', () => {
  const modules = Object.freeze([
    block('late', 'image', 4), block('equal-a', 'text_block', 1),
    block('hidden', 'quote', -10, { visible: false }), block('first', 'gallery'),
    block('equal-b', 'video', 1),
  ]);
  expect(selectVisibleModules(modules).map(m => m.id)).toEqual(['first', 'equal-a', 'equal-b', 'late']);
  expect(modules.map(m => m.id)).toEqual(['late', 'equal-a', 'hidden', 'first', 'equal-b']);
  expect(selectVisibleModules()).toEqual([]);
});

test('sidebar markers, page TOC markers and entity/unknown blocks retain their existing placement', () => {
  const { sidebarModules, contentModules } = selectPageModules([
    block('text', 'text_block', 4), block('photo', 'poster_photo', 2),
    block('toc', 'table_of_contents', 3), block('entity', 'participants', 1),
    block('unknown', 'future_module', 0), block('facts', 'facts_table', 1),
  ]);
  expect(sidebarModules.map(m => m.id)).toEqual(['facts', 'photo']);
  expect(contentModules.map(m => m.id)).toEqual(['unknown', 'entity', 'toc', 'text']);
});

test('preview omits interactive/random modules using registry policy, preserving all other modules', () => {
  const types = ['poll', 'random_page', 'quiz_questions', 'quiz_results', 'rating_widget',
    'poster_photo', 'facts_table', 'text_block', 'table_of_contents', 'future_module'];
  const modules = types.map(type => block(type, type));
  const publicModules = selectPageModules(modules);
  expect(publicModules.sidebarModules.map(m => m.type)).toEqual(['rating_widget', 'poster_photo', 'facts_table']);
  const preview = selectPageModules(modules, { preview: true });
  expect(preview.sidebarModules.map(m => m.type)).toEqual(['poster_photo', 'facts_table']);
  expect(preview.contentModules.map(m => m.type)).toEqual(['text_block', 'table_of_contents', 'future_module']);
});

test('a domain exclusion only filters content and does not change sidebar or ordering', () => {
  const modules = [block('old-games', 'text_block', 1), block('photo', 'poster_photo'),
    block('new-games', 'games_list', 2), block('history', 'timeline', 3)];
  const result = selectPageModules(modules, { excludeContent: m => m.id === 'old-games' });
  expect(result.contentModules.map(m => m.id)).toEqual(['new-games', 'history']);
  expect(result.sidebarModules.map(m => m.id)).toEqual(['photo']);
});

test('legacy documents with modules:null retain an empty module list', () => {
  expect(selectVisibleModules(null)).toEqual([]);
  expect(selectPageModules(null)).toEqual({ sidebarModules: [], contentModules: [] });
});
