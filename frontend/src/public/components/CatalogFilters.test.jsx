import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, useLocation, useSearchParams } from 'react-router-dom';
import CatalogFilters from './CatalogFilters';

const fields = [
  { name: 'city', label: 'Город', options: [{ value: 'Томск', label: 'Томск' }] },
  { name: 'sort', label: 'Порядок', options: [{ value: 'popular', label: 'По популярности' }] },
];

function Harness() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  return <>
    <CatalogFilters key={searchParams.toString()} fields={fields}
      searchParams={searchParams} setSearchParams={setSearchParams} />
    <output data-testid="url">{location.search}</output>
  </>;
}

let host;
let root;

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

test('applies catalog filters in the URL while preserving text and letter search', async () => {
  await act(async () => root.render(
    <MemoryRouter initialEntries={['/teams?q=Прима&letter=П&page=3']}><Harness /></MemoryRouter>
  ));

  await act(async () => {
    const city = host.querySelector('#catalog-filter-city');
    const sort = host.querySelector('#catalog-filter-sort');
    city.value = 'Томск';
    city.dispatchEvent(new Event('change', { bubbles: true }));
    sort.value = 'popular';
    sort.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await act(async () => host.querySelector('button[type="submit"]').click());

  const params = new URLSearchParams(host.querySelector('output').textContent);
  expect(params.get('q')).toBe('Прима');
  expect(params.get('letter')).toBe('П');
  expect(params.get('city')).toBe('Томск');
  expect(params.get('sort')).toBe('popular');
  expect(params.has('page')).toBe(false);
});

test('restores filters from a saved URL and resets only catalog filters', async () => {
  await act(async () => root.render(
    <MemoryRouter initialEntries={['/teams?q=Прима&city=Томск&sort=popular&page=2']}>
      <Harness />
    </MemoryRouter>
  ));

  expect(host.querySelector('#catalog-filter-city').value).toBe('Томск');
  expect(host.querySelector('#catalog-filter-sort').value).toBe('popular');
  await act(async () => [...host.querySelectorAll('button')].find(button => button.textContent === 'Сбросить фильтры').click());
  const params = new URLSearchParams(host.querySelector('output').textContent);
  expect(params.get('q')).toBe('Прима');
  expect(params.has('city')).toBe(false);
  expect(params.has('sort')).toBe(false);
  expect(params.has('page')).toBe(false);
});
