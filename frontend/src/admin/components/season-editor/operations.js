import { roundTo } from '@/utils/number';

function replaceStage(data, stageIndex, updateStage) {
  if (!Array.isArray(data?.stages) || !data.stages[stageIndex]) return data;
  const stages = [...data.stages];
  stages[stageIndex] = updateStage(stages[stageIndex]);
  return { ...data, stages };
}

function replaceGame(data, stageIndex, gameIndex, updateGame) {
  return replaceStage(data, stageIndex, stage => {
    if (!Array.isArray(stage.games) || !stage.games[gameIndex]) return stage;
    const games = [...stage.games];
    games[gameIndex] = updateGame(games[gameIndex]);
    return { ...stage, games };
  });
}

function replaceTeam(data, stageIndex, gameIndex, teamIndex, updateTeam) {
  return replaceGame(data, stageIndex, gameIndex, game => {
    if (!Array.isArray(game.teams) || teamIndex < 0 || teamIndex >= game.teams.length) return game;
    const teams = [...game.teams];
    teams[teamIndex] = updateTeam(teams[teamIndex] || {});
    return { ...game, teams };
  });
}

function arrayMove(items, fromIndex, toIndex) {
  const result = [...items];
  const [item] = result.splice(fromIndex, 1);
  result.splice(toIndex, 0, item);
  return result;
}

function renumber(items) {
  return items.map((item, index) => ({ ...item, order: index + 1 }));
}

function totalFor(contests, scores) {
  return roundTo(contests.reduce((sum, contest) => {
    const score = scores[contest] ?? 0;
    return sum + (typeof score === 'number' ? score : 0);
  }, 0), 2);
}

export function removeCityFromName(name) {
  if (!name) return name;
  return name.replace(/\s*\([^)]+\)\s*$/, '').trim();
}

export function cloneGameForNewStage(game, gameIndex) {
  const copy = JSON.parse(JSON.stringify(game));
  delete copy._canonical_id;
  delete copy.id; // A copied legacy ID could bind to the original canonical game.
  copy.name = `${copy.name || `Игра ${gameIndex + 1}`} (копия)`;
  return copy;
}

export function mergeTeamIdentityUpdate(team, updates) {
  const updated = { ...team, ...updates };
  const oldSlug = String(team.team_slug || '').trim();
  const newSlug = String(updated.team_slug || '').trim();
  const identityChanged = (
    Object.prototype.hasOwnProperty.call(updates, 'team_slug') ||
    Object.prototype.hasOwnProperty.call(updates, 'team_name')
  ) && (
    oldSlug || newSlug
      ? oldSlug !== newSlug
      : String(team.team_name || '').trim() !== String(updated.team_name || '').trim()
  );
  if (identityChanged) {
    delete updated.team_id;
    delete updated.person_id;
  }
  return updated;
}

export function retainUnambiguousTeamLinks(teams, previousTeams = []) {
  const used = new Set();
  return teams.map(team => {
    const slug = String(team.team_slug || '').trim().toLowerCase();
    const name = removeCityFromName(String(team.team_name || '').trim()).toLowerCase();
    const candidates = previousTeams
      .map((previous, index) => ({ previous, index }))
      .filter(({ previous, index }) => {
        if (used.has(index)) return false;
        const previousSlug = String(previous.team_slug || '').trim().toLowerCase();
        if (slug && previousSlug) return slug === previousSlug;
        return !slug && !previousSlug && name &&
          removeCityFromName(String(previous.team_name || '').trim()).toLowerCase() === name;
      });
    if (candidates.length !== 1) return team;
    const { previous, index } = candidates[0];
    used.add(index);
    return { ...previous, ...team };
  });
}

export function hasUnmatchedPersonReferences(teams, previousTeams = []) {
  const linkedTeams = retainUnambiguousTeamLinks(teams, previousTeams);
  return previousTeams.some(previous => {
    if (!previous.person_id) return false;
    const previousSlug = String(previous.team_slug || '').trim().toLowerCase();
    const previousName = removeCityFromName(String(previous.team_name || '').trim()).toLowerCase();
    return !linkedTeams.some(team => {
      if (team.person_id !== previous.person_id) return false;
      const teamSlug = String(team.team_slug || '').trim().toLowerCase();
      const teamName = removeCityFromName(String(team.team_name || '').trim()).toLowerCase();
      return previousSlug || teamSlug
        ? previousSlug === teamSlug
        : previousName === teamName;
    });
  });
}

export function formatWinners(winners) {
  return winners.map(winner => {
    if (!winner || typeof winner !== 'object') return winner;
    if (winner.slug) {
      return { ...winner, name: winner.name || winner.slug, city: winner.city || '' };
    }
    return { ...winner };
  });
}

