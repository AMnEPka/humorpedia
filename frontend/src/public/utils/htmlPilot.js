import { useLayoutEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { buildPageTitle } from '../../utils/pageTitle';

let active = null;
let generation = 0;
export const isHtmlPilotEnabled = () => typeof window !== 'undefined' && window.__HTML_PILOT__ === true;
export const isHtmlPilotDetail = path => /^\/(people|articles)\/[^/]+\/?$/.test(path);
const fallback = () => document.getElementById('html-pilot-fallback');
function showRoot() {
  const root = document.getElementById('root');
  if (root) { root.hidden = false; root.removeAttribute('aria-hidden'); }
}
function clearHead() {
  document.head.querySelectorAll('meta[name="description"],meta[name="robots"],meta[property^="og:"],link[rel="canonical"]').forEach(node => node.remove());
  document.title = buildPageTitle('');
}
function meta(attribute, name, value) {
  if (typeof value !== 'string') return;
  const node = document.createElement('meta');
  node.setAttribute(attribute, name); node.content = value; document.head.appendChild(node);
}
function applyMetadata(data) {
  clearHead();
  if (typeof data.title === 'string') document.title = data.title;
  meta('name', 'description', data.description); meta('name', 'robots', data.robots);
  for (const [key, value] of Object.entries({title:data.title, description:data.description, url:data.canonical_url,
    type:data.og_type, image:data.image_url, 'image:alt':data.image_alt, locale:data.locale})) meta('property', 'og:' + key, value);
  if (typeof data.canonical_url === 'string') {
    const node = document.createElement('link'); node.rel = 'canonical'; node.href = data.canonical_url; document.head.appendChild(node);
  }
  if (typeof data.lang === 'string') document.documentElement.lang = data.lang;
}
export function isHtmlPilotResultCurrent(result, pathname, key) {
  return Boolean(active && active.path === pathname && active.key === key && result?.token === active);
}
export function beginPage(pathname, navigationKey) {
  if (!isHtmlPilotEnabled()) return null;
  if (navigationKey !== undefined && active?.path === pathname && active.key === navigationKey) return active;
  active = {path:pathname, key:navigationKey, generation:++generation};
  document.getElementById('html-pilot-status')?.remove();
  document.getElementById('root')?.removeAttribute('data-html-pilot-ready');
  if ((fallback() && fallback().dataset.path !== pathname) || !isHtmlPilotDetail(pathname)) {
    fallback()?.remove(); showRoot();
  }
  if (!isHtmlPilotDetail(pathname)) clearHead();
  return active;
}
export function commitPage(token, {status, metadata = null}) {
  if (!isHtmlPilotEnabled() || !token || token !== active) return false;
  if (status === 'network_error') {
    if (!fallback() || fallback().dataset.path !== token.path) clearHead();
    if (!document.getElementById('html-pilot-status')) {
      const node = document.createElement('p'); node.id = 'html-pilot-status'; node.setAttribute('role', 'status');
      node.textContent = 'Не удалось загрузить интерактивную страницу. Попробуйте обновить страницу.';
      (fallback() || document.body).appendChild(node);
    }
    return true;
  }
  if (!['ready', 'not_found'].includes(status)) return false;
  if (status === 'not_found') { clearHead(); meta('name', 'robots', 'noindex,follow'); }
  else if (metadata) applyMetadata(metadata);
  else if (!fallback()) clearHead();
  document.getElementById('html-pilot-status')?.remove();
  fallback()?.remove(); showRoot();
  document.getElementById('root')?.setAttribute('data-html-pilot-ready', token.path);
  if (status === 'ready' && window.location.hash) {
    let id;
    try { id = decodeURIComponent(window.location.hash.slice(1)); } catch { id = ''; }
    document.getElementById(id)?.scrollIntoView?.({block:'start'});
  }
  return true;
}
export function useHtmlPilotNavigation() {
  const {pathname, key} = useLocation();
  useLayoutEffect(() => { beginPage(pathname, key); }, [pathname, key]);
}
export function useHtmlPilotReady(result, {preview = false} = {}) {
  const {pathname, key} = useLocation();
  useLayoutEffect(() => {
    if (preview || !isHtmlPilotEnabled()) return;
    const token = beginPage(pathname, key);
    if (result?.token === token) commitPage(token, result);
  }, [pathname, key, preview, result]);
}
