import DOMPurify from 'dompurify';

/**
 * Sanitizes HTML content to prevent XSS attacks
 * @param {string} html - HTML string to sanitize
 * @param {object} options - DOMPurify configuration options
 * @returns {string} - Sanitized HTML string
 */
export function sanitizeHTML(html, options = {}) {
  if (typeof html !== 'string') {
    return '';
  }

  // Default configuration: allow common formatting tags but remove dangerous attributes
  const defaultOptions = {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'u', 's', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'ul', 'ol', 'li', 'blockquote', 'a', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'div', 'span', 'code', 'pre'
    ],
    ALLOWED_ATTR: [
      'href', 'title', 'alt', 'src', 'class', 'style', 'target', 'rel'
    ],
    ALLOW_DATA_ATTR: false,
    // Remove event handlers and javascript: URLs
    FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onfocus', 'onblur'],
  };

  const config = { ...defaultOptions, ...options };

  return DOMPurify.sanitize(html, config);
}

/**
 * Checks if a string contains HTML tags
 * @param {string} str - String to check
 * @returns {boolean} - True if string contains HTML tags
 */
export function containsHTML(str) {
  if (typeof str !== 'string') return false;
  return /<[a-z][\s\S]*>/i.test(str);
}
