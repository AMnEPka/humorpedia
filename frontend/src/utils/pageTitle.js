import { useEffect } from 'react';

const DOMAIN = 'humorpedia.ru';
const SUFFIX = `| ${DOMAIN}`;

export function buildPageTitle(pageTitle) {
  const t = (pageTitle ?? '').toString().trim();
  if (!t) return `Humorpedia ${SUFFIX}`;

  // Avoid double suffix if caller already provided it
  if (t.toLowerCase().endsWith(SUFFIX.toLowerCase())) return t;
  return `${t} ${SUFFIX}`;
}

export function usePageTitle(pageTitle) {
  useEffect(() => {
    document.title = buildPageTitle(pageTitle);
  }, [pageTitle]);
}

