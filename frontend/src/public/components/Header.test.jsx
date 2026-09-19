/** @jest-environment node */

import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import Header from './Header';

jest.mock('../utils/api', () => ({
  __esModule: true,
  default: {
    getSections: jest.fn(),
    searchAutocomplete: jest.fn(),
  },
}));

test('public header does not show unfinished authorization actions', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <Header />
    </MemoryRouter>
  );

  expect(html).not.toContain('href="/login"');
  expect(html).not.toContain('href="/register"');
  expect(html).not.toContain('>Войти<');
  expect(html).not.toContain('>Регистрация<');
});
