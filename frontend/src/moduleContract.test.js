import definitions from './moduleContract.json';
import { canPreviewModule, isGenericModule, isSidebarModule } from './moduleContract';

const sidebarTypes = ['poster_photo', 'facts_table', 'tags_cloud', 'social_links', 'rating_widget'];
const hiddenInPreview = ['rating_widget', 'poll', 'random_page', 'quiz_questions', 'quiz_results'];
const entityTypes = [
  'participants', 'text', 'cast_list', 'seasons_list',
  'first_league_champions', 'vl_league_champions',
];
const quizTypes = ['quiz_questions', 'quiz_results'];
const systemTypes = [...sidebarTypes, 'table_of_contents'];

function expectedRendering(type, kind) {
  let owner;
  if (quizTypes.includes(type)) owner = 'quiz';
  else if (systemTypes.includes(type)) owner = 'system';
  else if (entityTypes.includes(type)) owner = 'entity';
  else if (kind === 'content' || kind === 'dynamic') owner = 'generic';
  else throw new Error(`Unclassified rendering owner: ${type} (${kind})`);

  return {
    owner,
    placement: sidebarTypes.includes(type) ? 'sidebar' : type === 'table_of_contents' ? 'page' : 'content',
    preview: !hiddenInPreview.includes(type),
  };
}

test.each(definitions)('$type declares the rendering contract', (definition) => {
  expect(definition.rendering).toEqual(expectedRendering(definition.type, definition.kind));
});

test('render helpers use registry metadata and preserve unknown-module diagnostics', () => {
  expect(isSidebarModule('poster_photo')).toBe(true);
  expect(isSidebarModule('table_of_contents')).toBe(false);
  expect(isGenericModule('poll')).toBe(true);
  expect(isGenericModule('participants')).toBe(false);
  expect(isGenericModule('unregistered_future_module')).toBe(true);
  expect(isGenericModule('toString')).toBe(true);
  expect(isGenericModule('constructor')).toBe(true);
  expect(isGenericModule('__proto__')).toBe(true);
  expect(canPreviewModule('poll')).toBe(false);
  expect(canPreviewModule('text_block')).toBe(true);
  expect(canPreviewModule('unregistered_future_module')).toBe(true);
});
