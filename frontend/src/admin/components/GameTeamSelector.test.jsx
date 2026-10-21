import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import GameTeamSelector from './GameTeamSelector';
import { contentApi } from '../utils/api';

jest.mock('../utils/api', () => ({
  contentApi: { getTeam: jest.fn() },
}));

let container;
let root;
const noSeasonTeams = [];

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  contentApi.getTeam.mockImplementation(async (id) => ({
    data: { id, slug: id, name: `Team ${id}`, facts: {} },
  }));
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  jest.clearAllMocks();
});

async function renderValue(value) {
  await act(async () => {
    root.render(<GameTeamSelector value={value} seasonAllTeams={noSeasonTeams} onChange={() => {}} />);
  });
}

test('an equivalent new team object does not repeat the team lookup', async () => {
  await renderValue({ team_slug: 'alpha', team_name: 'Alpha' });
  await renderValue({ team_slug: 'alpha', team_name: 'Alpha' });

  expect(contentApi.getTeam).toHaveBeenCalledTimes(1);
  expect(container.textContent).toContain('Team alpha');
});

test('changing a string team id reloads and displays the selected team', async () => {
  await renderValue('alpha');
  await renderValue('beta');

  expect(contentApi.getTeam.mock.calls).toEqual([['alpha'], ['beta']]);
  expect(container.textContent).toContain('Team beta');
  expect(container.textContent).not.toContain('Team alpha');
});

test('omitting season teams renders without an update loop', async () => {
  const originalError = console.error;
  const errors = jest.spyOn(console, 'error').mockImplementation((message, ...args) => {
    if (String(message).includes('Maximum update depth exceeded')) {
      throw new Error('Selector entered an update loop');
    }
    originalError(message, ...args);
  });
  try {
    await act(async () => {
      root.render(<GameTeamSelector onChange={() => {}} />);
    });
    expect(container.textContent).toContain('Выберите команду...');
  } finally {
    errors.mockRestore();
  }
});
