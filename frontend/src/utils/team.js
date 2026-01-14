/**
 * Очищает название команды от города в скобках в конце.
 * Удаляет только скобки с городом (без кавычек и других специальных символов).
 * Также удаляет HTML теги, если они присутствуют.
 * 
 * Это позволяет сохранить скобки как часть названия (например, "НГУ («В джазе только девушки»)").
 * 
 * @param {string} teamName - Название команды для очистки
 * @returns {string} Очищенное название команды
 */
export function cleanTeamName(teamName) {
  if (!teamName) return '';
  
  // Сначала удаляем HTML теги
  let cleaned = String(teamName).replace(/<[^>]*>/g, '').trim();
  
  // Убираем последние скобки в конце строки, но только если они не содержат кавычек
  // Это позволяет сохранить скобки как часть названия (например, "НГУ («В джазе только девушки»)")
  const lastParenMatch = cleaned.match(/\s+\(([^)]*)\)\s*$/);
  if (lastParenMatch) {
    const content = lastParenMatch[1];
    // Если в скобках нет кавычек и других специальных символов - это скорее всего город
    if (!content.includes('«') && !content.includes('»') && !content.includes('"') && !content.includes("'")) {
      cleaned = cleaned.replace(/\s+\([^)]*\)\s*$/, '').trim();
    }
  }
  
  return cleaned;
}
