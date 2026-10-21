import {
  createModule, createModuleDraft, updateModuleData, reorderModules, replaceModule,
  withTimelineEvents, ensureTableHeaders, updateTableCell, updateTableHeader,
  appendTableRow, removeTableRow, appendTableColumn, removeTableColumn,
} from './operations';

const freeze = value => {
  if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); }
  return value;
};

const gallery = { id: 'stable', type: 'gallery', title: 'Фото', visible: false, order: 7,
  imported: { owner: 'legacy' }, data: { custom: { keep: true }, images: [
    { url: '/one.jpg', caption: 'Первая', alt: 'Описание', imported_id: 42 },
  ] } };

test('a module draft round-trips JSON and cannot mutate the original nested data', () => {
  const original = freeze(JSON.parse(JSON.stringify(gallery)));
  const draft = createModuleDraft(original);
  expect(draft).toEqual(original);
  draft.data.images[0].caption = 'Правка';
  draft.imported.owner = 'new';
  expect(original.data.images[0].caption).toBe('Первая');
  expect(original.imported.owner).toBe('legacy');
  expect(createModuleDraft(null)).toBeNull();
});

test('one data edit preserves identity, metadata, hidden state and all other modules', () => {
  const original = freeze([gallery, { id: 'other', type: 'future', data: { unknown: [1, 2] }, custom: 9 }]);
  const edited = updateModuleData(createModuleDraft(original[0]), {
    ...original[0].data, images: original[0].data.images.map(item => ({ ...item, caption: 'Правка' })),
  });
  const next = replaceModule(original, edited);
  expect(next).toEqual([{ ...gallery, data: { ...gallery.data, images: [
    { ...gallery.data.images[0], caption: 'Правка' },
  ] } }, original[1]]);
  expect(next[1]).toBe(original[1]);
  expect(original[0].data.images[0].caption).toBe('Первая');
});

test('text data title follows the existing title synchronization rule only for text blocks', () => {
  const block = freeze({ id: 't', type: 'text_block', title: 'old', data: { extra: true } });
  expect(updateModuleData(block, { ...block.data, title: 'new' })).toEqual({
    ...block, title: 'new', data: { extra: true, title: 'new' },
  });
  expect(updateModuleData(gallery, { ...gallery.data, title: 'new' }).title).toBe('Фото');
});

test('reordering preserves IDs/unknown fields, normalizes order and safely ignores cancelled/invalid drops', () => {
  const modules = freeze([gallery, { id: 'b', type: 'text_block', order: 99, data: { extra: true } }]);
  expect(reorderModules(modules, 'b', 'stable')).toEqual([
    { ...modules[1], order: 0 }, { ...modules[0], order: 1 },
  ]);
  expect(modules[0].order).toBe(7);
  for (const ids of [['b', null], ['b', 'missing'], ['missing', 'b'], ['b', 'b']]) {
    expect(reorderModules(modules, ...ids)).toBe(modules);
  }
  expect(createModule('quote', 2, 'new-id')).toEqual({ id: 'new-id', type: 'quote', order: 2, visible: true, data: {} });
});

test('editing legacy timeline events removes only the alias and keeps per-event extensions', () => {
  const data = freeze({ items: [{ year: '2001', description: '<b>Текст</b>', canonical: 'event-1' }], extra: { a: 1 } });
  const next = withTimelineEvents(data, data.items.map(item => ({ ...item, year: '2002' })));
  expect(next).toEqual({ extra: { a: 1 }, events: [{ ...data.items[0], year: '2002' }] });
  expect(data.items[0].year).toBe('2001');
});

test('a single table cell edit round-trips rows, headers and extensions without mutation', () => {
  const data = freeze({ title: 'Таблица', headers: ['Имя', 'Баллы'], rows: [['A', '10'], ['B', '12']],
    collapsed: true, sortable: true, custom: { source: 'import' } });
  expect(updateTableCell(data, 1, 1, '13')).toEqual({ ...data, rows: [['A', '10'], ['B', '13']] });
  expect(updateTableHeader(data, 1, 'Очки')).toEqual({ ...data, headers: ['Имя', 'Очки'] });
  expect(ensureTableHeaders(data)).toBe(data);
  const blank = ensureTableHeaders({ custom: 7, rows: [['a', 'b']] });
  expect(blank).toEqual({ custom: 7, rows: [['a', 'b']], headers: ['', ''] });
});

test('table row/column operations keep extensions and the last row/column', () => {
  const data = freeze({ headers: ['A', 'B'], rows: [['a', 'b']], custom: 8 });
  expect(appendTableRow(data)).toEqual({ ...data, rows: [['a', 'b'], ['', '']] });
  expect(removeTableRow(data, 0)).toBe(data);
  expect(removeTableColumn(appendTableColumn(data), 2)).toEqual(data);
  const single = freeze({ rows: [['x']], headers: ['X'], custom: 8 });
  expect(removeTableColumn(single, 0)).toBe(single);
  const hidden = freeze({ ...data, hasHeaders: false });
  expect(appendTableColumn(hidden)).toEqual({ ...hidden, rows: [['a', 'b', '']] });
  expect(removeTableColumn(hidden, 1)).toEqual({ ...hidden, rows: [['a']], headers: ['A', 'B'] });
});
