/**
 * URL картинки из полей документа.
 * Поле может быть строкой ("/media/...") или объектом MediaFile ({url, thumbnail}), как его сохраняет админка.
 * Возвращает первый непустой URL из кандидатов (передавать в порядке приоритета) или null.
 */
export function mediaUrl(...candidates) {
  for (const value of candidates) {
    const url = typeof value === 'string' ? value : (value?.url || value?.thumbnail);
    if (url && url.trim()) {
      return url.startsWith('/') || url.startsWith('http') ? url : `/${url}`;
    }
  }
  return null;
}

/**
 * Фото человека: сначала `photo` (его редактирует админка), затем поля старого импорта.
 */
export function personPhotoUrl(person) {
  if (!person) return null;
  return mediaUrl(person.photo, person.cover_image, person.image, person.poster);
}

/**
 * Пары [ключ, значение] фактов в порядке facts_order (ключи вне порядка — в конце).
 */
export function orderedFacts(facts, order) {
  const entries = Object.entries(facts || {});
  if (!Array.isArray(order) || order.length === 0) return entries;
  const rank = new Map(order.map((key, i) => [key, i]));
  return entries
    .map((entry, i) => [entry, rank.has(entry[0]) ? rank.get(entry[0]) : order.length + i])
    .sort((a, b) => a[1] - b[1])
    .map(([entry]) => entry);
}
