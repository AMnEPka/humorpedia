/**
 * Round a number to a fixed number of decimal places.
 * Returns a number (not a string).
 */
export function roundTo(value, decimals = 2) {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return 0;
  const factor = 10 ** decimals;
  return Math.round((n + Number.EPSILON) * factor) / factor;
}

/**
 * Format a number with up to `decimals` digits after decimal point,
 * trimming unnecessary trailing zeros (and a trailing dot).
 *
 * Examples (decimals=2):
 * - 1 -> "1"
 * - 1.2 -> "1.2"
 * - 1.23 -> "1.23"
 * - 1.20 -> "1.2"
 * - 1.00 -> "1"
 */
export function formatDecimalTrim(value, decimals = 2) {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return '';
  const fixed = n.toFixed(decimals);
  return fixed.replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
}

