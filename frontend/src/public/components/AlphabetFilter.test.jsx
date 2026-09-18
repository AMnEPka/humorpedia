/** @jest-environment node */

import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import AlphabetFilter, { RUSSIAN_ALPHABET } from './AlphabetFilter';

test('renders the full Russian alphabet and marks the selected letter', () => {
  const html = renderToStaticMarkup(
    <AlphabetFilter selectedLetter="Ё" onLetterClick={() => {}} />
  );

  expect(RUSSIAN_ALPHABET).toHaveLength(33);
  expect(html).toContain('aria-label="Фильтр по первой букве"');
  expect(html).toContain('aria-pressed="true"');
  expect(html).toContain('>Ё</button>');
  expect(html).toContain('>Й</button>');
  expect(html).toContain('>Ъ</button>');
  expect(html).toContain('>Ы</button>');
  expect(html).toContain('>Ь</button>');
  expect(html).toContain('Сбросить');
});

test('does not render reset action without an active letter', () => {
  const html = renderToStaticMarkup(
    <AlphabetFilter selectedLetter="" onLetterClick={() => {}} />
  );

  expect(html).not.toContain('Сбросить');
});
