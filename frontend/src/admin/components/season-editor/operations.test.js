import {
  copyContests,
  copyGameToStage,
  formatWinners,
  moveGameToStage,
  removeContest,
  renameContest,
  reorderStages,
  updateTeam,
} from './operations';

function deepFreeze(value) {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
  Object.freeze(value);
  Object.values(value).forEach(deepFreeze);
  return value;
}

test('stage reorder and game move/copy are immutable and preserve extension data', () => {
  const input = deepFreeze({
    season_extension: { keep: true },
    stages: [
      { name: 'A', order: 8, stage_extension: 'a', games: [{ name: 'Final', order: 7, _canonical_id: 'game-1', game_extension: { keep: true }, teams: [{ team_id: 'team-1', person_id: 'person-1', team_slug: 'slug', team_extension: 42 }] }] },
      { name: 'B', order: 9, stage_extension: 'b', games: [{ name: 'Semifinal', order: 3 }] },
    ],
  });

  const reordered = reorderStages(input, 0, 1);
  expect(reordered.stages.map(stage => [stage.name, stage.order])).toEqual([['B', 1], ['A', 2]]);
  expect(reordered.season_extension).toEqual({ keep: true });
  expect(reordered.stages[0].stage_extension).toBe('b');

  const moved = moveGameToStage(input, 0, 0, 1);
  expect(moved.stages[0].games).toEqual([]);
  expect(moved.stages[1].games[1]).toMatchObject({ name: 'Final', order: 4, _canonical_id: 'game-1', game_extension: { keep: true } });
  expect(moved.stages[1].games[1].teams[0]).toMatchObject({ team_id: 'team-1', person_id: 'person-1', team_extension: 42 });

  const copied = copyGameToStage(input, 0, 0, 1);
  expect(copied.stages[1].games[1]).toMatchObject({ name: 'Final (копия)', order: 4, game_extension: { keep: true } });
  expect(copied.stages[1].games[1]).not.toHaveProperty('_canonical_id');
  expect(copied.stages[1].games[1].teams[0]).toMatchObject({ team_id: 'team-1', person_id: 'person-1' });
  expect(input.stages[0].games[0].order).toBe(7);
});

test('team result patch preserves unknown fields, clears stale links only on identity change, and keeps duplicate additional teams', () => {
  const input = deepFreeze({ stages: [{ additional_teams: ['Old', 'Shared'], games: [
    { teams: [
      { team_slug: 'old', team_name: 'Old (City)', team_id: 'id-old', person_id: 'p-old', is_additional: true, custom: { keep: true }, scores: { Final: 3 } },
      { team_slug: 'shared', team_name: 'Shared', is_additional: true },
    ] },
    { teams: [{ team_slug: 'shared-2', team_name: 'Shared', is_additional: true }] },
  ] }] });

  const scoreEdit = updateTeam(input, 0, 0, 0, { place: 1 });
  expect(scoreEdit.stages[0].games[0].teams[0]).toMatchObject({ team_id: 'id-old', person_id: 'p-old', custom: { keep: true }, place: 1 });

  const identityEdit = updateTeam(input, 0, 0, 0, { team_slug: 'new', team_name: 'New (Town)' });
  expect(identityEdit.stages[0].games[0].teams[0]).toMatchObject({ team_slug: 'new', team_name: 'New (Town)', custom: { keep: true }, is_additional: true });
  expect(identityEdit.stages[0].games[0].teams[0]).not.toHaveProperty('team_id');
  expect(identityEdit.stages[0].games[0].teams[0]).not.toHaveProperty('person_id');
  expect(identityEdit.stages[0].additional_teams).toEqual(['Shared', 'New']);
  expect(input.stages[0].additional_teams).toEqual(['Old', 'Shared']);
});

test('contest rename/copy preserve unrelated score keys and team extensions; removal recalculates totals', () => {
  const input = deepFreeze({ stages: [{ games: [
    { contests: ['Old', 'Other'], teams: [{ scores: { Old: 2.5, Other: 1, legacy_score: 99 }, total: 3.5, team_extension: 'keep' }] },
    { contests: ['Other'], teams: [{ scores: { Other: 4, legacy_score: 88 }, total: 4, team_extension: 'destination' }] },
  ] }] });
  const renamed = renameContest(input, 0, 0, 0, ' New ');
  expect(renamed.stages[0].games[0].contests).toEqual(['New', 'Other']);
  expect(renamed.stages[0].games[0].teams[0]).toMatchObject({ scores: { New: 2.5, Other: 1, legacy_score: 99 }, total: 3.5, team_extension: 'keep' });

  const copied = copyContests(input, 0, 1, 0, 0);
  expect(copied.stages[0].games[1].contests).toEqual(['Old', 'Other']);
  expect(copied.stages[0].games[1].teams[0]).toMatchObject({ scores: { Old: 0, Other: 4 }, total: 4, team_extension: 'destination' });

  const removed = removeContest(input, 0, 0, 'Old');
  expect(removed.stages[0].games[0].teams[0]).toMatchObject({ scores: { Other: 1, legacy_score: 99 }, total: 1, team_extension: 'keep' });
  expect(input.stages[0].games[0].contests).toEqual(['Old', 'Other']);
});

test('winner normalization keeps custom fields while retaining string winner compatibility', () => {
  expect(formatWinners([
    { slug: 'team', name: 'Команда', city: 'Город', source: 'legacy', custom: { keep: true } },
    { name: 'Свободное название', custom: 'retain' },
    'legacy-slug',
  ])).toEqual([
    { slug: 'team', name: 'Команда', city: 'Город', source: 'legacy', custom: { keep: true } },
    { name: 'Свободное название', custom: 'retain' },
    'legacy-slug',
  ]);
});
