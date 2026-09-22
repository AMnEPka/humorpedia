import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';

import ScrollRestoration from './ScrollRestoration';


function NavigationHarness() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <>
      <div data-testid="location">{location.pathname}</div>
      <button type="button" onClick={() => navigate('/detail')}>Открыть</button>
      <button type="button" onClick={() => navigate(-1)}>Назад</button>
    </>
  );
}


let host;
let root;
let maxScrollY;
let originalScrollTo;


function setScrollY(y) {
  Object.defineProperty(window, 'scrollY', {
    configurable: true,
    value: y,
  });
}


beforeEach(() => {
  jest.useFakeTimers();
  window.sessionStorage.clear();
  maxScrollY = 2000;
  setScrollY(0);

  originalScrollTo = window.scrollTo;
  window.scrollTo = jest.fn((_x, y) => {
    setScrollY(Math.min(y, maxScrollY));
  });

  Object.defineProperty(window.history, 'scrollRestoration', {
    configurable: true,
    writable: true,
    value: 'auto',
  });

  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
});


afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  window.scrollTo = originalScrollTo;
  window.sessionStorage.clear();
  jest.runOnlyPendingTimers();
  jest.useRealTimers();
});


test('opens a new URL at the top and restores the previous position on back', async () => {
  await act(async () => {
    root.render(
      <React.StrictMode>
        <MemoryRouter initialEntries={['/list']}>
          <ScrollRestoration />
          <NavigationHarness />
        </MemoryRouter>
      </React.StrictMode>
    );
  });

  setScrollY(640);
  await act(async () => host.querySelector('button').click());

  expect(host.querySelector('[data-testid="location"]').textContent).toBe('/detail');
  expect(window.scrollY).toBe(0);

  setScrollY(90);
  maxScrollY = 120;
  await act(async () => host.querySelectorAll('button')[1].click());

  expect(host.querySelector('[data-testid="location"]').textContent).toBe('/list');
  expect(window.scrollY).toBe(120);

  maxScrollY = 2000;
  await act(async () => jest.advanceTimersByTime(100));

  expect(window.scrollY).toBe(640);
});


test('cancels delayed restoration when the user starts interacting', async () => {
  await act(async () => {
    root.render(
      <React.StrictMode>
        <MemoryRouter initialEntries={['/list']}>
          <ScrollRestoration />
          <NavigationHarness />
        </MemoryRouter>
      </React.StrictMode>
    );
  });

  setScrollY(700);
  await act(async () => host.querySelector('button').click());

  maxScrollY = 100;
  await act(async () => host.querySelectorAll('button')[1].click());
  expect(window.scrollY).toBe(100);

  window.dispatchEvent(new WheelEvent('wheel'));
  maxScrollY = 2000;
  await act(async () => jest.advanceTimersByTime(500));

  expect(window.scrollY).toBe(100);
});
