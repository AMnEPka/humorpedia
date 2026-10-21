import React, { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import ModuleEditor from './ModuleEditor';

jest.mock('./RichTextEditor', () => ({ __esModule: true, default: () => null }));
jest.mock('../utils/api', () => ({ contentApi: {} }));

let host, root, saved;
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement('div'); document.body.appendChild(host);
  root = createRoot(host); saved = null;
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });

function mount(initial) {
  function Harness() {
    const [modules, setModules] = useState(initial);
    return <ModuleEditor modules={modules} onChange={next => { saved = next; setModules(next); }} />;
  }
  act(() => root.render(<Harness />));
}
async function editFirst() {
  const row = host.querySelector('.bg-white.border.rounded-lg');
  await act(async () => row.querySelectorAll('button')[1].click());
}
async function save() {
  const button = [...document.querySelectorAll('[role="dialog"] button')].find(x => x.textContent === 'Сохранить');
  await act(async () => button.click());
}
function field(label, value) {
  const input = document.querySelector('input[aria-label="' + label + '"]');
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}

test('edits one gallery field, saves and reopens without changing any other JSON', async () => {
  const initial = [{ id: 'gallery', type: 'gallery', order: 7, visible: false, imported: 'keep',
    data: { title: 'Галерея', extra: { x: 1 }, images: [{ url: '/photo.jpg', caption: 'old', alt: 'описание', legacy_id: 5 }] } },
    { id: 'other', type: 'quote', data: { text: 'Сосед', extra: true } }];
  mount(initial); await editFirst();
  expect(saved).toBeNull();
  field('Изображение 1: подпись', 'new');
  expect(saved).toBeNull(); // The page becomes edited only on dialog save, as before.
  await save();
  expect(saved).toEqual([{ ...initial[0], data: { ...initial[0].data, images: [{ ...initial[0].data.images[0], caption: 'new' }] } }, initial[1]]);
  expect(initial[0].data.images[0].caption).toBe('old');
  await editFirst();
  expect(document.querySelector('input[aria-label="Изображение 1: подпись"]').value).toBe('new');
});

test('an unsupported compatible module survives opening and saving unchanged', async () => {
  const initial = [{ id: 'unknown', type: 'future_module', order: 4, visible: false, extra: true,
    data: { opaque: { nested: [1, 2, { x: 'keep' }] } } }];
  mount(initial); await editFirst();
  expect(document.querySelector('[role="dialog"]').textContent).toContain('Имеющиеся данные сохраняются');
  await save(); expect(saved).toEqual(initial);
});

function change(input, value) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}

test('legacy timeline edit retains event metadata and canonicalizes only the items alias', async () => {
  const initial = [{ id: 'timeline', type: 'timeline', order: 2, data: {
    imported: 'keep', items: [{ year: '2001', title: 'Событие', description: '<b>Текст</b>', extension: { a: 1 } }],
  } }];
  mount(initial); await editFirst();
  change(document.querySelector('input[placeholder="2007-2013"]'), '2002-2003');
  await save();
  expect(saved).toEqual([{ ...initial[0], data: { imported: 'keep', events: [{ ...initial[0].data.items[0], year: '2002-2003' }] } }]);
});

test('text title edit synchronizes the list title without altering rich text or extensions', async () => {
  const initial = [{ id: 'text', type: 'text_block', title: 'Прежний', visible: false, order: 5,
    data: { title: 'Прежний', content: '<p><b>Текст</b></p>', extension: 7 } }];
  mount(initial); await editFirst();
  change(document.querySelector('input[placeholder="Биография"]'), 'Новый');
  await save();
  expect(saved).toEqual([{ ...initial[0], title: 'Новый', data: { ...initial[0].data, title: 'Новый' } }]);
});

test('table cell save/reopen changes only that cell and does not dirty the parent on open', async () => {
  const initial = [{ id: 'table', type: 'table', order: 4, imported: true,
    data: { title: 'Таблица', headers: ['Имя', 'Баллы'], rows: [['A', '10'], ['B', '12']], extension: { a: 1 } } }];
  mount(initial); await editFirst();
  expect(saved).toBeNull();
  change(document.querySelectorAll('[role="dialog"] tbody input')[3], '13');
  await save();
  expect(saved).toEqual([{ ...initial[0], data: { ...initial[0].data, rows: [['A', '10'], ['B', '13']] } }]);
  await editFirst();
  expect(document.querySelectorAll('[role="dialog"] tbody input')[3].value).toBe('13');
});

test('opening a table without headers initializes the existing header defaults only inside the draft', async () => {
  const initial = [{ id: 'table', type: 'table', data: { rows: [['A', '10']], extension: 8 } }];
  const errors = jest.spyOn(console, 'error').mockImplementation(() => {});
  try {
    mount(initial); await editFirst();
    expect(saved).toBeNull();
    expect(errors.mock.calls.flat().join(' ')).not.toContain('Cannot update a component');
    await save();
    expect(saved).toEqual([{ ...initial[0], data: { ...initial[0].data, headers: ['', ''] } }]);
  } finally { errors.mockRestore(); }
});

test('closing the dialog with Escape autosaves its current draft and preserves neighboring JSON', async () => {
  const initial = [{ id: 'gallery', type: 'gallery', order: 3, data: { extension: true,
    images: [{ url: '/image.jpg', caption: 'old', alt: 'keep' }] } },
    { id: 'neighbor', type: 'quote', data: { text: 'keep' } }];
  mount(initial); await editFirst();
  field('Изображение 1: подпись', 'saved on close');
  await act(async () => document.querySelector('[role="dialog"]').dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true })
  ));
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  expect(saved).toEqual([{ ...initial[0], data: { ...initial[0].data,
    images: [{ ...initial[0].data.images[0], caption: 'saved on close' }] } }, initial[1]]);
  expect(initial[0].data.images[0].caption).toBe('old');
});
