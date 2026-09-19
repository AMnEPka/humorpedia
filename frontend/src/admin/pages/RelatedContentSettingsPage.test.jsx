import { DEFAULT_SETTINGS, normalizeSettings } from './RelatedContentSettingsPage';

jest.mock('../utils/api', () => ({
  getErrorMessage: (_error, fallback) => fallback,
  recommendationSettingsApi: { get: jest.fn(), update: jest.fn() },
}));

test('по умолчанию включает согласованные типы, но не новости', () => {
  expect(DEFAULT_SETTINGS.max_items).toBe(3);
  expect(DEFAULT_SETTINGS.result_types).toEqual([
    'article', 'person', 'kvn_team', 'show_team', 'show', 'city', 'kvn', 'quiz',
  ]);
  expect(DEFAULT_SETTINGS.apply_to).toEqual({
    articles: true,
    news: true,
    people: true,
    kvn_teams: true,
    show_teams: true,
    shows: true,
    cities: true,
    kvn: true,
  });
});

test('дополняет отсутствующие поля сохранённых настроек значениями по умолчанию', () => {
  expect(normalizeSettings({ max_items: 6, result_types: ['person'], apply_to: { cities: false } })).toEqual({
    ...DEFAULT_SETTINGS,
    max_items: 6,
    result_types: ['person'],
    apply_to: { ...DEFAULT_SETTINGS.apply_to, cities: false },
  });
});