export function reorderStages(data, fromIndex, toIndex) {
  if (!Array.isArray(data?.stages) || fromIndex < 0 || toIndex < 0 || fromIndex >= data.stages.length || toIndex >= data.stages.length || fromIndex === toIndex) return data;
  return { ...data, stages: renumber(arrayMove(data.stages, fromIndex, toIndex)) };
}

export function reorderGames(data, stageIndex, fromIndex, toIndex) {
  const games = data?.stages?.[stageIndex]?.games;
  if (!Array.isArray(games) || fromIndex < 0 || toIndex < 0 || fromIndex >= games.length || toIndex >= games.length || fromIndex === toIndex) return data;
  return replaceStage(data, stageIndex, stage => ({ ...stage, games: renumber(arrayMove(stage.games, fromIndex, toIndex)) }));
}

export function reorderTeams(data, stageIndex, gameIndex, fromIndex, toIndex) {
  const teams = data?.stages?.[stageIndex]?.games?.[gameIndex]?.teams;
  if (!Array.isArray(teams) || fromIndex < 0 || toIndex < 0 || fromIndex >= teams.length || toIndex >= teams.length || fromIndex === toIndex) return data;
  return replaceGame(data, stageIndex, gameIndex, game => ({ ...game, teams: arrayMove(game.teams, fromIndex, toIndex) }));
}

export function updateStage(data, stageIndex, updates) {
  return replaceStage(data, stageIndex, stage => ({ ...stage, ...updates }));
}

export function addStage(data) {
  const stages = Array.isArray(data?.stages) ? data.stages : [];
  const maxOrder = stages.length ? Math.max(...stages.map(stage => stage.order || 0)) : 0;
  return { ...data, stages: [...stages, {
    name: `Стадия ${stages.length + 1}`, order: maxOrder + 1, games: [], comment: '', notes: '',
    additional_teams: [], additional_notes: '',
  }] };
}

export function removeStage(data, stageIndex) {
  if (!Array.isArray(data?.stages)) return data;
  return { ...data, stages: data.stages.filter((_, index) => index !== stageIndex) };
}

export function updateGame(data, stageIndex, gameIndex, updates) {
  return replaceGame(data, stageIndex, gameIndex, game => ({ ...game, ...updates }));
}

export function addGame(data, stageIndex) {
  return replaceStage(data, stageIndex, stage => {
    const games = Array.isArray(stage.games) ? stage.games : [];
    const maxOrder = games.length ? Math.max(...games.map(game => game.order || 0)) : 0;
    return { ...stage, games: [...games, {
      name: `Игра ${games.length + 1}`, order: maxOrder + 1, date: '', host: '', jury: [],
      contests: [], teams: [], notes: '',
    }] };
  });
}

export function removeGame(data, stageIndex, gameIndex) {
  const stage = data?.stages?.[stageIndex];
  if (!Array.isArray(stage?.games)) return data;
  const removedGame = stage.games[gameIndex];
  if (!removedGame) return data;
  const removedNames = (removedGame.teams || []).filter(team => team?.is_additional)
    .map(team => String(team?.team_name || '').trim()).filter(Boolean);
  const games = stage.games.filter((_, index) => index !== gameIndex);
  let additionalTeams = stage.additional_teams;
  if (removedNames.length) {
    const stillHasName = name => {
      const target = String(name || '').trim();
      if (!target) return false;
      const targetWithoutCity = removeCityFromName(target);
      return games.some(game => (game.teams || []).some(team => {
        const teamName = String(team?.team_name || '').trim();
        return team?.is_additional && (teamName === target || removeCityFromName(teamName) === targetWithoutCity);
      }));
    };
    additionalTeams = (Array.isArray(stage.additional_teams) ? stage.additional_teams : []).filter(value => {
      const name = String(value || '').trim();
      if (!name) return false;
      const nameWithoutCity = removeCityFromName(name);
      const shouldRemove = removedNames.some(removed => name === removed || nameWithoutCity === removeCityFromName(removed));
      return !shouldRemove || stillHasName(name);
    });
  }
  return replaceStage(data, stageIndex, current => ({ ...current, games, ...(removedNames.length ? { additional_teams: additionalTeams } : {}) }));
}

