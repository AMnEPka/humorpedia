/** @jest-environment node */

import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import AlphabetFilter, {
  OTHER_ALPHABET_FILTER,
  RUSSIAN_ALPHABET,
} from './AlphabetFilter';

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
  expect(html).toContain('aria-label="Латиница, цифры и символы"');
  expect(html).toContain('>A–Z 0–9 #</button>');
  expect(html).toContain('Сбросить');
});

test('marks the combined Latin, digit and symbol group as selected', () => {
  const html = renderToStaticMarkup(
    <AlphabetFilter selectedLetter={OTHER_ALPHABET_FILTER} onLetterClick={() => {}} />
  );

  expect(html).toContain(
    'aria-label="Латиница, цифры и символы" aria-pressed="true"'
  );
  expect(html).toContain('Сбросить');
});

test('renders only filters that have matching names', () => {
  const html = renderToStaticMarkup(
    <AlphabetFilter
      selectedLetter=""
      onLetterClick={() => {}}
      availableLetters={['А', 'Ё']}
    />
  );

  expect(html).toContain('>А</button>');
  expect(html).toContain('>Ё</button>');
  expect(html).not.toContain('>Б</button>');
  expect(html).not.toContain('>Ъ</button>');
  expect(html).not.toContain('>Ы</button>');
  expect(html).not.toContain('>Ь</button>');
  expect(html).not.toContain('A–Z 0–9 #');
});

test('does not render reset action without an active letter', () => {
  const html = renderToStaticMarkup(
    <AlphabetFilter selectedLetter="" onLetterClick={() => {}} />
  );

  expect(html).not.toContain('Сбросить');
});
