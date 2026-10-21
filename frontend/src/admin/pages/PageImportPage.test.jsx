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
