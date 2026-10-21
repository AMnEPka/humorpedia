import React, { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import SeasonDataEditor from '../SeasonDataEditor';

jest.mock('../GameTeamSelector', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('../RichTextEditor', () => ({ __esModule: true, default: () => <textarea /> }));
jest.mock('../TeamSelector', () => ({ __esModule: true, default: () => <div /> }));

let host;
let root;
let saved;

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
  saved = null;
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

function mount(initial) {
  function Harness() {
    const [season, setSeason] = useState(initial);
    return <SeasonDataEditor seasonData={season} onChange={next => { saved = next; setSeason(next); }} />;
  }
  act(() => root.render(<Harness />));
}

test('stage and game expansion exposes named controls and editing a contest score preserves season JSON', async () => {
  const initial = {
    league_name: 'Лига',
    custom_season_field: { keep: true },
    stages: [{ name: 'R10 Этап', comment: 'Сохранить', extra_stage: 1, games: [{
      name: 'R10 Финал', extra_game: 2, contests: ['Приветствие'],
      teams: [{ team_slug: 'r8-participant', team_name: 'R8 participant', person_id: 'person-1',
        scores: { Приветствие: 1 }, unknown_team_field: ['keep'] }]
    }]}]
  };
  mount(initial);

  const stageToggle = host.querySelector('[aria-label="Развернуть стадию R10 Этап"]');
  expect(stageToggle).not.toBeNull();
  await act(async () => stageToggle.click());
  expect(host.querySelector('[aria-label="Свернуть стадию R10 Этап"]')).not.toBeNull();

  const gameToggle = host.querySelector('[aria-label="Развернуть игру R10 Финал"]');
  expect(gameToggle).not.toBeNull();
  await act(async () => gameToggle.click());
  expect(host.querySelector('[aria-label="Свернуть игру R10 Финал"]')).not.toBeNull();

  const score = host.querySelector('[aria-label="Баллы: R8 participant — Приветствие"]');
  expect(score).not.toBeNull();
  act(() => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(score, '2.5');
    score.dispatchEvent(new Event('input', { bubbles: true }));
  });
  act(() => score.dispatchEvent(new Event('focusout', { bubbles: true })));

  expect(saved.stages[0]).toMatchObject({ name: 'R10 Этап', comment: 'Сохранить', extra_stage: 1 });
  expect(saved.stages[0].games[0]).toMatchObject({ name: 'R10 Финал', extra_game: 2 });
  expect(saved.stages[0].games[0].teams[0]).toMatchObject({
    team_slug: 'r8-participant', team_name: 'R8 participant', person_id: 'person-1',
    unknown_team_field: ['keep'], scores: { Приветствие: 2.5 }, total: 2.5
  });
  expect(saved.custom_season_field).toEqual({ keep: true });
  expect(initial.stages[0].games[0].teams[0].scores).toEqual({ Приветствие: 1 });
});
