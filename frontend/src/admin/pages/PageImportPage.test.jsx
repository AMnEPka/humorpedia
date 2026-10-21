import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import PageImportPage from './PageImportPage';
import { pagePackagesApi } from '../utils/api';

jest.mock('../utils/api', () => ({
  pagePackagesApi: { preview: jest.fn(), getPreview: jest.fn(), getAsset: jest.fn(), apply: jest.fn() },
  getErrorMessage: (_error, fallback) => fallback,
}));
jest.mock('../components/page-builder/PageBuilderPreview', () => () => <div>Предпросмотр пакета</div>);

let host;
let root;
const preview = {
  id: 'package-1', hash: 'hash-1', kind: 'person', status: 'preview',
  page: { title: 'Комик', slug: 'komik', full_name: 'Комик', facts: {}, modules: [] },
  relations: [{ id: 'relation-1', kind: 'appearance', target: { type: 'show', slug: 'show-a' } }],
  assets: [], warnings: [], conflicts: [],
};

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  pagePackagesApi.preview.mockResolvedValue({ data: preview });
  pagePackagesApi.apply.mockResolvedValue({ data: { ...preview, status: 'applied', result: { id: 'page-1', url: '/people/komik', edit_url: '/admin/people/page-1' } } });
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  jest.clearAllMocks();
});

async function render() {
  await act(async () => root.render(<MemoryRouter><PageImportPage /></MemoryRouter>));
}

