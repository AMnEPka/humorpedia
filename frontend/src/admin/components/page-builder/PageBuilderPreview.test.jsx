import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import PageBuilderPreview from './PageBuilderPreview';

jest.mock('@/public/pages/PersonDetailPage', () => function PersonDetailPage({ previewDocument }) {
  return <div data-testid="preview-document">{previewDocument.title}{(previewDocument.modules || []).map((module, index) => <div key={index} dangerouslySetInnerHTML={{ __html: module.data?.content || '' }} />)}</div>;
});
jest.mock('@/public/pages/TeamDetailPage', () => () => <div />);
jest.mock('@/public/pages/ShowDetailPage', () => () => <div />);

let host;
let root;
let frameStyle;
let frameStylesheet;
let originalCreateObjectUrl;
let originalRevokeObjectUrl;
const noAssets = [];
const imageAsset = [{ id: 'asset_123' }];

beforeEach(() => {
  originalCreateObjectUrl = URL.createObjectURL;
  originalRevokeObjectUrl = URL.revokeObjectURL;
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  frameStyle = document.createElement('style');
  frameStyle.dataset.previewTestCss = 'true';
  frameStyle.textContent = '.preview-test { color: rgb(1, 2, 3); }';
  document.head.appendChild(frameStyle);
  frameStylesheet = document.createElement('link');
  frameStylesheet.rel = 'stylesheet';
  frameStylesheet.dataset.previewTestCss = 'true';
  frameStylesheet.href = '/preview-test.css';
  document.head.appendChild(frameStylesheet);
});

afterEach(async () => {
  await act(async () => root.unmount());
  if (originalCreateObjectUrl) URL.createObjectURL = originalCreateObjectUrl;
  else delete URL.createObjectURL;
  if (originalRevokeObjectUrl) URL.revokeObjectURL = originalRevokeObjectUrl;
  else delete URL.revokeObjectURL;
  frameStyle.remove();
  frameStylesheet.remove();
  host.remove();
});

async function render({ page = { title: 'Проверяемая страница' }, assets = noAssets, getAsset } = {}) {
  await act(async () => root.render(
    <PageBuilderPreview kind="person" ownerId="draft-1" page={page} assets={assets} getAsset={getAsset} />,
  ));
}

test('renders one isolated responsive viewport and switches its layout width', async () => {
  await render();
  const iframe = host.querySelector('iframe');

  expect(iframe).not.toBeNull();
  expect(iframe.getAttribute('sandbox')).toBe('allow-same-origin');
  expect(iframe.srcdoc).toContain('name="viewport"');
  expect(iframe.srcdoc).not.toContain('<script');
  expect(iframe.style.width).toBe('1120px');
  expect(iframe.style.height).toBe('650px');

  await act(async () => Array.from(host.querySelectorAll('button')).find((button) => button.textContent.includes('Телефон')).click());
  expect(iframe.style.width).toBe('390px');
  expect(iframe.style.height).toBe('650px');
});

test('copies parent stylesheets into the frame and portals the live public page there', async () => {
  await render();
  const iframe = host.querySelector('iframe');
  const frameDocument = iframe.contentDocument;
  if (!frameDocument.body) frameDocument.documentElement.appendChild(frameDocument.createElement('body'));
  if (!frameDocument.getElementById('page-preview-root')) {
    const rootNode = frameDocument.createElement('div');
    rootNode.id = 'page-preview-root';
    frameDocument.body.appendChild(rootNode);
  }
  await act(async () => iframe.dispatchEvent(new Event('load')));

  expect(frameDocument.head.querySelector('style[data-preview-test-css="true"]')?.textContent).toContain('.preview-test');
  expect(frameDocument.head.querySelector('link[data-preview-test-css="true"]')?.href).toBe(frameStylesheet.href);
  expect(frameDocument.body.textContent).toContain('Проверяемая страница');
  expect(host.textContent).not.toContain('Проверяемая страница');
});

test('resolves private asset references embedded inside module HTML', async () => {
  URL.createObjectURL = jest.fn(() => 'blob:private-preview-image');
  URL.revokeObjectURL = jest.fn();
  const getAsset = jest.fn().mockResolvedValue({ data: new Blob(['image']) });
  await render({
    assets: imageAsset,
    getAsset,
    page: { title: 'Проверяемая страница', modules: [{ data: { content: '<p><img src="asset:asset_123" alt="Портрет"></p>' } }] },
  });
  const iframe = host.querySelector('iframe');
  const frameDocument = iframe.contentDocument;
  if (!frameDocument.body) frameDocument.documentElement.appendChild(frameDocument.createElement('body'));
  if (!frameDocument.getElementById('page-preview-root')) {
    const rootNode = frameDocument.createElement('div');
    rootNode.id = 'page-preview-root';
    frameDocument.body.appendChild(rootNode);
  }
  await act(async () => iframe.dispatchEvent(new Event('load')));
  await act(async () => { await Promise.resolve(); });

  expect(getAsset).toHaveBeenCalledWith('draft-1', 'asset_123');
  expect(frameDocument.querySelector('img')?.getAttribute('src')).toBe('blob:private-preview-image');
});
