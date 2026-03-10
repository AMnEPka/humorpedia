import { useState, useEffect } from 'react';
import { useLocation, Link, useNavigate } from 'react-router-dom';
import { Loader2, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import publicApi from '../utils/api';
import ModuleRenderer from '../components/ModuleRenderer';
import SeasonDetailPage from './SeasonDetailPage';
import { usePageTitle } from '@/utils/pageTitle';

export default function SectionDetailPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [section, setSection] = useState(null);
  const [children, setChildren] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  usePageTitle((section?.name || section?.title) || (loading ? 'Раздел' : (error ? 'Раздел не найден' : 'Раздел')));

  useEffect(() => {
    const fetchSection = async () => {
      setLoading(true);
      setError('');
      try {
        // Get current path
        const path = location.pathname;
        const cleanPath = path.startsWith('/') ? path.substring(1) : path;
        let res;
        
        // Check if this is a KVN page
        if (cleanPath.startsWith('kvn') && !cleanPath.startsWith('kvn/teams')) {
          // Try KVN API first
          try {
            res = await publicApi.getKvnByPath(cleanPath);
          } catch (kvnErr) {
            // Fall back to sections API
            res = await publicApi.getSectionByPath(path);
          }
        } else {
          // Use sections API
          res = await publicApi.getSectionByPath(path);
        }
        
        const data = res.data;
        setSection(data);

        // Если есть season_data - используем новый формат
        // (SeasonDetailPage будет показан ниже)

        // Если есть season_data - не загружаем children (они не нужны для нового формата)
        if (!data.season_data) {
          // Fetch children if show_children_list is true
          if (data.show_children_list) {
            const childrenRes = await publicApi.getSectionChildren(data._id);
            setChildren(childrenRes.data.items || []);
          } else if (data.children && data.children.length > 0) {
            // For KVN pages, children are already in the response
            setChildren(data.children || []);
          } else if (data.id) {
            // For KVN pages (identified by presence of 'id' field), try to fetch children if not included
            try {
              const childrenRes = await publicApi.getKvnChildren(data.slug);
              setChildren(childrenRes.data.items || []);
            } catch (err) {
              console.log('No children or error fetching children');
            }
          }
        }
      } catch (err) {
        console.error('Error fetching section:', err);
        setError('Раздел не найден');
      } finally {
        setLoading(false);
      }
    };
    fetchSection();
  }, [location.pathname]);

  // Определяем, является ли страница страницей с сезонами Первой лиги КВН
  const isFirstLeaguePage = section && (
    section.slug === '1l-kvn' ||
    section.full_path === 'kvn/1l-kvn' ||
    location.pathname === '/kvn/1l-kvn'
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !section) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
        <p className="text-gray-500 mb-4">{error || 'Раздел не найден'}</p>
        <Button asChild>
          <Link to="/">Вернуться на главную</Link>
        </Button>
      </div>
    );
  }

  // Если есть season_data - показываем новый формат
  if (section.season_data) {
    // Передаём данные через location.state, чтобы SeasonDetailPage не делал повторный запрос
    return <SeasonDetailPage seasonData={section} />;
  }

  // Иначе - старый формат
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumbs */}
      {section.breadcrumbs && section.breadcrumbs.length > 0 && (
        <nav className="mb-6">
          <ol className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
            <li>
              <Link to="/" className="hover:text-blue-600">
                Главная
              </Link>
            </li>
            {section.breadcrumbs.map((crumb, idx) => (
              <li key={idx} className="flex items-center gap-2">
                <ChevronRight className="h-4 w-4" />
                <Link to={crumb.full_path} className="hover:text-blue-600">
                  {crumb.title}
                </Link>
              </li>
            ))}
            <li className="flex items-center gap-2">
              <ChevronRight className="h-4 w-4" />
              <span className="text-gray-900">{section.title}</span>
            </li>
          </ol>
        </nav>
      )}

      {/* Header */}
      <header className="mb-8">
        <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
          {section.name || section.title}
        </h1>

        {section.description && (
          <p className="text-lg text-gray-600 max-w-3xl">{section.description}</p>
        )}

        {section.tags && section.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {section.tags.map((tag) => (
              <Link key={tag} to={`/tags/${encodeURIComponent(tag)}`}>
                <Badge variant="secondary" className="cursor-pointer hover:bg-blue-100">
                  {tag}
                </Badge>
              </Link>
            ))}
          </div>
        )}
      </header>
      {isFirstLeaguePage ? (
        <FirstLeagueSeasonsPage section={section} seasons={children} />
      ) : (
        <>
          {/* Cover Image / Poster */}
          {(section.cover_image || section.poster) && (
            <div className="mb-8">
              <img
                src={(section.cover_image || section.poster)?.url}
                alt={(section.cover_image || section.poster)?.alt || section.name || section.title}
                className="w-full h-auto rounded-lg shadow-lg object-cover max-h-[500px]"
              />
            </div>
          )}

          {/* Modular Content */}
          {section.modules && section.modules.length > 0 && (
            <div className="mb-8">
              <ModuleList modules={section.modules} />
            </div>
          )}

          {/* Children Sections */}
          {children.length > 0 && (
            <div className="mt-12">
              <h2 className="text-2xl font-bold text-gray-900 mb-6">
                Подразделы
              </h2>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {children.map((child) => (
                  <Card
                    key={child.id || child._id}
                    className="hover:shadow-lg transition-shadow cursor-pointer"
                    onClick={() => navigate(child.full_path || `/${child.slug}`)}
                  >
                    <CardHeader>
                      <CardTitle className="text-lg">{child.name || child.title}</CardTitle>
                    </CardHeader>
                    {child.description && (
                      <CardContent>
                        <p className="text-sm text-gray-600 line-clamp-3">
                          {child.description}
                        </p>
                      </CardContent>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* Related Content */}
          {section.child_types && section.child_types.length > 0 && (
            <div className="mt-12 p-6 bg-blue-50 rounded-lg">
              <p className="text-sm text-gray-600">
                Этот раздел может содержать: {section.child_types.join(', ')}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// Вспомогательная функция для извлечения города из facts сезона
function getCityFromFactsForSeason(facts) {
  if (!facts || typeof facts !== 'object') return '';

  const cityValue =
    facts['Город'] ||
    facts['город'] ||
    facts['Города'] ||
    facts['города'] ||
    '';

  if (!cityValue) return '';

  if (typeof cityValue === 'string') {
    let cleaned = cityValue
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<[^>]+>/g, '')
      .trim();

    const cities = cleaned
      .split(/[\n,;/]/)
      .map((c) => c.trim())
      .filter((c) => c.length > 0);

    return cities.length > 0 ? cities.join(', ') : '';
  }

  return String(cityValue).trim();
}

// Блок таблицы чемпионов (рендерится как модуль типа first_league_champions)
function FirstLeagueChampionsBlock({ normalizeSeasons, leagueSlug, title }) {
  if (!normalizeSeasons || normalizeSeasons.length === 0) return null;

  const heading = title || 'Чемпионы Первой лиги КВН';

  return (
    <section className="space-y-4">
      <h2 className="text-2xl md:text-3xl font-bold text-gray-900">{heading}</h2>
      <Card>
        <CardContent className="pt-6">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[90px]">Сезон</TableHead>
                  <TableHead className="w-[220px]">Город проведения лиги</TableHead>
                  <TableHead>Команда</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {normalizeSeasons.map((season) => (
                  <TableRow key={season.id}>
                    <TableCell className="font-medium">
                      <Link
                        to={
                          season.full_path
                            ? `/${season.full_path}`
                            : `/kvn/${leagueSlug}/${season.slug}`
                        }
                        className="text-blue-600 hover:underline"
                      >
                        {season.year}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {season.venueCity ? (
                        season.venueCity
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {season.winners.length === 0 && (
                        <span className="text-gray-400">нет данных</span>
                      )}
                      {season.winners.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {season.winners.map((winner, idx) => {
                            const isString = typeof winner === 'string';
                            const winnerSlug = isString ? null : (winner.slug || '');
                            const teamInfo = winnerSlug ? season.teamData?.[winnerSlug] || {} : {};
                            let winnerName =
                              (teamInfo.name ||
                                (isString ? winner : (winner.name || winner.slug || '')));
                            let winnerCity =
                              teamInfo.city ||
                              (!isString && winner && typeof winner === 'object' ? (winner.city || '') : '');

                            if (!winnerName) return null;

                            if (winnerCity && !winnerName.includes(`(${winnerCity})`)) {
                              winnerName = `${winnerName} (${winnerCity})`;
                            }

                            const content = winnerSlug ? (
                              <Link
                                to={`/kvn/teams/${winnerSlug}`}
                                className="text-blue-600 hover:underline"
                              >
                                {winnerName}
                              </Link>
                            ) : (
                              <span>{winnerName}</span>
                            );

                            return (
                              <span key={idx} className="inline-flex items-center">
                                {idx > 0 && <span className="mx-1 text-gray-400">/</span>}
                                {content}
                              </span>
                            );
                          })}
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}

// Специальная страница для сезонов Первой лиги КВН
function FirstLeagueSeasonsPage({ section, seasons }) {
  const leagueSlug = '1l-kvn';

  const normalizeSeasons = (seasons || [])
    .filter((s) => s && s.season_data)
    .map((s) => {
      const sd = s.season_data || {};
      const year =
        sd.year ||
        (() => {
          const m = String(s.slug || '').match(/\d{4}/);
          return m ? parseInt(m[0], 10) : null;
        })();

      const venueCity = getCityFromFactsForSeason(s.facts);

      return {
        id: s.id || s._id || s.slug,
        title: s.name || s.title || `${year || ''} сезон`,
        slug: s.slug,
        full_path: s.full_path,
        year,
        winners: Array.isArray(sd.winners) ? sd.winners : [],
        venueCity,
        teamData: s.team_data || {},
        description: sd.description || s.description || '',
      };
    })
    .filter((s) => s.year)
    .sort((a, b) => a.year - b.year);

  const uniqueCities = Array.from(
    new Set(
      normalizeSeasons
        .map((s) => s.venueCity)
        .filter((c) => c && c.length > 0)
    )
  );

  return (
    <div className="space-y-10">
      {/* Краткое описание лиги */}
      {(section.description || (section.cover_image || section.poster)) && (
        <div className="grid gap-6 md:grid-cols-[minmax(0,2fr)_minmax(0,1.2fr)] items-start mb-4">
          <div>
            {section.description && (
              <p className="text-lg text-gray-700 leading-relaxed">
                {section.description}
              </p>
            )}
          </div>
          {(section.cover_image || section.poster) && (
            <div className="w-full">
              <img
                src={(section.cover_image || section.poster)?.url}
                alt={(section.cover_image || section.poster)?.alt || section.name || section.title}
                className="w-full h-auto rounded-xl shadow-lg object-cover max-h-[360px]"
              />
            </div>
          )}
        </div>
      )}

      {/* Модули страницы (в т.ч. «Чемпионы Первой лиги КВН» — порядок задаётся в админке) */}
      {(() => {
        const sortedModules = (section.modules || [])
          .slice()
          .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

        return (
          <div className="space-y-10">
            {sortedModules.map((module) =>
              module.type === 'first_league_champions' ? (
                <FirstLeagueChampionsBlock
                  key={module.id}
                  normalizeSeasons={normalizeSeasons}
                  leagueSlug={leagueSlug}
                  title={module.title || module.data?.title}
                />
              ) : (
                <div key={module.id}>
                  <ModuleRenderer module={module} />
                </div>
              )
            )}
          </div>
        );
      })()}

      {/* Города проведения */}
      {uniqueCities.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-2xl font-bold text-gray-900">
            Города проведения Первой лиги
          </h2>
          <p className="text-gray-600">
            На основе сезонов, уже занесённых в базу.
          </p>
          <div className="flex flex-wrap gap-2">
            {uniqueCities.map((city) => (
              <Badge key={city} variant="outline" className="text-base py-1.5 px-3">
                {city}
              </Badge>
            ))}
          </div>
        </section>
      )}

      {/* Все сезоны */}
      {normalizeSeasons.length > 0 && (
        <section className="space-y-4 pt-4 border-t mt-4">
          <h2 className="text-2xl font-bold text-gray-900">
            Все сезоны в базе
          </h2>
          <div className="flex flex-wrap gap-2">
            {normalizeSeasons.map((season) => (
              <Button
                key={season.id}
                asChild
                variant="outline"
                size="sm"
                className="rounded-full"
              >
                <Link
                  to={
                    season.full_path
                      ? `/${season.full_path}`
                      : `/kvn/${leagueSlug}/${season.slug}`
                  }
                >
                  {season.year}
                </Link>
              </Button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

