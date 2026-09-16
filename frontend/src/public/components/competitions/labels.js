// Общие подписи для турниров, сезонов и составов (перекрёстные ссылки).

const STAGE_RESULT = {
  final: 'Финалист',
  '1/2': 'Полуфинал',
  '1/4': 'Четвертьфинал',
  '1/8': '1/8 финала',
};

// Итог участника в сезоне (строка participations kind=season)
export function seasonResult(row) {
  if (!row) return { label: '', tone: 'default' };
  if (row.is_champion) return { label: 'Чемпион', tone: 'gold' };
  if (row.best_stage_code && STAGE_RESULT[row.best_stage_code]) {
    return { label: STAGE_RESULT[row.best_stage_code], tone: row.best_stage_code === 'final' ? 'silver' : 'default' };
  }
  if (row.best_stage_name) return { label: row.best_stage_name, tone: 'default' };
  return { label: 'Участник сезона', tone: 'muted' };
}

export const RESULT_TONE_CLASSES = {
  gold: 'bg-amber-100 text-amber-800 border-amber-200',
  silver: 'bg-slate-100 text-slate-700 border-slate-200',
  default: 'bg-blue-50 text-blue-700 border-blue-100',
  muted: 'bg-gray-50 text-gray-500 border-gray-200',
};

const ROLE_TITLES = {
  jury: { one: 'Член жюри', many: 'Жюри' },
  host: { one: 'Ведущий', many: 'Ведущий' },
  editor: { one: 'Редактор', many: 'Редактор' },
};

export function roleTitle(role, many = false) {
  const titles = ROLE_TITLES[role];
  if (!titles) return role;
  return many ? titles.many : titles.one;
}

export function yearsLabel({ from_year: from, to_year: to } = {}) {
  if (from && to) return from === to ? `${from}` : `${from}–${to}`;
  if (from) return `с ${from}`;
  if (to) return `до ${to}`;
  return '';
}

export function pagePath(path) {
  if (!path) return null;
  return path.startsWith('/') ? path : `/${path}`;
}

// Страница команды. Сейчас публичный маршрут есть только у команд КВН;
// для команд других шоу маршрут появится вместе с их разделами.
export function teamHref(team) {
  if (!team?.slug) return null;
  return `/kvn/teams/${team.slug}`;
}

export function personHref(person) {
  return person?.slug ? `/people/${person.slug}` : null;
}

export function tournamentTitle(tournament) {
  return tournament?.title || tournament?.short_title || tournament?.slug || '';
}

export function formatDate(value) {
  if (!value) return '';
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  return `${match[3]}.${match[2]}.${match[1]}`;
}

export function formatScore(value) {
  if (value === null || value === undefined || value === '') return '';
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return Number.isInteger(number) ? String(number) : number.toFixed(2).replace(/0+$/, '').replace('.', ',');
}
