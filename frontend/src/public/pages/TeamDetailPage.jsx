import { Fragment, useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, Users, MapPin, Trophy, Share2, Calendar, List } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import publicApi from '../utils/api';
import { 
  isSystemModule 
} from '@/components/SystemModules';
import { usePageTitle } from '@/utils/pageTitle';
import TeamParticipations from '../components/competitions/TeamParticipations';
import TeamRoster from '../components/competitions/TeamRoster';
import CommonModuleRenderer from '../components/ModuleRenderer';
import { teamPageTitle, teamSubtitle } from '@/utils/teams';
import FittedImage from '@/components/FittedImage';
import { teamLogoUrl } from '@/utils/media';
import RelatedArticles from '../components/RelatedArticles';
import RatingCard from '../components/RatingCard';
import RelatedNews from '../components/RelatedNews';
import { sharePage } from '../utils/share';
import TeamProjects, {
  TEAM_PROJECTS_TITLE,
  hasManualTeamProjects,
  isTeamProjectsModule,
} from '../components/TeamProjects';

// Старый модуль «Список игр команды» (HTML-таблица из season_data) — вместо него блок «Телевизионные лиги КВН»
const isGamesTableModule = (m) => m.type === 'text_block' && (m.data?.title || '').trim().toLowerCase().startsWith('список игр команды');

export function teamTocItems(modules = [], mode = 'auto', projectsVisible = false) {
  const effectiveMode = mode === 'auto' ? 'sections' : mode;
  if (effectiveMode === 'timeline') {
    const timelineModule = modules.find(m => m.type === 'timeline');
    const events = timelineModule?.data?.events || timelineModule?.data?.items || [];
    return events.map(item => ({
      id: `timeline-${item.year}`,
      label: item.year,
      title: item.title,
    }));
  }

  const items = [];
  let projectsAdded = false;
  for (const module of modules) {
    if (isTeamProjectsModule(module)) {
      if (projectsVisible && !projectsAdded) {
        items.push({
          id: 'section-team-projects',
          label: TEAM_PROJECTS_TITLE,
          title: TEAM_PROJECTS_TITLE,
        });
        projectsAdded = true;
      }
      continue;
    }
    if (module.type === 'text_block' && module.data?.title) {
      items.push({
        id: `section-${module.id}`,
        label: module.data.title,
        title: module.data.title,
      });
    }
  }
  if (projectsVisible && !projectsAdded) {
    items.push({
      id: 'section-team-projects',
      label: TEAM_PROJECTS_TITLE,
      title: TEAM_PROJECTS_TITLE,
    });
  }
  return items;
}

// Table of Contents component for teams
function TableOfContents({ modules, mode = 'auto', projectsVisible = false }) {
  const items = useMemo(
    () => teamTocItems(modules, mode, projectsVisible),
    [modules, mode, projectsVisible]
  );

  if (items.length === 0) return null;

  const scrollToSection = (id) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <List className="h-5 w-5" /> Оглавление
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <nav className="space-y-1">
          {items.map((item, i) => (
            <button
              key={i}
              onClick={() => scrollToSection(item.id)}
              className="w-full text-left px-2 py-1.5 text-sm rounded hover:bg-gray-100 transition-colors"
            >
              {item.label}
            </button>
          ))}
        </nav>
      </CardContent>
    </Card>
  );
}

