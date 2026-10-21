import {
  cloneGameForNewStage,
  hasUnmatchedPersonReferences,
  mergeTeamIdentityUpdate,
  retainUnambiguousTeamLinks,
} from './SeasonDataEditor';

jest.mock('./TeamSelector', () => () => null);
jest.mock('./GameTeamSelector', () => () => null);
jest.mock('./RichTextEditor', () => () => null);

test('copying a canonical game drops only its game identity and keeps participant references', () => {
  const source = {
    _canonical_id: 'game-1',
    name: 'Финал',
    teams: [{ team_id: 'team-1', person_id: 'person-1', team_slug: 'team', extra: 'keep' }],
  };

  const copy = cloneGameForNewStage(source, 0);

  expect(copy).toEqual({
    name: 'Финал (копия)',
    teams: [{ team_id: 'team-1', person_id: 'person-1', team_slug: 'team', extra: 'keep' }],
  });
  expect(source._canonical_id).toBe('game-1');
});

test('changing a result team clears references to the replaced team, while score edits keep them', () => {
  const oldTeam = { team_id: 'team-old', person_id: 'person-old', team_slug: 'old', team_name: 'Старая', place: 2 };

  expect(mergeTeamIdentityUpdate(oldTeam, { place: 1 })).toEqual({ ...oldTeam, place: 1 });
  expect(mergeTeamIdentityUpdate(oldTeam, { team_slug: 'old', team_name: 'Новое название' })).toEqual({
    ...oldTeam, team_name: 'Новое название',
  });
  expect(mergeTeamIdentityUpdate(oldTeam, { team_slug: 'new', team_name: 'Новая' })).toEqual({
    team_slug: 'new', team_name: 'Новая', place: 2,
  });
});

test('pasting a table keeps links and extra fields only for an unambiguous same team', () => {
  const linked = { team_id: 'team-1', person_id: 'person-1', team_slug: 'same', team_name: 'Команда', custom: 'keep' };
  const matches = retainUnambiguousTeamLinks(
    [{ team_slug: 'same', team_name: 'Команда', total: 12 }],
    [linked]
  );
  const ambiguous = retainUnambiguousTeamLinks(
    [{ team_slug: 'same', team_name: 'Команда' }],
    [linked, { ...linked, team_id: 'team-2' }]
  );

  expect(matches[0]).toEqual({ ...linked, total: 12 });
  expect(ambiguous[0]).toEqual({ team_slug: 'same', team_name: 'Команда' });
  expect(hasUnmatchedPersonReferences([{ team_slug: 'same', team_name: 'Команда' }], [linked])).toBe(false);
  expect(hasUnmatchedPersonReferences([{ team_slug: 'different', team_name: 'Другая' }], [linked])).toBe(true);
  expect(hasUnmatchedPersonReferences([{ team_slug: 'same', team_name: 'Команда' }], [linked, { ...linked, team_id: 'team-2' }])).toBe(true);
});
