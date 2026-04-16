import { useMemo, useState, useEffect } from 'react';
import { useLocation, Link, useNavigate } from 'react-router-dom';
import { Loader2, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import publicApi from '../utils/api';
import ModuleRenderer, { ModuleList } from '../components/ModuleRenderer';
import { LeagueSeasonsNav } from '../components/LeagueSeasonsNav';
import SeasonDetailPage from './SeasonDetailPage';
import { usePageTitle } from '@/utils/pageTitle';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function stripHtml(input) {
  if (typeof input !== 'string') return '';
  // Prefer a real HTML parser instead of regex-based stripping.
  // `textContent` yields a plain-text representation, avoiding tag re-introduction edge cases.
  try {
    if (typeof window !== 'undefined' && typeof window.DOMParser !== 'undefined') {
      const doc = new window.DOMParser().parseFromString(String(input), 'text/html');
      return (doc?.body?.textContent || '').replace(/\s+/g, ' ');
    }
  } catch {
    // Fall through to minimal safe fallback.
  }

  // Non-browser / extremely constrained environments: ensure no tag delimiters remain.
  return String(input).replace(/[<>]/g, '').replace(/\s+/g, ' ');
}

export default function SectionDetailPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [section, setSection] = useState(null);
  const [children, setChildren] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [kvnLeagueCards, setKvnLeagueCards] = useState({ main: [], former: [] });

  usePageTitle((section?.name || section?.title) || (loading ? 'Раздел' : (error ? 'Раздел не найден' : 'Раздел')));

  // Список slug'ов телевизионных лиг КВН
  const LEAGUE_SLUGS = ['1l-kvn', 'vl-kvn', 'premier-liga', 'ml-kvn', 'vul'];

  // Авторитетный slug лиги: сначала из URL, при отсутствии — из section.full_path
  const leagueSlugFromPath = (() => {
    const parts = (location.pathname || '').split('/').filter(Boolean);
    if (parts[0] !== 'kvn') return null;
    const slug = parts[1] || null;
    if (LEAGUE_SLUGS.includes(slug)) return slug;
    return null;
  })();
  const leagueSlugFromSectionFullPath = (() => {
    if (!section?.full_path) return null;
    const parts = String(section.full_path).split('/').filter(Boolean);
    if (parts[0] !== 'kvn') return null;
    const slug = parts[1] || null;
    if (LEAGUE_SLUGS.includes(slug)) return slug;
    return null;
  })();

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
        // Пробуем найти редирект для старых URL
        try {
          const redirectRes = await fetch(
            `${BACKEND_URL}/api/redirects/lookup?path=${encodeURIComponent(location.pathname)}`
          );
          if (redirectRes.ok) {
            const redirectData = await redirectRes.json();
            if (redirectData.found && redirectData.new_path) {
              navigate(redirectData.new_path, { replace: true });
              return;
            }
          }
        } catch (redirectErr) {
          console.warn('Redirect lookup failed:', redirectErr);
        }
        setError('Раздел не найден');
      } finally {
        setLoading(false);
      }
    };
    fetchSection();
  }, [location.pathname]);

  // Страницы лиг с сезонами (все телевизионные лиги)
  const isLeaguePage = section && (
    LEAGUE_SLUGS.includes(leagueSlugFromPath) ||
    LEAGUE_SLUGS.includes(section.slug) ||
    LEAGUE_SLUGS.some(ls => section.full_path === `kvn/${ls}`)
  );

  const isKvnRootPage = section && (section.full_path === 'kvn' || section.slug === 'kvn');

  const filteredChildren = useMemo(() => {
    if (!isKvnRootPage) return children;
    // Remove Dalnevostochnaya league from the main KVN page UI (content remains in DB)
    return (children || []).filter((c) => c?.slug !== 'dl-kvn');
  }, [children, isKvnRootPage]);

  // Fetch champions for league cards on KVN root
  useEffect(() => {
    if (!isKvnRootPage) return;

    const TARGET_YEAR = 2025; // current year minus one (per requirement)

    const leagueDefs = {
      main: [
        { slug: 'vl-kvn', title: 'Высшая лига КВН', href: '/kvn/vl-kvn/' },
        { slug: 'premier-liga', title: 'Премьер-лига КВН', href: '/kvn/premier-liga/' },
        { slug: '1l-kvn', title: 'Первая лига КВН', href: '/kvn/1l-kvn/' },
      ],
      former: [
        { slug: 'ml-kvn', title: 'Международная лига КВН', href: '/kvn/ml-kvn/' },
        { slug: 'vul', title: 'Высшая украинская лига КВН', href: '/kvn/vul/' },
      ],
    };

    const pickSeasonChampion = (seasons) => {
      const normalized = (seasons || [])
        .filter((s) => s && s.season_data)
        .map((s) => ({
          year: s.season_data?.year,
          winners: Array.isArray(s.season_data?.winners) ? s.season_data.winners : [],
          teamData: s.team_data || {},
        }))
        .filter((s) => typeof s.year === 'number');

      const exact = normalized.find((s) => s.year === TARGET_YEAR);
      const fallback = normalized.sort((a, b) => b.year - a.year)[0];
      const season = exact || fallback;
      if (!season) return { year: null, winner: null };

      const w0 = season.winners[0];
      if (!w0) return { year: season.year, winner: null };

      if (typeof w0 === 'string') {
        return { year: season.year, winner: { name: w0 } };
      }

      const slug = w0.slug || '';
      const teamInfo = slug ? (season.teamData?.[slug] || {}) : {};
      const name = teamInfo.name || w0.name || w0.slug || '';
      const city = teamInfo.city || w0.city || '';

      return {
        year: season.year,
        winner: {
          slug: slug || undefined,
          name: city && name && !name.includes(`(${city})`) ? `${name} (${city})` : name,
        },
      };
    };

    const pickLeagueBlurb = (leagueDoc, fallbackText) => {
      const raw = stripHtml(leagueDoc?.description || '').trim();
      if (raw) return raw;
      const textBlock = (leagueDoc?.modules || []).find((m) => m?.type === 'text_block' && m?.data?.content);
      const plain = stripHtml(textBlock?.data?.content || '').trim();
      return plain || fallbackText || '';
    };

    const FALLBACK_BLURBS = {
      'vl-kvn': 'Главная лига МС КВН: сезонные игры и финал — главная витрина движения.',
      'premier-liga': 'Вторая по статусу лига МС КВН, важный этап на пути в Высшую лигу.',
      '1l-kvn': 'Официальная лига МС КВН, где раскрываются будущие участники главных лиг.',
      'ml-kvn': 'Бывшая главная лига МС КВН (2014–2025), проводившаяся в Минске и Смоленске.',
      'vul': 'Лига МС КВН (1999–2013), важная часть истории украинского и постсоветского КВН.',
    };

    const load = async () => {
      try {
        const allDefs = [...leagueDefs.main, ...leagueDefs.former];
        const leagueDocs = await Promise.all(
          allDefs.map(async (ld) => {
            try {
              const res = await publicApi.getKvnByPath(`kvn/${ld.slug}`);
              return { def: ld, doc: res.data };
            } catch {
              return { def: ld, doc: null };
            }
          })
        );

        const seasonsByLeague = await Promise.all(
          allDefs.map(async (ld) => {
            try {
              const res = await publicApi.getKvnChildren(ld.slug);
              return { slug: ld.slug, items: res.data?.items || [] };
            } catch {
              return { slug: ld.slug, items: [] };
            }
          })
        );
        const seasonsMap = new Map(seasonsByLeague.map((x) => [x.slug, x.items]));

        const makeCard = ({ def, doc }) => {
          const blurb = pickLeagueBlurb(doc, FALLBACK_BLURBS[def.slug]);
          const { year, winner } = pickSeasonChampion(seasonsMap.get(def.slug));
          return {
            slug: def.slug,
            title: def.title,
            href: def.href,
            blurb,
            championYear: year,
            champion: winner,
          };
        };

        const cards = leagueDocs.map(makeCard);
        const main = leagueDefs.main.map((d) => cards.find((c) => c.slug === d.slug)).filter(Boolean);
        const former = leagueDefs.former.map((d) => cards.find((c) => c.slug === d.slug)).filter(Boolean);

        setKvnLeagueCards({ main, former });
      } catch (e) {
        // Keep page functional even if cards fail
        setKvnLeagueCards({ main: [], former: [] });
      }
    };

    load();
  }, [isKvnRootPage]);

  const scrollToAnchor = (id) => {
    if (!id) return;
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const kvnTocItems = useMemo(() => ([
    { id: 'glavnye-ligi', label: 'Главные лиги КВН' },
    { id: 'centralnye-ligi', label: 'Центральные лиги КВН' },
    { id: 'komandy-kvn', label: 'Команды КВН' },
    { id: 'specproekty-i-turniry', label: 'Спецпроекты и турниры КВН' },
    { id: 'istoriya-kvn', label: 'История телепередачи КВН' },
  ]), []);

  const renderKvnToc = () => (
    <Card className="mb-8">
      <CardHeader>
        <CardTitle className="text-xl">Оглавление</CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {kvnTocItems.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => scrollToAnchor(item.id)}
              className="text-left px-3 py-2 rounded-md hover:bg-gray-100 text-gray-900 transition-colors"
            >
              {item.label}
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );

  const LeagueCard = ({ card }) => {
    const championLabel = card?.champion
      ? (
        card.champion.slug
          ? <Link className="text-blue-600 hover:underline" to={`/kvn/teams/${card.champion.slug}`}>{card.champion.name}</Link>
          : <span>{card.champion.name}</span>
      )
      : <span className="text-gray-500">нет данных</span>;

    return (
      <Card className="hover:shadow-lg transition-shadow">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">
            <Link to={card.href} className="hover:underline">
              {card.title}
            </Link>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {card.blurb && (
            <p className="text-sm text-gray-600 line-clamp-4">{card.blurb}</p>
          )}
          <div className="text-sm">
            <div className="text-gray-500">Действующий чемпион{card.championYear ? ` (${card.championYear})` : ''}</div>
            <div className="font-medium text-gray-900">{championLabel}</div>
          </div>
        </CardContent>
      </Card>
    );
  };

  const renderKvnLeagueCards = () => (
    <div className="space-y-10 mb-10">
      <section id="glavnye-ligi" className="space-y-5 scroll-mt-24">
        <h2 className="text-2xl md:text-3xl font-bold text-gray-900">Главные лиги КВН</h2>
        <div className="grid lg:grid-cols-3 gap-6">
          {kvnLeagueCards.main.map((c) => <LeagueCard key={c.slug} card={c} />)}
        </div>
      </section>

      <section className="space-y-5">
        <h2 className="text-2xl md:text-3xl font-bold text-gray-900">Бывшие главные лиги</h2>
        <div className="grid md:grid-cols-2 gap-6">
          {kvnLeagueCards.former.map((c) => <LeagueCard key={c.slug} card={c} />)}
        </div>
      </section>
    </div>
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
      {isLeaguePage ? (
        <LeagueSeasonsPage section={section} seasons={children} leagueSlug={leagueSlugFromPath || leagueSlugFromSectionFullPath || section.slug} />
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
              {isKvnRootPage ? (
                (() => {
                  const sorted = (section.modules || [])
                    .filter((m) => m && m.visible !== false)
                    .slice()
                    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

                  // Heuristic: intro is the first text_block with empty title/data.title
                  const intro = sorted.find((m) => m.type === 'text_block' && !(m.title || m.data?.title));

                  // Hide the old TOC and old "Главные лиги" module blocks on the root page;
                  // replaced by dedicated UI (TOC + cards).
                  const rest = sorted.filter((m) => {
                    if (m === intro) return false;
                    if (m.type !== 'text_block') return true;
                    const t = (m.title || m.data?.title || '').toLowerCase();
                    if (t.includes('оглавление')) return false;
                    if (t.includes('главные лиги')) return false;
                    return true;
                  });

                  const wrapWithAnchor = (module) => {
                    if (module?.type !== 'text_block') return <ModuleRenderer key={module.id} module={module} />;
                    const title = module.title || module.data?.title || '';
                    const map = {
                      'Центральные лиги КВН': 'centralnye-ligi',
                      'Команды КВН': 'komandy-kvn',
                      'Спецпроекты и турниры КВН': 'specproekty-i-turniry',
                      'История телепередачи КВН': 'istoriya-kvn',
                    };
                    const anchor = map[title] || null;
                    return (
                      <section
                        key={module.id}
                        id={anchor || undefined}
                        className={anchor ? 'scroll-mt-24' : undefined}
                      >
                        <ModuleRenderer module={module} />
                      </section>
                    );
                  };

                  return (
                    <div className="space-y-10">
                      {intro && <ModuleRenderer module={intro} />}
                      {renderKvnToc()}
                      {renderKvnLeagueCards()}
                      <div className="space-y-10">
                        {rest.map(wrapWithAnchor)}
                      </div>
                    </div>
                  );
                })()
              ) : (
                <ModuleList modules={section.modules} />
              )}
            </div>
          )}

          {/* Children Sections */}
          {filteredChildren.length > 0 && (
            <div className="mt-12">
              <h2 className="text-2xl font-bold text-gray-900 mb-6">
                Подразделы
              </h2>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredChildren.map((child) => (
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

// Названия лиг для заголовков
const LEAGUE_NAMES = {
  'vl-kvn': 'Высшая лига КВН',
  'premier-liga': 'Премьер-лига КВН',
  '1l-kvn': 'Первая лига КВН',
  'ml-kvn': 'Международная лига КВН',
  'vul': 'Высшая украинская лига КВН',
};

// Названия лиг в родительном падеже (для "Чемпионы ... лиги")
const LEAGUE_NAMES_GENITIVE = {
  'vl-kvn': 'Высшей лиги КВН',
  'premier-liga': 'Премьер-лиги КВН',
  '1l-kvn': 'Первой лиги КВН',
  'ml-kvn': 'Международной лиги КВН',
  'vul': 'Высшей украинской лиги КВН',
};

// Блок таблицы чемпионов лиги (модуль first_league_champions или vl_league_champions)
function LeagueChampionsBlock({ normalizeSeasons, leagueSlug, title }) {
  if (!normalizeSeasons || normalizeSeasons.length === 0) return null;

  const defaultTitle = LEAGUE_NAMES_GENITIVE[leagueSlug]
    ? `Чемпионы ${LEAGUE_NAMES_GENITIVE[leagueSlug]}`
    : 'Чемпионы лиги';
  const heading = title || defaultTitle;

  // Колонка «Город проведения» показывается только для Первой лиги
  const showCityColumn = leagueSlug === '1l-kvn';

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
                  {showCityColumn && (
                    <TableHead className="w-[220px]">Город проведения лиги</TableHead>
                  )}
                  <TableHead>Чемпион(ы)</TableHead>
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
                    {showCityColumn && (
                      <TableCell>
                        {season.venueCity ? (
                          season.venueCity
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </TableCell>
                    )}
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

// Страница лиги с сезонами (все телевизионные лиги)
function LeagueSeasonsPage({ section, seasons, leagueSlug }) {
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

  const leagueName = LEAGUE_NAMES[leagueSlug] || leagueSlug;

  // Определяем, является ли модуль блоком чемпионов
  const isChampionsModule = (module) => {
    if (module.type === 'first_league_champions' || module.type === 'vl_league_champions') return true;
    if (module.type === 'text_block') {
      const title = (module.title || module.data?.title || '').toLowerCase();
      if (title.includes('чемпион')) return true;
      // Для VUL: заголовок внутри контента
      const content = (module.data?.content || '').toLowerCase();
      if (content.match(/^<h[1-6]>\s*чемпион/)) return true;
    }
    return false;
  };

  // Определяем, является ли модуль старой статической таблицей чемпионов
  const isStaticChampionTable = (module) => {
    if (module.type !== 'text_block') return false;
    const title = (module.title || module.data?.title || '').trim();
    if (title) return false; // Если есть заголовок — это не «голая» таблица
    const content = (module.data?.content || '').trim();
    const lower = content.toLowerCase();
    // Таблица чемпионов: содержит <table> и (слово «чемпион» или заголовок «Сезон»)
    if (!content.startsWith('<table')) return false;
    if (lower.includes('чемпион') || lower.includes('<strong>сезон</strong>')) return true;
    return false;
  };

  // Определяем, является ли модуль старой навигационной сеткой годов (год-ссылки в таблице)
  const isStaticYearNavGrid = (module) => {
    if (module.type !== 'text_block') return false;
    const title = (module.title || module.data?.title || '').trim();
    if (title) return false;
    const content = (module.data?.content || '').trim();
    if (!content.startsWith('<table')) return false;
    // Проверяем, что таблица содержит в основном 4-значные годы как ссылки
    const yearLinks = (content.match(/>\d{4}<\/a>/g) || []).length;
    const totalCells = (content.match(/<td/g) || []).length;
    return yearLinks > 0 && totalCells > 0 && yearLinks >= totalCells * 0.5;
  };

  return (
    <div className="space-y-10">
      {/* Модули страницы (чемпионы лиги, текстовые блоки и т.д. — порядок в админке) */}
      {(() => {
        const sortedModules = (section.modules || [])
          .slice()
          .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

        // Отслеживаем, был ли уже отрисован динамический блок чемпионов
        let championsRendered = false;

        // Собираем индексы модулей, которые нужно скрыть
        // (статические таблицы чемпионов, если динамический блок уже отрисован)
        const modulesToHide = new Set();

        // Первый проход: находим модули-чемпионы и их смежные статические таблицы
        let firstChampionIdx = -1;
        for (let i = 0; i < sortedModules.length; i++) {
          if (isChampionsModule(sortedModules[i])) {
            if (firstChampionIdx === -1) {
              firstChampionIdx = i;
            } else {
              // Последующие блоки «Чемпионы» — скрываем (будет одна динамическая таблица)
              modulesToHide.add(i);
            }
            // Скрываем следующие модули, если это статические таблицы чемпионов
            for (let j = i + 1; j < sortedModules.length; j++) {
              if (isStaticChampionTable(sortedModules[j])) {
                modulesToHide.add(j);
              } else {
                break;
              }
            }
          }
          // Старые навигационные сетки годов — скрываем (заменены на LeagueSeasonsNav)
          if (isStaticYearNavGrid(sortedModules[i])) {
            modulesToHide.add(i);
          }
        }

        return (
          <div className="space-y-10">
            {sortedModules.map((module, idx) => {
              // Скрытые модули
              if (modulesToHide.has(idx)) return null;

              // Первый модуль-чемпион → динамическая таблица
              if (isChampionsModule(module) && !championsRendered) {
                championsRendered = true;
                // Для модулей с городом в заголовке (например "в Минске") — используем дефолтный заголовок,
                // т.к. динамическая таблица охватывает все города
                const moduleTitle = module.title || module.data?.title || '';
                const cityPattern = /\sв\s/i;
                const passTitle = cityPattern.test(moduleTitle) ? null : moduleTitle;
                return (
                  <LeagueChampionsBlock
                    key={module.id || `champ-${idx}`}
                    normalizeSeasons={normalizeSeasons}
                    leagueSlug={leagueSlug}
                    title={passTitle}
                  />
                );
              }

              // Последующие блоки чемпионов — уже скрыты через modulesToHide
              if (isChampionsModule(module) && championsRendered) return null;

              return (
                <div key={module.id || `mod-${idx}`}>
                  <ModuleRenderer module={module} />
                </div>
              );
            })}

            {/* Если ни один модуль-чемпион не нашёлся — всё равно показываем динамическую таблицу */}
            {!championsRendered && normalizeSeasons.length > 0 && (
              <LeagueChampionsBlock
                normalizeSeasons={normalizeSeasons}
                leagueSlug={leagueSlug}
              />
            )}
          </div>
        );
      })()}

      {/* Все сезоны лиги */}
      <LeagueSeasonsNav
        seasons={normalizeSeasons}
        leagueSlug={leagueSlug}
        title={`Все сезоны ${LEAGUE_NAMES_GENITIVE[leagueSlug] || leagueName}`}
      />
    </div>
  );
}

