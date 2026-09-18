/** @jest-environment node */
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { StageSection } from './StageSection';

jest.mock('./GameTable', () => ({ GameTable: () => <div>Игра</div> }));

test('показывает многострочный текстовый комментарий стадии перед играми', () => {
  const html = renderToStaticMarkup(<StageSection stage={{
    name: 'Полуфинал',
    comment: 'Первая строка\nВторая строка <script>alert(1)</script>',
    games: [{ name: 'Игра' }],
  }} />);

  expect(html).toContain('Первая строка\nВторая строка &lt;script&gt;alert(1)&lt;/script&gt;');
  expect(html).toContain('whitespace-pre-line');
  expect(html).not.toContain('<script>');
  expect(html.indexOf('Первая строка')).toBeLessThan(html.indexOf('Игра'));
});

test('не создаёт пустой комментарий у старой стадии', () => {
  const html = renderToStaticMarkup(<StageSection stage={{ name: 'Финал', games: [] }} />);
  expect(html).not.toContain('whitespace-pre-line');
  expect(html).toContain('Информация об играх отсутствует');
});
