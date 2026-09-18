import { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { publicApi } from '../utils/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Loader2, Calendar, Tv, Users, ExternalLink, Trophy } from 'lucide-react';
import EmojiRating from '@/components/EmojiRating';
import { isSystemModule } from '@/components/SystemModules';
import { usePageTitle } from '@/utils/pageTitle';
import { contentImageUrl, orderedFacts } from '@/utils/media';
import FittedImage from '@/components/FittedImage';
import ContentTable from '../components/ContentTable';
import CommonModuleRenderer from '../components/ModuleRenderer';
import CollapsibleCard from '../components/CollapsibleCard';
import TeamDetailPage from './TeamDetailPage';
import { isShowTeamPath } from '@/utils/teams';
import ForeignAgentNotice from '../components/ForeignAgentNotice';

// Module renderer component
export function ModuleRenderer({ module }) {
  if (!module || module.visible === false) return null;
  
  // Add table styles
  const tableStyles = `
    table { 
      border-collapse: collapse; 
      width: 100%; 
      margin: 1rem 0;
      border: 1px solid #e5e7eb;
    }
    th, td { 
      border: 1px solid #e5e7eb; 
      padding: 0.5rem 0.75rem; 
      text-align: left;
    }
    th { 
      background-color: #f3f4f6; 
      font-weight: 600;
    }
    tr:nth-child(even) {
      background-color: #f9fafb;
    }
  `;
  
  switch (module.type) {
    case 'text_block':
      if (module.data?.collapsed) {
        return (
          <CollapsibleCard title={module.data.title}>
            <style>{tableStyles}</style>
            <div
              className="prose prose-sm max-w-none overflow-x-auto break-words"
              dangerouslySetInnerHTML={{ __html: module.data?.content || '' }}
            />
          </CollapsibleCard>
        );
      }
      return (
        <Card>
          {module.data?.title && (
            <CardHeader>
              <CardTitle>{module.data.title}</CardTitle>
            </CardHeader>
          )}
          <CardContent>
            <style>{tableStyles}</style>
            <div
              className="prose prose-lg max-w-none overflow-x-auto break-words"
              dangerouslySetInnerHTML={{ __html: module.data?.content || '' }}
            />
          </CardContent>
        </Card>
      );
    
    case 'gallery':
    case 'video':
      return <CommonModuleRenderer module={module} />;
    
    case 'cast_list':
      return (
        <div>
          <h3 className="text-lg font-bold mb-3">{module.data?.title || 'Участники'}</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {module.data?.cast?.map((person, i) => (
              <Link
                key={i}
                to={`/people/${person.slug || person.id}`}
                className="text-center group"
              >
                <div className="aspect-square rounded-full overflow-hidden bg-muted mb-2 mx-auto w-20 h-20">
                  <FittedImage
                    src={contentImageUrl(person, person.photo)}
                    fallbackKey={person.slug || person.name}
                    alt={person.name}
                    className="w-full h-full"
                    fit="cover"
                  />
                </div>
                <div className="font-medium text-sm group-hover:text-primary transition-colors">
                  {person.name}
                </div>
                {person.role && (
                  <div className="text-xs text-muted-foreground">{person.role}</div>
                )}
              </Link>
            ))}
          </div>
        </div>
      );
    
    case 'table':
      if (!module.data?.rows?.length) return null;
      if (module.data.collapsed) {
        return (
          <CollapsibleCard title={module.data.title}>
            <ContentTable data={module.data} />
          </CollapsibleCard>
        );
      }
      return (
        <Card>
          {module.data.title && <CardHeader><CardTitle>{module.data.title}</CardTitle></CardHeader>}
          <CardContent><ContentTable data={module.data} /></CardContent>
        </Card>
      );

    case 'timeline':
      if (!module.data?.events?.length) return null;
      return (
        <Card>
          <CardHeader><CardTitle>{module.data.title || 'Хронология'}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {module.data.events.map((event, i) => (
              <div key={i} className="border-l-2 border-blue-500 pl-4">
                <div className="text-sm font-medium text-blue-600">{event.date || event.year}</div>
                <div className="font-medium">{event.title}</div>
                {event.description && (
                  <div className="prose prose-sm max-w-none text-gray-600 mt-1" dangerouslySetInnerHTML={{ __html: event.description }} />
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      );

    case 'participants':
      if (!module.data?.items?.length) return null;
      return (
        <Card>
          <CardHeader><CardTitle>{module.data.title || 'Участники'}</CardTitle></CardHeader>
          <CardContent>
            <div className="grid sm:grid-cols-2 gap-4">
              {module.data.items.map((item, i) => {
                const photo = contentImageUrl(item.person_slug || item.name, item.photo);
                const card = (
                  <>
                    <div className="w-20 h-24 flex-shrink-0 rounded-md overflow-hidden bg-muted">
                      <FittedImage
                        src={photo}
                        fallbackKey={item.person_slug || item.name}
                        alt={item.name}
                        className="w-full h-full"
                        imageClassName="object-top"
                        fit="cover"
                      />
                    </div>
                    <div className="min-w-0 text-sm">
                      <div className="font-semibold text-base mb-1">{item.name}</div>
                      {(item.facts || []).map((fact, j) => (
                        <div key={j} className="text-gray-600">
                          <span className="text-gray-500">{fact.title}:</span> {fact.value}
                        </div>
                      ))}
                    </div>
                  </>
                );
                return item.person_url ? (
                  <Link key={i} to={item.person_url} className="flex gap-3 p-3 rounded-lg border bg-white min-w-0 hover:border-blue-400 hover:bg-blue-50/30 transition-colors">
                    {card}
                  </Link>
                ) : (
                  <div key={i} className="flex gap-3 p-3 rounded-lg border bg-white min-w-0">{card}</div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      );

    case 'seasons_list':
      return (
        <div>
          <h3 className="text-lg font-bold mb-3">{module.data?.title || 'Сезоны'}</h3>
          <div className="space-y-2">
            {module.data?.seasons?.map((season, i) => (
              <Card key={i}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{season.title || `Сезон ${i + 1}`}</div>
                      {season.year && (
                        <div className="text-sm text-muted-foreground">{season.year}</div>
                      )}
                    </div>
                    {season.episodes_count && (
                      <Badge variant="secondary">{season.episodes_count} серий</Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      );
    
    default:
      return <CommonModuleRenderer module={module} />;
  }
}

export default function ShowDetailPage() {
  const { slug, parentSlug, childSlug, grandchildSlug, greatGrandchildSlug } = useParams();
  // Собираем полный путь из всех параметров
  // Если есть parentSlug, значит это вложенный путь
  const fullPath = parentSlug
    ? [parentSlug, childSlug, grandchildSlug, greatGrandchildSlug].filter(Boolean).join('/')
    : slug;

  // /shows/{шоу}/teams/{slug} — страница команды шоу
  if (isShowTeamPath(fullPath)) {
    return <TeamDetailPage showTeamPath={fullPath} />;
  }
  return <ShowPage fullPath={fullPath} />;
}

function ShowPage({ fullPath }) {
  const [show, setShow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  usePageTitle(show?.title || (loading ? 'Шоу' : (error ? 'Шоу не найдено' : 'Шоу')));

  useEffect(() => {
    if (!fullPath) {
      setError('Шоу не найдено');
      setLoading(false);
      return;
    }

    // by-path отдаёт и корневые, и вложенные шоу вместе с дочерними страницами и хлебными крошками
    publicApi.getShowByPath(fullPath)
      .then(res => setShow(res.data))
      .catch(() => setError('Шоу не найдено'))
      .finally(() => setLoading(false));
  }, [fullPath]);

  // Разделяем модули на системные (sidebar) и контентные (main)
  // Хуки должны быть до любых return
  const sidebarModules = useMemo(() => {
    if (!show?.modules) return [];
    return show.modules
      .filter(m => m.visible !== false && isSystemModule(m.type))
      .sort((a, b) => (a.order || 0) - (b.order || 0));
  }, [show?.modules]);

  const contentModules = useMemo(() => {
    if (!show?.modules) return [];
    return show.modules
      .filter(m => m.visible !== false && !isSystemModule(m.type))
      .sort((a, b) => (a.order || 0) - (b.order || 0));
  }, [show?.modules]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !show) {
    return (
      <div className="container max-w-4xl mx-auto py-12 px-4 text-center">
        <h1 className="text-2xl font-bold mb-4">Шоу не найдено</h1>
        <Button asChild>
          <Link to="/shows">← К списку шоу</Link>
        </Button>
      </div>
    );
  }

  const facts = show.facts || {};

  // Строим breadcrumb из full_path
  const buildBreadcrumbs = () => {
    const crumbs = [
      { label: 'Главная', path: '/' },
      { label: 'Шоу', path: '/shows' }
    ];
    
    (show.breadcrumbs || []).forEach((crumb) => crumbs.push({ label: crumb.title, path: crumb.path }));
    
    // Текущая страница (без ссылки)
    crumbs.push({ label: show.title, path: null });
    
    return crumbs;
  };

  const breadcrumbs = buildBreadcrumbs();

  return (
    <div className="container max-w-7xl mx-auto py-8 px-4">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm text-gray-500 flex-wrap">
          {breadcrumbs.map((crumb, idx) => (
            <li key={idx} className="flex items-center gap-2">
              {idx > 0 && <span>/</span>}
              {crumb.path ? (
                <Link to={crumb.path} className="hover:text-blue-600">{crumb.label}</Link>
              ) : (
                <span className="text-gray-900 truncate max-w-[200px]">{crumb.label}</span>
              )}
            </li>
          ))}
        </ol>
      </nav>

      {/* Hero */}
      <div className="mb-8">
        <div className="flex items-start gap-6">
          {/* Poster - рендерится если есть модуль poster_photo */}
          {sidebarModules.find(m => m.type === 'poster_photo') && (
            <div className="w-32 sm:w-48 flex-shrink-0">
              <FittedImage
                src={contentImageUrl(show, show.poster)}
                fallbackKey={show}
                alt={show.title}
                className="aspect-[2/3] rounded-xl shadow-lg"
                loading="eager"
              />
            </div>
          )}

          {/* Title & Description */}
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl sm:text-4xl font-bold mb-4">{show.title}</h1>
            {show.description && (
              <div 
                className="text-lg text-gray-700 leading-relaxed mb-4"
                dangerouslySetInnerHTML={{ __html: show.description }}
              />
            )}
            
            {/* Tags - рендерятся если есть модуль tags_cloud */}
            {sidebarModules.find(m => m.type === 'tags_cloud') && show.tags?.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-4">
                {show.tags.map(tag => (
                  <Link key={tag} to={`/tags/${encodeURIComponent(tag)}`}>
                    <Badge variant="secondary" className="cursor-pointer hover:bg-gray-300">{tag}</Badge>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main content - 2 column layout */}
      <div className="grid lg:grid-cols-3 gap-8">
        {/* Sidebar */}
        <div className="lg:col-span-1 space-y-6 min-w-0">
          {/* Дочерние страницы: сезоны, подпроекты, разделы */}
          {show.children?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Tv className="h-5 w-5" /> Разделы
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <nav className="space-y-1">
                  {show.children.map((child) => (
                    <Link
                      key={child._id}
                      to={`/shows/${child.full_path || child.slug}`}
                      className="block px-2 py-1.5 text-sm rounded hover:bg-gray-100 transition-colors"
                    >
                      {child.title}
                    </Link>
                  ))}
                </nav>
              </CardContent>
            </Card>
          )}

          {/* Facts Table - рендерится если есть модуль facts_table */}
          {sidebarModules.find(m => m.type === 'facts_table') && show.facts && Object.keys(show.facts).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Trophy className="h-5 w-5" /> Информация
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <table className="w-full text-sm border-collapse border border-gray-200">
                  <tbody>
                    {orderedFacts(show.facts, show.facts_order).map(([key, value], i) => (
                      <tr key={i} className={`border-b border-gray-200 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                        <td className="py-2 pr-4 pl-2 text-gray-600 font-medium border-r border-gray-200 align-top">{key}</td>
                        <td className="py-2 pl-2" dangerouslySetInnerHTML={{ __html: value }} />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}

          {/* Social Links - рендерится если есть модуль social_links */}
          {sidebarModules.find(m => m.type === 'social_links') && show.social_links && Object.keys(show.social_links).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ExternalLink className="h-5 w-5" /> Ссылки
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0 space-y-2">
                {show.social_links.website && (
                  <a 
                    href={show.social_links.website} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-blue-600 hover:underline text-sm"
                  >
                    🌐 Официальный сайт
                  </a>
                )}
                {show.social_links.vk && (
                  <a 
                    href={show.social_links.vk} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-blue-600 hover:underline text-sm"
                  >
                    VK
                  </a>
                )}
                {show.social_links.youtube && (
                  <a 
                    href={show.social_links.youtube} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-blue-600 hover:underline text-sm"
                  >
                    YouTube
                  </a>
                )}
              </CardContent>
            </Card>
          )}

          {/* Rating Widget - рендерится если есть модуль rating_widget */}
          {sidebarModules.find(m => m.type === 'rating_widget') && (
            <Card>
              <CardHeader>
                <CardTitle>Оценка</CardTitle>
              </CardHeader>
              <CardContent>
                <EmojiRating 
                  value={show.rating?.average || 0}
                  max={10}
                  readonly={false}
                />
                <div className="mt-2 text-sm text-gray-600 text-center">
                  {show.rating?.average ? (
                    <>
                      {show.rating.average.toFixed(1)} / 10
                      {show.rating.count > 0 && ` (${show.rating.count} ${show.rating.count === 1 ? 'голос' : 'голосов'})`}
                    </>
                  ) : (
                    'Пока нет оценок'
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Main content */}
        <div className="lg:col-span-2 space-y-6 min-w-0">
          {contentModules.map((module) => (
            <ModuleRenderer key={module.id} module={module} />
          ))}
          <ForeignAgentNotice
            visible={show.foreign_agent_notice}
            notices={show.foreign_agent_notices}
          />
        </div>
      </div>
    </div>
  );
}
