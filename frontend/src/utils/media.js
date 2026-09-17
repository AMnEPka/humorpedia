export const PLACEHOLDER_IMAGES = [1, 2, 3, 4]
  .map((index) => `/media/imported/images/pattern/${index}.jpg`);

function entityKey(value) {
  if (value && typeof value === 'object') {
    return value.slug || value._id || value.id || value.title || value.name || value.full_name || '';
  }
  return String(value || 'humorpedia');
}

function normalizeLegacyPattern(url) {
  const match = String(url || '').match(/\/pattern-(\d)\.(?:jpe?g|png)$/i);
  return match ? `/media/imported/images/pattern/${match[1]}.jpg` : url;
}

export function isPlaceholderMedia(value) {
  const url = typeof value === 'string' ? value : (value?.url || value?.thumbnail || '');
  return /\/media\/imported\/images\/pattern(?:-|\/)/i.test(url);
}

function realMediaUrl(...candidates) {
  for (const candidate of candidates) {
    if (isPlaceholderMedia(candidate)) continue;
    const url = mediaUrl(candidate);
    if (url) return url;
  }
  return null;
}

/** Stable selection: the same page/card keeps the same one of four legacy patterns. */
export function placeholderImageUrl(value) {
  const key = entityKey(value);
  let hash = 0;
  for (let index = 0; index < key.length; index += 1) {
    hash = (Math.imul(hash, 31) + key.charCodeAt(index)) >>> 0;
  }
  return PLACEHOLDER_IMAGES[hash % PLACEHOLDER_IMAGES.length];
}

export function placeholderMedia(value) {
  const url = placeholderImageUrl(value);
  return { url, alt: '', caption: '', thumbnail: url };
}

/**
 * URL картинки из полей документа.
 * Поле может быть строкой ("/media/...") или объектом MediaFile ({url, thumbnail}), как его сохраняет админка.
 * Возвращает первый непустой URL из кандидатов (передавать в порядке приоритета) или null.
 */
export function mediaUrl(...candidates) {
  for (const value of candidates) {
    const rawUrl = typeof value === 'string' ? value : (value?.url || value?.thumbnail);
    const url = normalizeLegacyPattern(rawUrl);
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
  if (!person) return placeholderImageUrl('person');
  return realMediaUrl(person.photo, person.cover_image, person.image, person.poster)
    || placeholderImageUrl(person);
}

/** Team image: current logo, legacy image fields, then a stable Humorpedia pattern. */
export function teamLogoUrl(team) {
  if (!team) return placeholderImageUrl('team');
  return realMediaUrl(team.logo, team.poster, team.photo, team.image, team.cover_image)
    || placeholderImageUrl(team);
}

/** Generic page/card image with the same stable fallback rule. */
export function contentImageUrl(content, ...candidates) {
  return realMediaUrl(...candidates) || placeholderImageUrl(content);
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
