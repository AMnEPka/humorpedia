import { seasonParticipantLabel } from './seasonParticipant';

test('показывает название и город сезона, сохраняя ссылку на прежнюю карточку', () => {
  expect(seasonParticipantLabel({ name: 'Титаны', slug: 'negoden', city: 'Санкт-Петербург' },
    { name: 'Негоден', city: 'Санкт-Петербург' })).toBe('Титаны (Санкт-Петербург)');
  expect(seasonParticipantLabel({ name: 'СПИКЛ', city: 'Мытищи' },
    { name: 'СПИКЛ', city: 'Саратов' })).toBe('СПИКЛ (Мытищи)');
});

test('поддерживает старые записи и явно пустой город', () => {
  expect(seasonParticipantLabel('old-slug', { name: 'Команда', city: 'Омск' })).toBe('Команда (Омск)');
  expect(seasonParticipantLabel({ name: 'Команда', city: '' }, { city: 'Омск' })).toBe('Команда');
  expect(seasonParticipantLabel({ name: 'Команда (Омск)', city: 'Омск' })).toBe('Команда (Омск)');
});
