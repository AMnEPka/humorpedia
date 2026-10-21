import { reorderGames, reorderTeams, updateTeam } from './operations';

function freezeTree(value) {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
  Object.freeze(value);
  Object.values(value).forEach(freezeTree);
  return value;
}

test('game and team reorders preserve the ordered payload without mutating the source', () => {
  const input = freezeTree({ extension: 'season', stages: [
    { name: 'A', games: [
      { name: 'G1', order: 9, extension: true, teams: [{ team_slug: 'a', team_extension: 1 }, { team_slug: 'b', team_extension: 2 }] },
      { name: 'G2', order: 4 },
    ] },
  ] });

  const games = reorderGames(input, 0, 0, 1);
  expect(games.stages[0].games.map(game => [game.name, game.order])).toEqual([['G2', 1], ['G1', 2]]);
  expect(games.stages[0].games[1].extension).toBe(true);
  expect(input.stages[0].games.map(game => [game.name, game.order])).toEqual([['G1', 9], ['G2', 4]]);

  const teams = reorderTeams(input, 0, 0, 0, 1);
  expect(teams.stages[0].games[0].teams.map(team => team.team_slug)).toEqual(['b', 'a']);
  expect(teams.stages[0].games[0].teams[1].team_extension).toBe(1);
  expect(input.stages[0].games[0].teams.map(team => team.team_slug)).toEqual(['a', 'b']);
});

test('score patches retain team/person links and duplicate additional names remain until last occurrence is removed', () => {
  const input = freezeTree({ stages: [{ additional_teams: ['Club', 'Club'], games: [
    { teams: [{ team_slug: 'club', team_name: 'Club', team_id: 't1', person_id: 'p1', is_additional: true, custom: 'keep', scores: { Final: 1 } }] },
    { teams: [{ team_slug: 'club-2', team_name: 'Club', team_id: 't2', is_additional: true, custom: 'also keep' }] },
  ] }] });

  const patched = updateTeam(input, 0, 0, 0, { scores: { Final: 2.25 } });
  expect(patched.stages[0].games[0].teams[0]).toMatchObject({
    team_id: 't1', person_id: 'p1', custom: 'keep', scores: { Final: 2.25 },
  });
  expect(patched.stages[0].additional_teams).toEqual(['Club', 'Club']);
  expect(input.stages[0].games[0].teams[0].scores.Final).toBe(1);

  const renamed = updateTeam(input, 0, 0, 0, { team_name: 'New Club', team_slug: 'new-club' });
  expect(renamed.stages[0].additional_teams).toEqual(['Club', 'Club', 'New Club']);
  expect(renamed.stages[0].games[0].teams[0]).not.toHaveProperty('team_id');
  expect(renamed.stages[0].games[0].teams[0]).not.toHaveProperty('person_id');
});