function button(label) {
  const found = Array.from(host.querySelectorAll('button')).find((node) => node.textContent.includes(label));
  if (!found) throw new Error(`Button not found: ${label}`);
  return found;
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function chooseZip(name) {
  const input = host.querySelector('input[type="file"]');
  const file = new File(['package'], name, { type: 'application/zip' });
  Object.defineProperty(input, 'files', { configurable: true, value: [file] });
  await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
  return file;
}

test('previews an uploaded package without creating a page', async () => {
  await render();
  const input = host.querySelector('input[type="file"]');
  Object.defineProperty(input, 'files', { configurable: true, value: [new File(['package'], 'page.zip', { type: 'application/zip' })] });
  await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
  await act(async () => button('Проверить архив').click());

  expect(pagePackagesApi.preview).toHaveBeenCalled();
  expect(pagePackagesApi.apply).not.toHaveBeenCalled();
  expect(host.textContent).toContain('Комик');
});

test('requires explicit review before applying and sends the package hash', async () => {
  await render();
  const input = host.querySelector('input[type="file"]');
  Object.defineProperty(input, 'files', { configurable: true, value: [new File(['package'], 'page.zip', { type: 'application/zip' })] });
  await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
  await act(async () => button('Проверить архив').click());
  expect(button('Создать и опубликовать').disabled).toBe(true);

  const review = host.querySelector('input[type="checkbox"][aria-label="Я проверил страницу и связи"]');
  await act(async () => { review.click(); });
  await act(async () => button('Создать и опубликовать').click());

  expect(pagePackagesApi.apply).toHaveBeenCalledWith('package-1', { hash: 'hash-1', reviewed: true, omit_relations: [] });
  expect(host.querySelector('a[href="/admin/people/page-1"]')).not.toBeNull();
  expect(host.querySelector('a[href="/people/komik"]')).not.toBeNull();
});

test('shows recoverable import errors and allows retrying the same reviewed package', async () => {
  pagePackagesApi.apply
    .mockRejectedValueOnce({ response: { data: { detail: 'Импорт прерван; исправьте причину и повторите применение' } } })
    .mockResolvedValueOnce({ data: { ...preview, status: 'applied', result: { id: 'page-1', url: '/people/komik', edit_url: '/admin/people/page-1' } } });
  pagePackagesApi.getPreview.mockResolvedValueOnce({ data: { ...preview, status: 'error', error: 'Импорт прерван; исправьте причину и повторите применение' } });
  await render();
  const input = host.querySelector('input[type="file"]');
  Object.defineProperty(input, 'files', { configurable: true, value: [new File(['package'], 'page.zip', { type: 'application/zip' })] });
  await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
  await act(async () => button('Проверить архив').click());
  await act(async () => host.querySelector('input[aria-label="Я проверил страницу и связи"]').click());
  await act(async () => button('Создать и опубликовать').click());

  expect(host.querySelector('[role="alert"]')?.textContent).toContain('Импорт прерван');
  expect(pagePackagesApi.getPreview).toHaveBeenCalledWith('package-1');
  expect(button('Повторить импорт').disabled).toBe(false);
  await act(async () => button('Повторить импорт').click());

  expect(pagePackagesApi.apply).toHaveBeenCalledTimes(2);
  expect(pagePackagesApi.apply).toHaveBeenLastCalledWith('package-1', { hash: 'hash-1', reviewed: true, omit_relations: [] });
  expect(host.textContent).toContain('Страница импортирована');
});

test('locks ZIP selection until preview completes, then allows a new package', async () => {
  const pending = deferred();
  const secondPreview = { ...preview, id: 'package-2', hash: 'hash-2', page: { ...preview.page, title: 'Второй комик' } };
  pagePackagesApi.preview.mockReturnValueOnce(pending.promise).mockResolvedValueOnce({ data: secondPreview });
  await render();
  await chooseZip('a.zip');
  await act(async () => button('Проверить архив').click());

  const input = host.querySelector('input[type="file"]');
  expect(input.disabled).toBe(true);
  expect(pagePackagesApi.apply).not.toHaveBeenCalled();
  await act(async () => pending.resolve({ data: preview }));
  expect(input.disabled).toBe(false);

  const secondFile = await chooseZip('b.zip');
  expect(host.textContent).not.toContain('Предпросмотр страницы:');
  await act(async () => button('Проверить архив').click());
  expect(pagePackagesApi.preview).toHaveBeenLastCalledWith(secondFile);
  expect(host.textContent).toContain('Второй комик');
  expect(button('Создать и опубликовать').disabled).toBe(true);
  await act(async () => host.querySelector('input[aria-label="Я проверил страницу и связи"]').click());
  await act(async () => button('Создать и опубликовать').click());
  expect(pagePackagesApi.apply).toHaveBeenCalledWith('package-2', { hash: 'hash-2', reviewed: true, omit_relations: [] });
});

test('unlocks ZIP selection after a failed preview', async () => {
  const pending = deferred();
  pagePackagesApi.preview.mockReturnValueOnce(pending.promise);
  await render();
  await chooseZip('a.zip');
  await act(async () => button('Проверить архив').click());
  const input = host.querySelector('input[type="file"]');
  expect(input.disabled).toBe(true);

  await act(async () => pending.reject(new Error('Preview failed')));
  expect(input.disabled).toBe(false);
  expect(host.querySelector('[role="alert"]').textContent).toContain('Не удалось проверить архив');
  const secondFile = await chooseZip('b.zip');
  await act(async () => button('Проверить архив').click());
  expect(pagePackagesApi.preview).toHaveBeenLastCalledWith(secondFile);
  expect(host.textContent).toContain('Предпросмотр страницы: Комик');
});

test('locks ZIP selection while applying the reviewed package', async () => {
  const pending = deferred();
  pagePackagesApi.apply.mockReturnValueOnce(pending.promise);
  await render();
  await chooseZip('a.zip');
  await act(async () => button('Проверить архив').click());
  await act(async () => host.querySelector('input[aria-label="Я проверил страницу и связи"]').click());
  await act(async () => button('Создать и опубликовать').click());
  expect(host.querySelector('input[type="file"]').disabled).toBe(true);

  await act(async () => pending.resolve({ data: { ...preview, status: 'applied', result: { edit_url: '/admin/people/page-1' } } }));
  expect(host.textContent).toContain('Страница импортирована');
  expect(host.querySelector('input[type="file"]')).toBeNull();
  expect(host.querySelector('a[href="/admin/people/page-1"]')).not.toBeNull();
});

test.each(['success', 'failure'])('locks ZIP selection through apply recovery %s, then allows another ZIP', async (outcome) => {
  const applying = deferred();
  const recovery = deferred();
  pagePackagesApi.apply.mockReturnValueOnce(applying.promise);
  pagePackagesApi.getPreview.mockReturnValueOnce(recovery.promise);
  await render();
  await chooseZip('a.zip');
  await act(async () => button('Проверить архив').click());
  await act(async () => host.querySelector('input[aria-label="Я проверил страницу и связи"]').click());
  await act(async () => button('Создать и опубликовать').click());

  await act(async () => applying.reject(new Error('Apply failed')));
  expect(pagePackagesApi.getPreview).toHaveBeenCalledWith('package-1');
  const input = host.querySelector('input[type="file"]');
  expect(input.disabled).toBe(true);
  await act(async () => {
    if (outcome === 'success') recovery.resolve({ data: { ...preview, status: 'error', error: 'Повторите импорт' } });
    else recovery.reject(new Error('Recovery failed'));
  });
  expect(input.disabled).toBe(false);
  const secondFile = await chooseZip('b.zip');
  expect(host.querySelector('input[aria-label="Я проверил страницу и связи"]')).toBeNull();
  await act(async () => button('Проверить архив').click());
  expect(pagePackagesApi.preview).toHaveBeenLastCalledWith(secondFile);
  expect(button('Создать и опубликовать').disabled).toBe(true);
  expect(pagePackagesApi.apply).toHaveBeenCalledTimes(1);
});
