import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';

import CorrectionSuggestionButton from './CorrectionSuggestionButton';
import { publicApi } from '../utils/api';


jest.mock('../utils/api', () => ({
  publicApi: {
    createCorrectionSuggestion: jest.fn(),
  },
}));


let host;
let root;

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  publicApi.createCorrectionSuggestion.mockResolvedValue({ data: { id: 'suggestion-1' } });
  document.title = 'Тестовая страница';
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  document.body.innerHTML = '';
  jest.clearAllMocks();
});


test('opens a plain-text correction form for the current page', async () => {
  await act(async () => {
    root.render(
      <MemoryRouter initialEntries={['/people/test-person']}>
        <h1>Тестовый человек</h1>
        <CorrectionSuggestionButton />
      </MemoryRouter>
    );
  });

  const trigger = host.querySelector('button[aria-label="Предложить исправление"]');
  expect(trigger).not.toBeNull();
  await act(async () => trigger.click());

  expect(document.body.textContent).toContain('Укажите раздел и опишите, что нужно исправить');
  expect(document.body.textContent).toContain('Тестовый человек');
  expect(document.body.querySelector('textarea')).not.toBeNull();
  expect(document.body.querySelector('input[type="email"]')).not.toBeNull();
  expect(document.body.querySelector('[contenteditable="true"]')).toBeNull();
});
