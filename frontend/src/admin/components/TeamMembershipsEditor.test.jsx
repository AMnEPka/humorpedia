jest.mock('../utils/api', () => ({
  contentApi: {},
  getErrorMessage: jest.fn(),
}));

jest.mock('../hooks/useAuth', () => ({
  useAuth: () => ({ isAdmin: false }),
}));

import { personSelectionPatch, toPayload } from './TeamMembershipsEditor';

test('removing a selected person preserves an explicit no-link override', () => {
  const changed = {
    person_name: 'Анна Бородина',
    ...personSelectionPatch([]),
  };

  expect(toPayload('team-25', changed)).toMatchObject({
    team_id: 'team-25',
    person_id: null,
    person_name: 'Анна Бородина',
    person_link_disabled: true,
  });
});

test('selecting a person enables the link again', () => {
  expect(personSelectionPatch(['person-1'])).toEqual({
    person_id: 'person-1',
    person_link_disabled: false,
  });
});
