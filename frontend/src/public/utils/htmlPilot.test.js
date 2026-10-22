import { beginPage, commitPage, isHtmlPilotEnabled } from './htmlPilot';

beforeEach(() => {
  window.__HTML_PILOT__ = true;
  document.head.innerHTML = '<title>Сервер SEO</title><meta name="description" content="Сервер"><link rel="canonical" href="https://humorpedia.ru/people/a">';
  document.body.innerHTML = '<section id="html-pilot-fallback" data-path="/people/a">Исходный текст</section><div id="root" hidden aria-hidden="true">React</div>';
});
afterEach(() => { delete window.__HTML_PILOT__; });
const metadata = { title: 'Новый SEO', description: '<script>literal</script>', canonical_url: 'https://humorpedia.ru/people/b', robots: 'noindex,follow', og_type: 'website', image_url: 'https://humorpedia.ru/image.png', image_alt: 'Имя', locale: 'ru_RU', lang: 'ru' };
test('keeps server head while loading and performs atomic handoff', () => {
  const token = beginPage('/people/a');
  expect(document.title).toBe('Сервер SEO');
  expect(document.getElementById('root').hidden).toBe(true);
  expect(commitPage(token, {status: 'ready', metadata})).toBe(true);
  expect(document.title).toBe('Новый SEO');
  expect(document.getElementById('html-pilot-fallback')).toBeNull();
  expect(document.getElementById('root').hidden).toBe(false);
  expect(document.querySelector('meta[name="description"]').content).toBe(metadata.description);
  expect(document.head.querySelector('script')).toBeNull();
});
test('stale token cannot commit including A to B to A', () => {
  const first = beginPage('/people/a'); beginPage('/people/b'); const last = beginPage('/people/a');
  expect(commitPage(first, {status: 'ready', metadata})).toBe(false);
  expect(document.title).toBe('Сервер SEO');
  expect(commitPage(last, {status: 'ready', metadata: null})).toBe(true);
  expect(document.title).toBe('Humorpedia | humorpedia.ru');
});
test('network failure preserves fallback and head, confirmed 404 removes it and noindexes', () => {
  const token = beginPage('/people/a');
  commitPage(token, {status: 'network_error', metadata: null});
  expect(document.getElementById('html-pilot-fallback')).not.toBeNull();
  expect(document.querySelector('[role="status"]').textContent).toContain('Не удалось');
  expect(document.title).toBe('Сервер SEO');
  commitPage(token, {status: 'not_found', metadata: null});
  expect(document.getElementById('html-pilot-fallback')).toBeNull();
  expect(document.querySelector('link[rel="canonical"]')).toBeNull();
  expect(document.querySelector('meta[name="robots"]').content).toBe('noindex,follow');
  expect(document.getElementById('root').hidden).toBe(false);
});
test('uncovered route and null metadata after SPA navigation clear stale head', () => {
  commitPage(beginPage('/people/a'), {status:'ready', metadata});
  beginPage('/articles');
  expect(document.querySelector('link[rel="canonical"]')).toBeNull();
  expect(document.title).toBe('Humorpedia | humorpedia.ru');
  expect(document.querySelector('meta[name="robots"]')).toBeNull();
  commitPage(beginPage('/people/b'), {status:'ready', metadata:null});
  expect(document.title).toBe('Humorpedia | humorpedia.ru');
});
test.each([false, undefined, 'true', 1])('flag %p is disabled and leaves DOM untouched', flag => {
  window.__HTML_PILOT__ = flag;
  const original = document.documentElement.innerHTML;
  expect(isHtmlPilotEnabled()).toBe(false);
  expect(commitPage(beginPage('/articles'), {status:'not_found', metadata})).toBe(false);
  expect(document.documentElement.innerHTML).toBe(original);
});
test('SPA network failure clears the previous document metadata without initial fallback', () => {
  commitPage(beginPage('/people/a'), {status:'ready', metadata});
  const next = beginPage('/people/b');
  commitPage(next, {status:'network_error', metadata:null});
  expect(document.querySelector('link[rel="canonical"]')).toBeNull();
  expect(document.querySelector('meta[property="og:title"]')).toBeNull();
  expect(document.title).toBe('Humorpedia | humorpedia.ru');
  expect(document.getElementById('root').hidden).toBe(false);
});

test.each([false, undefined, 'true', 1])('neutral flag %p is strict', value => {
  window.__HTML_PILOT__ = false;
  window.__PUBLIC_HTML_ENABLED__ = value;
  expect(isHtmlPilotEnabled()).toBe(false);
  delete window.__PUBLIC_HTML_ENABLED__;
});
test('neutral runtime boolean enables the same navigation guard', () => {
  window.__HTML_PILOT__ = false;
  window.__PUBLIC_HTML_ENABLED__ = true;
  expect(isHtmlPilotEnabled()).toBe(true);
  const old = beginPage('/people/a', 'repeat');
  beginPage('/people/b', 'b');
  const current = beginPage('/people/a', 'repeat');
  expect(commitPage(old, {status:'ready', metadata})).toBe(false);
  expect(commitPage(current, {status:'ready', metadata})).toBe(true);
  delete window.__PUBLIC_HTML_ENABLED__;
});
