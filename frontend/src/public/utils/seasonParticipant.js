// Название и город участника принадлежат конкретному сезону. Карточка нужна для старых записей без этих данных.
export function seasonParticipantLabel(participant, current = {}) {
  const stored = typeof participant === 'object' && participant !== null ? participant : {};
  const name = stored.name || current.name || (typeof participant === 'string' ? participant : stored.slug) || '';
  const city = Object.prototype.hasOwnProperty.call(stored, 'city') ? stored.city : current.city;
  return city && !name.includes(`(${city})`) ? `${name} (${city})` : name;
}
