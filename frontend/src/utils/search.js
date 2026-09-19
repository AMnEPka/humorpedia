export const normalizeSearchText = (value) => String(value ?? '')
  .toLocaleLowerCase('ru-RU')
  .replace(/ё/g, 'е')
  .replace(/\s+/g, ' ')
  .trim();