export function moveGameToStage(data, fromStageIndex, gameIndex, toStageIndex) {
  const source = data?.stages?.[fromStageIndex];
  const target = data?.stages?.[toStageIndex];
  const game = source?.games?.[gameIndex];
  if (!source || !target || !game) return data;
  const stages = [...data.stages];
  const sourceGames = [...(source.games || [])];
  sourceGames.splice(gameIndex, 1);
  stages[fromStageIndex] = { ...source, games: sourceGames };
  const targetGames = fromStageIndex === toStageIndex ? sourceGames : [...(target.games || [])];
  const maxOrder = targetGames.length ? Math.max(...targetGames.map(item => item.order || 0)) : 0;
  targetGames.push({ ...game, order: maxOrder + 1 });
  stages[toStageIndex] = { ...target, games: targetGames };
  return { ...data, stages };
}

export function copyGameToStage(data, fromStageIndex, gameIndex, toStageIndex) {
  const game = data?.stages?.[fromStageIndex]?.games?.[gameIndex];
  const target = data?.stages?.[toStageIndex];
  if (!game || !target) return data;
  const games = Array.isArray(target.games) ? target.games : [];
  const maxOrder = games.length ? Math.max(...games.map(item => item.order || 0)) : 0;
  const copy = cloneGameForNewStage(game, gameIndex);
  copy.order = maxOrder + 1;
  return replaceStage(data, toStageIndex, stage => ({ ...stage, games: [...(stage.games || []), copy] }));
}

export function updateTeam(data, stageIndex, gameIndex, teamIndex, updates) {
  const previousStage = data?.stages?.[stageIndex];
  const previousTeam = previousStage?.games?.[gameIndex]?.teams?.[teamIndex] || {};
  const prevName = String(previousTeam.team_name || '').trim();
  const prevIsAdditional = !!previousTeam.is_additional;
  const updatedTeam = mergeTeamIdentityUpdate(previousTeam, updates);
  let result = replaceTeam(data, stageIndex, gameIndex, teamIndex, () => updatedTeam);
  const shouldSyncAdditional = Object.prototype.hasOwnProperty.call(updates, 'is_additional') || Object.prototype.hasOwnProperty.call(updates, 'team_name');
  if (!shouldSyncAdditional) return result;

  const stage = result.stages[stageIndex];
  const currentAdditional = Array.isArray(stage.additional_teams) ? [...stage.additional_teams] : [];
  const nextName = String(updatedTeam.team_name || '').trim();
  const nextIsAdditional = !!updatedTeam.is_additional;
  const stageHasAdditionalName = (name, excludeGameIndex, excludeTeamIndex) => {
    const target = String(name || '').trim();
    if (!target) return false;
    return (stage.games || []).some((game, gIndex) => (game.teams || []).some((team, tIndex) => {
      if (gIndex === excludeGameIndex && tIndex === excludeTeamIndex) return false;
      return team?.is_additional && String(team?.team_name || '').trim() === target;
    }));
  };
  let additional = currentAdditional.map(value => String(value || '').trim()).filter(Boolean);
  const previousWithoutCity = removeCityFromName(prevName);
  const nextWithoutCity = removeCityFromName(nextName);

  if (prevIsAdditional && previousWithoutCity && previousWithoutCity !== nextWithoutCity && !stageHasAdditionalName(prevName, gameIndex, teamIndex)) {
    additional = additional.filter(value => removeCityFromName(value) !== previousWithoutCity);
  }
  if (prevIsAdditional && !nextIsAdditional && previousWithoutCity && !stageHasAdditionalName(prevName, gameIndex, teamIndex)) {
    additional = additional.filter(value => removeCityFromName(value) !== previousWithoutCity);
  }
  if (nextIsAdditional && nextWithoutCity && !additional.some(value => removeCityFromName(value) === nextWithoutCity)) {
    additional.push(nextWithoutCity);
  }
  if (prevIsAdditional && nextIsAdditional && nextWithoutCity && !additional.some(value => removeCityFromName(value) === nextWithoutCity)) {
    additional.push(nextWithoutCity);
  }
  return replaceStage(result, stageIndex, current => ({ ...current, additional_teams: additional }));
}

export function addTeamToGame(data, stageIndex, gameIndex) {
  return replaceGame(data, stageIndex, gameIndex, game => ({ ...game, teams: [...(game.teams || []), {
    team_slug: '', team_name: '', place: 0, total: 0, scores: {}, passed: false, is_winner: false,
    is_additional: false, city: '',
  }] }));
}