// Команда КВН (/kvn/teams/:slug) или команда шоу (/shows/{шоу}/teams/{slug} — showTeamPath из ShowDetailPage)
export default function TeamDetailPage({ showTeamPath = null }) {
  const { slug } = useParams();
  const [team, setTeam] = useState(null);
  const [members, setMembers] = useState(null);
  const [teamProjects, setTeamProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [shareMessage, setShareMessage] = useState('');

  usePageTitle(teamPageTitle(team) || (loading ? 'Команда' : (error ? 'Команда не найдена' : 'Команда')));

  useEffect(() => {
    const fetchTeam = async () => {
      setLoading(true);
      setError('');
      setShareMessage('');
      try {
        const res = showTeamPath ? await publicApi.getTeamByPath(showTeamPath) : await publicApi.getTeam(slug);
        setTeam(res.data);
      } catch (err) {
        setTeam(null);
        setError('Команда не найдена');
      } finally {
        setLoading(false);
      }
    };
    fetchTeam();
  }, [slug, showTeamPath]);

  // Составы и турниры — по _id: slug команды шоу уникален только внутри шоу
  const teamKey = team?._id;
  useEffect(() => {
    if (!teamKey) return undefined;
    let cancelled = false;
    setMembers(null);
    publicApi.getTeamMembers(teamKey)
      .then(res => { if (!cancelled) setMembers(res.data); })
      .catch(() => { if (!cancelled) setMembers(null); });
    return () => { cancelled = true; };
  }, [teamKey]);

  useEffect(() => {
    if (!teamKey || team?.show_id) {
      setTeamProjects([]);
      return undefined;
    }
    let cancelled = false;
    setTeamProjects([]);
    publicApi.getTeamProjects(teamKey)
      .then(res => { if (!cancelled) setTeamProjects(res.data?.items || []); })
      .catch(() => { if (!cancelled) setTeamProjects([]); });
    return () => { cancelled = true; };
  }, [teamKey, team?.show_id]);

  // Разделяем модули на системные (sidebar) и контентные (main)
  // Хуки должны быть до любых return
  const sidebarModules = useMemo(() => {
    if (!team?.modules) return [];
    return team.modules
      .filter(m => m.visible !== false && isSystemModule(m.type))
      .sort((a, b) => (a.order || 0) - (b.order || 0));
  }, [team?.modules]);

  const contentModules = useMemo(() => {
    if (!team?.modules) return [];
    return team.modules
      .filter(m => m.visible !== false && !isSystemModule(m.type) && !isGamesTableModule(m))
      .sort((a, b) => (a.order || 0) - (b.order || 0));
  }, [team?.modules]);

  const manualProjectModules = useMemo(() => {
    if (team?.show_id) return [];
    return contentModules.filter(isTeamProjectsModule);
  }, [contentModules, team?.show_id]);
  const firstProjectModuleId = manualProjectModules[0]?.id;
  const projectsVisible = !team?.show_id
    && (teamProjects.length > 0 || hasManualTeamProjects(manualProjectModules));

  // Текстовые блоки состава, разобранные полностью, заменяются структурированным составом
  const replacedRosterIds = useMemo(() => {
    if (!members?.total) return new Set();
    const blocks = (members.roster_blocks || []).filter(b => b.count > 0);
    // Если хоть один блок разобран не полностью — показываем исходный текст, чтобы не потерять пояснения
    if (blocks.length === 0 || blocks.some(b => !b.complete)) return new Set();
    return new Set(blocks.map(b => b.module_id));
  }, [members]);
  const firstRosterId = contentModules.find(m => replacedRosterIds.has(m.id))?.id;

  const cityValue = team?.city || team?.facts?.['Город'] || team?.facts?.city || '';

  const factEntries = useMemo(() => {
    const facts = team?.facts || {};
    if (!facts || typeof facts !== 'object') return [];

    const order = Array.isArray(team?.facts_order) ? team.facts_order : [];
    const seen = new Set();
    const entries = [];

    for (const key of order) {
      if (Object.prototype.hasOwnProperty.call(facts, key)) {
        const value = facts[key];
        if (value !== null && value !== undefined && String(value) !== '') {
          entries.push([key, value]);
          seen.add(key);
        }
      }
    }

    for (const [key, value] of Object.entries(facts)) {
      if (seen.has(key)) continue;
      if (value !== null && value !== undefined && String(value) !== '') {
        entries.push([key, value]);
      }
    }

    return entries;
  }, [team?.facts, team?.facts_order]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !team) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
        <p className="text-gray-500 mb-4">{error || 'Команда не найдена'}</p>
        <Button asChild>
          <Link to={showTeamPath ? '/shows' : '/kvn/teams'}>Вернуться к списку</Link>
        </Button>
      </div>
    );
  }

  // Хлебные крошки: у команды шоу — шоу и страница «Команды …» (от API), у команды КВН — список команд КВН
  const crumbs = team.show_id
    ? [{ title: 'Шоу', path: '/shows' }, ...(team.breadcrumbs || [])]
    : [{ title: 'КВН', path: '/kvn/teams' }];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <ol className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
          <li><Link to="/" className="hover:text-blue-600">Главная</Link></li>
          {crumbs.map((crumb) => (
            <li key={crumb.path} className="flex items-center gap-2">
              <span>/</span>
              <Link to={crumb.path} className="hover:text-blue-600">{crumb.title}</Link>
            </li>
          ))}
          <li>/</li>
          <li className="text-gray-900 truncate max-w-[200px]">{team.title}</li>
        </ol>
      </nav>

      {/* Hero */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-800 rounded-2xl p-8 md:p-12 text-white mb-8">
        <div className="flex flex-col md:flex-row items-center gap-8">
          {/* Logo/Photo - рендерится если есть модуль poster_photo */}
          {sidebarModules.find(m => m.type === 'poster_photo') && (
            <div className="w-32 h-32 bg-white/10 rounded-xl overflow-hidden flex-shrink-0">
              <FittedImage
                src={teamLogoUrl(team)}
                fallbackKey={team}
                alt={team.title}
                className="w-full h-full bg-white/95"
                loading="eager"
              />
            </div>
          )}
          <div className="text-center md:text-left">
            <h1 className="text-3xl md:text-4xl font-bold mb-2">{team.title}</h1>
            {team.show_id && (
              <div className="text-blue-100 mb-2">
                {team.show?.full_path
                  ? <Link to={`/shows/${team.show.full_path}`} className="hover:underline">{teamSubtitle(team)}</Link>
                  : teamSubtitle(team)}
              </div>
            )}
            {cityValue && (
              <div className="flex items-center justify-center md:justify-start gap-2 text-blue-100">
                <MapPin className="h-4 w-4" />
                <span>{cityValue}</span>
              </div>
            )}
            {/* Tags - рендерятся если есть модуль tags_cloud */}
            {sidebarModules.find(m => m.type === 'tags_cloud') && team.tags?.length > 0 && (
              <div className="flex flex-wrap justify-center md:justify-start gap-2 mt-4">
                {team.tags.map((tag, i) => (
                  <Link key={i} to={`/tags/${encodeURIComponent(tag)}`}
                    className="rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-white">
                    <Badge variant="secondary" className="bg-white/20 text-white hover:bg-white/30 min-h-11 flex items-center">{tag}</Badge>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Sidebar */}
        <div className="lg:col-span-1 space-y-6 min-w-0">
          <RatingCard entityType="team" entityId={team._id || team.id} />

          {/* Facts Table - рендерится если есть модуль facts_table */}
          {sidebarModules.find(m => m.type === 'facts_table') && factEntries.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Trophy className="h-5 w-5" /> Информация
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <table className="w-full text-sm border-collapse border border-gray-200">
                  <tbody>
                    {factEntries.map(([key, value], i) => {
                      const displayKey = key === 'city' ? 'Город' : key;
                      return (
                      <tr key={i} className={`border-b border-gray-200 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                        <td className="py-2 pr-4 pl-2 text-gray-600 font-medium border-r border-gray-200">{displayKey}</td>
                        <td className="py-2 pl-2" dangerouslySetInnerHTML={{ __html: value }} />
                      </tr>
                    )})}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}

          {/* Та же команда в других шоу (related_team_ids) */}
          {team.related_teams?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" /> {team.show_id ? 'Команда в КВН и других шоу' : 'Команда в других шоу'}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0 space-y-1">
                {team.related_teams.map(rt => (
                  <Link key={rt.id} to={rt.url} className="block p-2 rounded hover:bg-gray-100 transition-colors">
                    <div className="font-medium text-sm text-blue-700">{rt.name}</div>
                    <div className="text-xs text-gray-500">{[teamSubtitle(rt), rt.city].filter(Boolean).join(' · ')}</div>
                  </Link>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Team Members */}
          {team.members?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" /> Состав
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="space-y-3">
                  {team.members.map((member, i) => (
                    <Link 
                      key={i} 
                      to={`/people/${member.slug}`}
                      className="flex items-center gap-3 p-2 rounded hover:bg-gray-100 transition-colors"
                    >
                      <div className="w-10 h-10 bg-gray-100 rounded-full overflow-hidden">
                        {member.photo ? (
                          <img src={member.photo} alt={member.name} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm font-bold">
                            {member.name?.charAt(0)}
                          </div>
                        )}
                      </div>
                      <div>
                        <div className="font-medium text-sm">{member.name}</div>
                        {member.role && <div className="text-xs text-gray-500">{member.role}</div>}
                      </div>
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Achievements */}
          {team.achievements?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Trophy className="h-5 w-5" /> Достижения
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <ul className="space-y-2">
                  {team.achievements.map((ach, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <Trophy className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
                      <span>{ach}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Social Links - рендерится если есть модуль social_links */}
          {sidebarModules.find(m => m.type === 'social_links') && team.social_links && Object.keys(team.social_links).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Share2 className="h-5 w-5" /> Ссылки
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="space-y-2">
                  {team.social_links.website && (
                    <a 
                      href={team.social_links.website} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-blue-600 hover:underline text-sm"
                    >
                      🌐 Официальный сайт
                    </a>
                  )}
                  {team.social_links.vk && (
                    <a 
                      href={team.social_links.vk} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-blue-600 hover:underline text-sm"
                    >
                      VK
                    </a>
                  )}
                  {team.social_links.youtube && (
                    <a 
                      href={team.social_links.youtube} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-blue-600 hover:underline text-sm"
                    >
                      YouTube
                    </a>
                  )}
                  {team.social_links.instagram && (
                    <a 
                      href={team.social_links.instagram} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-blue-600 hover:underline text-sm"
                    >
                      Instagram
                    </a>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          <Button variant="outline" className="w-full" onClick={async () => {
            try { setShareMessage(await sharePage(team.title) ? 'Ссылка скопирована' : ''); }
            catch { setShareMessage('Не удалось скопировать ссылку'); }
          }}>
            <Share2 className="mr-2 h-4 w-4" /> Поделиться
          </Button>
          <span role="status" className="block text-sm text-gray-600">{shareMessage}</span>

          {/* Table of Contents */}
          <TableOfContents modules={contentModules} projectsVisible={projectsVisible} />
        </div>

        {/* Main content */}
        <div className="lg:col-span-2 space-y-6 min-w-0">
          {/* History/Bio */}
          {team.history && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>История</CardTitle>
                </CardHeader>
                <CardContent>
                  <div
                    className="prose prose-blue max-w-none overflow-x-auto break-words"
                    dangerouslySetInnerHTML={{ __html: team.history }}
                  />
                </CardContent>
              </Card>
              <RelatedNews entityType="team" entityId={team._id || team.id || team.slug} />
            </>
          )}

          {!team.history && contentModules.length === 0 && (
            <RelatedNews entityType="team" entityId={team._id || team.id || team.slug} />
          )}

          {/* Content Modules: старые таблицы игр скрыты, полностью разобранный состав — структурой */}
          {contentModules.map((module, i) => {
            let renderedModule;
            if (!team.show_id && isTeamProjectsModule(module)) {
              renderedModule = module.id === firstProjectModuleId ? (
                <TeamProjects items={teamProjects} manualModules={manualProjectModules} />
              ) : null;
            } else if (replacedRosterIds.has(module.id)) {
              renderedModule = module.id === firstRosterId ? (
                <TeamRoster
                  members={members}
                  title={module.data?.title || 'Состав команды'}
                  anchorId={`section-${module.id}`}
                />
              ) : null;
            } else {
              renderedModule = <ModuleRenderer module={module} />;
            }

            return (
              <Fragment key={module.id || i}>
                {renderedModule}
                {!team.history && i === 0 && (
                  <RelatedNews entityType="team" entityId={team._id || team.id || team.slug} />
                )}
              </Fragment>
            );
          })}

          {!team.show_id && manualProjectModules.length === 0 && teamProjects.length > 0 && (
            <TeamProjects items={teamProjects} />
          )}

          <TeamParticipations teamSlug={team._id} teamName={team.name || team.title} />
          <RelatedArticles contentType="team" contentId={team._id || team.id || team.slug} />
        </div>
      </div>
    </div>
  );
}

// Module renderer component (same as PersonDetailPage)
export function ModuleRenderer({ module }) {
  // Add table and heading styles
  const contentStyles = `
    /* Таблицы */
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
    
    /* Заголовки h3 в тексте - жирные и увеличенные */
    h3 {
      font-size: 1.25rem;
      font-weight: 700;
      margin-top: 1.5rem;
      margin-bottom: 0.75rem;
      color: #1f2937;
      line-height: 1.4;
    }
    
    /* Также стилизуем strong на случай других заголовков */
    p strong:only-child,
    p > strong:first-child {
      font-size: 1.125rem;
      font-weight: 700;
      display: block;
      margin-top: 1.5rem;
      margin-bottom: 0.5rem;
      color: #1f2937;
    }
  `;

  switch (module.type) {
    case 'text_block':
      return (
        <Card id={`section-${module.id}`} className="scroll-mt-20">
          {module.data?.title && (
            <CardHeader>
              <CardTitle>{module.data.title}</CardTitle>
            </CardHeader>
          )}
          <CardContent>
            <style>{contentStyles}</style>
            <div 
              className="prose prose-blue max-w-none overflow-x-auto break-words"
              dangerouslySetInnerHTML={{ __html: module.data?.content || '' }}
            />
          </CardContent>
        </Card>
      );
    
    case 'timeline':
      const timelineEvents = module.data?.events || module.data?.items || [];
      return (
        <Card>
          <CardHeader>
            <CardTitle>{module.data?.title || 'Хронология'}</CardTitle>
          </CardHeader>
          <CardContent>
            {timelineEvents.length === 0 ? (
              <p className="text-gray-500">Нет событий</p>
            ) : (
              <div className="relative pl-6 border-l-2 border-blue-200 space-y-6">
                {timelineEvents.map((item, i) => (
                  <div key={i} id={`timeline-${item.year}`} className="relative scroll-mt-20">
                    <div className="absolute -left-[25px] w-4 h-4 bg-blue-600 rounded-full border-4 border-white" />
                    <div className="text-sm text-blue-600 font-semibold">{item.year}</div>
                    <div className="font-medium">{item.title}</div>
                    {item.description && (
                      <p className="text-gray-600 text-sm mt-1" dangerouslySetInnerHTML={{ __html: item.description }} />
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      );
    
    case 'gallery':
      return (
        <Card>
          <CardHeader>
            <CardTitle>{module.data?.title || 'Галерея'}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {module.data?.images?.map((img, i) => (
                <img 
                  key={i} 
                  src={img.url} 
                  alt={img.caption || ''}
                  className="rounded-lg aspect-square object-cover"
                />
              ))}
            </div>
          </CardContent>
        </Card>
      );

    case 'tv_appearances':
      return <CommonModuleRenderer module={module} />;
    
    default:
      return <CommonModuleRenderer module={module} />;
  }
}
