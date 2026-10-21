/** @jest-environment node */
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import TextModuleCard from './TextModuleCard';

test('retains the page anchor, title, rich HTML and page-specific styles', () => {
  const html = renderToStaticMarkup(<TextModuleCard id="section-stable" title="История"
    className="scroll-mt-20" bodyClassName="prose prose-blue"
    styles="table { width: 100%; }" content="<h3>Начало</h3><p><b>Текст</b></p>" />);
  expect(html).toContain('id="section-stable"');
  expect(html).toContain('scroll-mt-20');
  expect(html.match(/История/g)).toHaveLength(1);
  expect(html).toContain('<style>table { width: 100%; }</style>');
  expect(html).toContain('<h3>Начало</h3><p><b>Текст</b></p>');
});

test('untitled and empty text has no invented heading or content', () => {
  const html = renderToStaticMarkup(<TextModuleCard />);
  expect(html).not.toContain('<h3');
  expect(html).not.toContain('<style');
  expect(html).not.toContain('undefined');
});
