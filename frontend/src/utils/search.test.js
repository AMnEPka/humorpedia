import { normalizeSearchText } from './search';

test('normalizes Russian е and ё as the same search letter', () => {
  expect(normalizeSearchText('  ЗВЁЗДЫ   на НТВ ')).toBe('звезды на нтв');
  expect(normalizeSearchText('звезды')).toBe(normalizeSearchText('ЗВЁЗДЫ'));
});
