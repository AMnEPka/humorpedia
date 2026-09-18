/** @jest-environment node */
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import SeasonModulesArchive from './SeasonModulesArchive';

test('показывает старые модули сезона только как архивный список', () => {
  const html = renderToStaticMarkup(<SeasonModulesArchive modules={[
    { id: 'old-results', type: 'text_block', data: { title: 'Результаты', content: '<table><tr><td>5</td></tr></table>' } },
  ]} />);

  expect(html).toContain('Архивные модули сезона');
  expect(html).toContain('Результаты');
  expect(html).toContain('(text_block)');
  expect(html).toContain('публично не отображаются');
  expect(html).not.toContain('<table>');
  expect(html).not.toContain('<button');
  expect(html).not.toContain('<input');
});
