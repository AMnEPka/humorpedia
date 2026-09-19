import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import Header from './Header';
import publicApi from '../utils/api';

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

jest.mock('../utils/api', () => ({
  __esModule: true,
  default: {
    getSections: jest.fn(),
    searchAutocomplete: jest.fn(),
  },
}));

let host;
let root;

beforeEach(() => {
  jest.useFakeTimers();
  jest.clearAllMocks();
  publicApi.getSections.mockResolvedValue({ data: { items: [] } });
  publicApi.searchAutocomplete.mockResolvedValue({
    data: [
      { id: 'person-1', title: 'Александр Гудков', type: 'person', path: '/people/aleksandr-gudkov' },
    ],
  });
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  jest.useRealTimers();
});

test('offers the full search page after autocomplete suggestions', async () => {
  await act(async () => {
    root.render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>
    );
  });

  await act(async () => {
    host.querySelector('[aria-label="Открыть поиск"]').click();
  });

  const input = host.querySelector('input[placeholder="Поиск..."]');
  const valueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    'value'
  ).set;
  await act(async () => {
    valueSetter.call(input, 'Гу');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    jest.advanceTimersByTime(300);
    await Promise.resolve();
  });

  expect(publicApi.searchAutocomplete).toHaveBeenCalledWith('Гу');
  expect(host.textContent).toContain('Александр Гудков');

  const allResultsButton = Array.from(host.querySelectorAll('button')).find((button) =>
    button.textContent.includes('Показать все результаты по запросу «Гу»')
  );
  expect(allResultsButton).toBeTruthy();

  await act(async () => allResultsButton.click());
  expect(mockNavigate).toHaveBeenCalledWith('/search?q=%D0%93%D1%83');
});
