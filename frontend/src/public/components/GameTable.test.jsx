/** @jest-environment node */
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { GameTable } from './GameTable';

jest.mock('react-router-dom', () => ({ Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a> }));
jest.mock('../utils/api', () => ({}));
jest.mock('../utils/teamStorage', () => ({ teamStorage: { getTeams: jest.fn(() => ({})) } }));

test('публичная таблица сортируется по числовому месту, сохраняет ничьи и не изменяет данные', () => {
  const teams = Object.freeze([
    Object.freeze({ team_name: 'Десятая', place: '10', total: 3 }),
    Object.freeze({ team_name: 'Без места', place: null, total: 10 }),
    Object.freeze({ team_name: 'Вторая А', place: '2', total: 5 }),
    Object.freeze({ team_name: 'Первая', team_slug: 'first', place: 1, total: 6, passed: true }),
    Object.freeze({ team_name: 'Вторая Б', place: 2, total: 5, is_additional: true, passed: true }),
    Object.freeze({ team_name: 'Пустое место', place: '', total: null }),
  ]);
  const html = renderToStaticMarkup(<GameTable game={{ name: 'Игра', teams }} stageName="1/4 финала" />);
  const expected = ['Первая', 'Вторая А', 'Вторая Б', 'Десятая', 'Без места', 'Пустое место'];
  expected.slice(1).forEach((name, index) => {
    expect(html.indexOf(expected[index])).toBeLessThan(html.indexOf(name));
  });
  expect(html).toContain('/kvn/teams/first');
  expect(html).toContain('Добор');
  expect(html.match(/>—<\/td>/g)).toHaveLength(2);
  expect(teams[0].team_name).toBe('Десятая');
});
