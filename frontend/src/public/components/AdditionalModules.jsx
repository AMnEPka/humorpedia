import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { publicApi } from '../utils/api';
import { teamUrl } from '@/utils/teams';
import { moduleNames } from '@/moduleContract';

export function ModuleFrame({ module, children }) {
  return <section className="my-6 space-y-3">
    <h3 className="text-lg font-bold">{module.title || module.data?.title || moduleNames[module.type]}</h3>
    {children}
  </section>;
}

export function StructuredListModule({ module }) {
  const data = module.data || {};
  const key = { team_members: 'members', tv_appearances: 'items', games_list: 'games', episodes_list: 'episodes' }[module.type];
  const items = data[key] || (module.type === 'tv_appearances' ? data.appearances : []) || [];
  return <ModuleFrame module={module}>
    {items.length === 0 ? <p className="text-muted-foreground">Пока нет записей.</p> : <ul className="space-y-3">
      {items.map((item, index) => <li key={index} className="rounded border p-3 space-y-1">
        <div className="font-semibold">{item.name || item.show || item.title || item.opponent || `Запись ${index + 1}`}</div>
        {[['Роль', 'role'], ['Дата', 'date'], ['Эфир', 'air_date'], ['Сезон', 'season'], ['Выпуск', 'episode'],
          ['Лига', 'league'], ['Результат', 'result'], ['Баллы', 'score'], ['С', 'joined_year'], ['По', 'left_year']]
          .filter(([, field]) => item[field] !== undefined && item[field] !== null && item[field] !== '')
          .map(([label, field]) => <p key={field}>{label}: {item[field]}</p>)}
        {item.guests?.length > 0 && <p>Гости: {item.guests.join(', ')}</p>}
        {(item.description || item.notes) && <p>{item.description || item.notes}</p>}
        {item.active === false && <p>Бывший участник</p>}
        {item.video_url && <a href={item.video_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">Смотреть видео</a>}
      </li>)}
    </ul>}
  </ModuleFrame>;
}

export function contentHref(item, type) {
  if (!item?.slug) return null;
  if (type === 'team') return teamUrl(item);
  if (type === 'show') return `/shows/${(item.full_path || item.slug).replace(/^\/+/, '')}`;
  const route = { person: 'people', article: 'articles', news: 'news', quiz: 'quizzes', city: 'city' }[type];
  return route ? `/${route}/${item.slug}` : null;
}

export function ContentWidget({ module }) {
  const { pathname } = useLocation();
  const [state, setState] = useState({ loading: true, items: [], error: false });
  const type = module.type === 'random_page' ? (module.data?.content_type || 'article') : 'article';
  const requestedLimit = Number(module.data?.limit);
  const limit = Number.isFinite(requestedLimit) && requestedLimit > 0 ? Math.min(20, Math.floor(requestedLimit)) : 3;
  useEffect(() => {
    let active = true;
    setState({ loading: true, items: [], error: false });
    const patterns = {
      person: /^\/people\/([^/]+)\/?$/, article: /^\/articles\/([^/]+)\/?$/,
      news: /^\/news\/([^/]+)\/?$/, quiz: /^\/quizzes\/([^/]+)\/?$/, city: /^\/city\/([^/]+)\/?$/,
      team: /^\/(?:kvn\/teams|shows\/.+\/teams)\/([^/]+)\/?$/,
      show: /^\/shows\/(?!.*\/teams\/)(?:[^/]+\/)*([^/]+)\/?$/,
    };
    const currentSlug = pathname.match(patterns[type] || /$^/)?.[1];
    const request = module.type === 'random_page'
      ? publicApi.getRandomContent(type, currentSlug ? { exclude_slug: decodeURIComponent(currentSlug) } : {})
      : publicApi.getArticles({ limit: limit + 1, exclude_archived: true, ...(module.type === 'best_articles' ? { sort: '-rating' } : { featured: true }) });
    request.then(({ data }) => {
      if (!active) return;
      const seen = new Set();
      const items = (module.type === 'random_page' ? (data.error ? [] : [data]) : data.items || [])
        .filter(item => {
          const href = contentHref(item, type);
          if (!href || href.replace(/\/$/, '') === pathname.replace(/\/$/, '') || item.status === 'archived' || seen.has(href)) return false;
          seen.add(href);
          return true;
        }).slice(0, limit);
      setState({ loading: false, items, error: false });
    }).catch(() => { if (active) setState({ loading: false, items: [], error: true }); });
    return () => { active = false; };
  }, [module.type, type, limit, pathname]);
  return <ModuleFrame module={module}>
    {state.loading ? <p role="status">Загрузка…</p> : state.error ? <p role="alert">Не удалось загрузить материалы.</p>
      : state.items.length === 0 ? <p>Пока нет подходящих материалов.</p>
        : <ul className="space-y-2">{state.items.map(item => <li key={contentHref(item, type)}>
          <Link className="text-blue-600 underline" to={contentHref(item, type)}>{item.title || item.name || item.slug}</Link>
          {item.excerpt && <p className="text-sm text-muted-foreground">{item.excerpt}</p>}
        </li>)}</ul>}
  </ModuleFrame>;
}

// Обычная ссылка на ролик не всегда разрешена для iframe.
export function videoEmbedUrl(raw) {
  try {
    const url = new URL(raw);
    if (!['https:', 'http:'].includes(url.protocol)) return null;
    const host = url.hostname.toLowerCase();
    if (['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'].includes(host)) {
      const id = host === 'youtu.be' ? url.pathname.slice(1) : url.searchParams.get('v') || url.pathname.split('/')[2];
      return /^[\w-]{11}$/.test(id || '') ? `https://www.youtube-nocookie.com/embed/${id}` : null;
    }
    if (host === 'www.youtube-nocookie.com' && /^\/embed\/[\w-]{11}$/.test(url.pathname)) return url.href;
    if (['vk.com', 'vkvideo.ru'].includes(host) && url.pathname === '/video_ext.php') return url.href;
    return null;
  } catch { return null; }
}

export function VideoModule({ module }) {
  const url = module.data?.url || '';
  const embed = videoEmbedUrl(url);
  return <ModuleFrame module={module}>
    {embed ? <div className="aspect-video rounded-lg overflow-hidden bg-black">
      <iframe src={embed} className="w-full h-full" allowFullScreen title={module.data?.title || 'Видео'} />
    </div> : /^https?:\/\//i.test(url) ? <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">Смотреть видео</a>
      : <p>Добавьте ссылку на видео.</p>}
    {module.data?.caption && <p>{module.data.caption}</p>}
  </ModuleFrame>;
}
