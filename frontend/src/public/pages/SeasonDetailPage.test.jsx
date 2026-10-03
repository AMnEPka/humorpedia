/** @jest-environment node */
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import SeasonDetailPage from './SeasonDetailPage';

jest.mock('react-router-dom', () => ({
  Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
  useLocation: () => ({ pathname: '/kvn/vl-kvn/vl-2026' }),
  useNavigate: () => jest.fn(),
}));
jest.mock('../utils/api', () => ({}));
jest.mock('../utils/teamStorage', () => ({ teamStorage: { getTeams: jest.fn(() => ({})) } }));

test('страница сезона показывает факты и места, скрывая редакционные заметки', () => {
  const privateNote = 'Состав финала не подтверждён; passed оставлен false';
  const season = {
    title: 'Высшая лига 2026',
    season_data: {
      year: 2026,
      editorial_notes: privateNote,
      stages: [{
        name: 'Полуфинал',
        additional_teams: ['Леон Киллер'],
        additional_notes: 'Леон Киллер добран в финал.',
        games: [{ name: 'Игра', teams: [
          { team_name: 'Вторая команда', place: 2, total: 20 },
          { team_name: 'Первая команда', place: 1, total: 21 },
        ] }],
      }],
    },
  };
  const html = renderToStaticMarkup(<SeasonDetailPage seasonData={season} />);
  expect(html).toContain('Леон Киллер добран в финал.');
  expect(html).not.toContain(privateNote);
  expect(html).not.toContain('passed');
  expect(html.indexOf('Первая команда')).toBeLessThan(html.indexOf('Вторая команда'));
});
