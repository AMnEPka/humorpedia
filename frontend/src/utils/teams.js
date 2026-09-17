// Адреса и подписи команд: команда КВН — /kvn/teams/{slug}, команда шоу — /shows/{путь шоу}/teams/{slug}
// (поле full_path; бэкенд также отдаёт готовый url и show: {title, full_path}). См. backend/services/show_teams.py.

export function teamUrl(team) {
  if (!team) return null;
  if (team.url) return team.url;
  // у части старых команд КВН full_path = slug — адрес шоу только при show_id
  if (team.show_id && team.full_path) return `/shows/${team.full_path.replace(/^\/+/, '')}`;
  return team.slug ? `/kvn/teams/${team.slug}` : null;
}

// «liga-gorodov/teams/eto-oni» — адрес команды шоу (а не страницы шоу)
export function isShowTeamPath(path) {
  const parts = (path || '').split('/').filter(Boolean);
  return parts.length >= 3 && parts[parts.length - 2] === 'teams';
}

// «Команда шоу «Лига Городов»» / «Команда КВН»
export function teamSubtitle(team) {
  if (!team) return '';
  if (team.show?.title) return `Команда шоу «${team.show.title}»`;
  return team.show_id ? 'Команда шоу' : 'Команда КВН';
}

// Заголовок вкладки: у команды шоу с подписью — в поиске одноимённые команды различимы
export function teamPageTitle(team) {
  if (!team) return '';
  const name = team.title || team.name || '';
  return team.show?.title ? `${name} — команда шоу «${team.show.title}»` : name;
}
