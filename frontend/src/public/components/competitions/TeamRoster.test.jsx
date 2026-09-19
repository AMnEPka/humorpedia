import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';

import TeamRoster from './TeamRoster';

test('former member links remain visibly blue', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <TeamRoster members={{
        current: [],
        former: [{
          _id: 'former-1',
          person_name: 'Анна Бородина',
          person: { slug: 'anna-borodina', name: 'Анна Бородина' },
          roles: [],
        }],
      }} />
    </MemoryRouter>
  );

  expect(html).toContain('href="/people/anna-borodina"');
  expect(html).toContain('class="text-blue-700 hover:underline"');
  expect(html).not.toContain('text-gray-700 hover:text-blue-600');
});
