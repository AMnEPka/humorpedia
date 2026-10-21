import { copyGameToStage } from './operations';

test('a copy placed before the original clears both canonical and legacy matching IDs', () => {
  const source = { id: 'legacy-game', _canonical_id: 'canonical-game', name: 'Финал', order: 1,
    extension: { preserve: true }, teams: [{ person_id: 'person', team_id: 'team', custom: 9 }] };
  const input = { custom: 8, stages: [
    { name: 'Раньше', games: [] },
    { name: 'Исходная', games: [source] },
  ] };
  const copy = copyGameToStage(input, 1, 0, 0).stages[0].games[0];
  expect(copy).not.toHaveProperty('_canonical_id');
  expect(copy).not.toHaveProperty('id');
  const { _canonical_id, id, name, order, ...content } = source;
  expect(copy).toEqual({ ...content, name: 'Финал (копия)', order: 1 });
  expect(input.stages[1].games[0]).toEqual(source);
});