export function removeTeamFromGame(data, stageIndex, gameIndex, teamIndex) {
  const stage = data?.stages?.[stageIndex];
  const game = stage?.games?.[gameIndex];
  if (!Array.isArray(game?.teams)) return data;
  const removed = game.teams[teamIndex] || {};
  const removedName = String(removed.team_name || '').trim();
  const teams = game.teams.filter((_, index) => index !== teamIndex);
  let result = replaceGame(data, stageIndex, gameIndex, current => ({ ...current, teams }));
  if (!removed.is_additional || !removedName) return result;
  const removedWithoutCity = removeCityFromName(removedName);
  const stillUsed = result.stages[stageIndex].games.some(currentGame => (currentGame.teams || []).some(team => {
    const name = String(team?.team_name || '').trim();
    return team?.is_additional && (name === removedName || removeCityFromName(name) === removedWithoutCity);
  }));
  if (stillUsed) return result;
  const additional = (Array.isArray(stage.additional_teams) ? stage.additional_teams : [])
    .map(value => String(value || '').trim()).filter(Boolean)
    .filter(value => value !== removedName && removeCityFromName(value) !== removedWithoutCity);
  return replaceStage(result, stageIndex, current => ({ ...current, additional_teams: additional }));
}

export function addContest(data, stageIndex, gameIndex, contestName) {
  const name = String(contestName || '').trim();
  if (!name) return data;
  return replaceGame(data, stageIndex, gameIndex, game => {
    const contests = [...(game.contests || []), name];
    const teams = Array.isArray(game.teams) ? game.teams.map(team => {
      const scores = { ...(team.scores || {}), [name]: 0 };
      return { ...team, scores, total: totalFor(contests, scores) };
    }) : game.teams;
    return { ...game, contests, ...(Array.isArray(game.teams) ? { teams } : {}) };
  });
}

export function moveContest(data, stageIndex, gameIndex, fromIndex, toIndex) {
  const contests = data?.stages?.[stageIndex]?.games?.[gameIndex]?.contests;
  if (!Array.isArray(contests) || fromIndex < 0 || fromIndex >= contests.length || toIndex < 0 || toIndex >= contests.length) return data;
  return replaceGame(data, stageIndex, gameIndex, game => ({ ...game, contests: arrayMove(game.contests || [], fromIndex, toIndex) }));
}

export function renameContest(data, stageIndex, gameIndex, contestIndex, newNameRaw) {
  const contests = data?.stages?.[stageIndex]?.games?.[gameIndex]?.contests;
  const newName = String(newNameRaw || '').trim();
  if (!Array.isArray(contests) || contestIndex < 0 || contestIndex >= contests.length || !newName) return data;
  const oldName = contests[contestIndex];
  if (oldName === newName || contests.includes(newName)) return data;
  return replaceGame(data, stageIndex, gameIndex, game => {
    const nextContests = [...game.contests];
    nextContests[contestIndex] = newName;
    const teams = Array.isArray(game.teams) ? game.teams.map(team => {
      const scores = { ...(team.scores || {}) };
      if (Object.prototype.hasOwnProperty.call(scores, oldName)) {
        scores[newName] = scores[oldName];
        delete scores[oldName];
      } else if (!Object.prototype.hasOwnProperty.call(scores, newName)) {
        scores[newName] = 0;
      }
      return { ...team, scores, total: totalFor(nextContests, scores) };
    }) : game.teams;
    return { ...game, contests: nextContests, ...(Array.isArray(game.teams) ? { teams } : {}) };
  });
}

export function copyContests(data, dstStageIndex, dstGameIndex, srcStageIndex, srcGameIndex) {
  const source = data?.stages?.[srcStageIndex]?.games?.[srcGameIndex];
  const destination = data?.stages?.[dstStageIndex]?.games?.[dstGameIndex];
  if (!source || !destination) return data;
  const contests = Array.isArray(source.contests) ? [...source.contests] : [];
  return replaceGame(data, dstStageIndex, dstGameIndex, game => {
    const teams = Array.isArray(game.teams) ? game.teams.map(team => {
      const oldScores = team.scores || {};
      const scores = {};
      contests.forEach(contest => {
        const value = oldScores[contest];
        scores[contest] = typeof value === 'number' ? roundTo(value, 2) : 0;
      });
      return { ...team, scores, total: totalFor(contests, scores) };
    }) : game.teams;
    return { ...game, contests, ...(Array.isArray(game.teams) ? { teams } : {}) };
  });
}

export function removeContest(data, stageIndex, gameIndex, contestName) {
  const game = data?.stages?.[stageIndex]?.games?.[gameIndex];
  if (!Array.isArray(game?.contests)) return data;
  const contests = game.contests.filter(contest => contest !== contestName);
  return replaceGame(data, stageIndex, gameIndex, current => {
    const teams = Array.isArray(current.teams) ? current.teams.map(team => {
      const scores = { ...(team.scores || {}) };
      delete scores[contestName];
      return { ...team, scores, total: totalFor(contests, scores) };
    }) : current.teams;
    return { ...current, contests, ...(Array.isArray(current.teams) ? { teams } : {}) };
  });
}
