import { useState, useEffect } from 'react';
import { useLocation, Link, useNavigate } from 'react-router-dom';
import { Loader2, ChevronLeft, ChevronRight, Trophy, Calendar, Users, Award } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table';
import publicApi from '../utils/api';
import { StageSection } from '../components/StageSection';

// Вспомогательная функция для извлечения города из facts
// Поддерживает поля "Город", "город", "Города", "города"
// Обрабатывает случаи, когда городов несколько (разделенных новой строкой или запятой)
// Удаляет HTML-теги (особенно <br>) из значения
function getCityFromFacts(facts) {
  if (!facts || typeof facts !== 'object') return '';
  
  // Ищем город по разным вариантам названия поля
  const cityValue = facts['Город'] || facts['город'] || facts['Города'] || facts['города'] || '';
  
  if (!cityValue) return '';
  
  // Если это строка, обрабатываем возможные разделители
  if (typeof cityValue === 'string') {
    // Сначала удаляем HTML-теги (особенно <br>, <br/>, <br />)
    let cleaned = cityValue
      .replace(/<br\s*\/?>/gi, '\n') // Заменяем <br> на новую строку
      .replace(/<[^>]+>/g, '') // Удаляем все остальные HTML-теги
      .trim();
    
    // Разделяем по новой строке, запятой или слэшу
    const cities = cleaned
      .split(/[\n,;/]/)
      .map(c => c.trim())
      .filter(c => c.length > 0);
    
    // Возвращаем все города через запятую
    return cities.length > 0 ? cities.join(', ') : '';
  }
  
  return String(cityValue).trim();
}

export default function SeasonDetailPage({ seasonData: initialSeasonData = null }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [season, setSeason] = useState(initialSeasonData);
  const [loading, setLoading] = useState(!initialSeasonData);
  const [error, setError] = useState('');
  const [teamNames, setTeamNames] = useState({}); // Кэш полных названий команд по slug

  useEffect(() => {
    // Если данные уже переданы через props - используем их
    if (initialSeasonData) {
      setSeason(initialSeasonData);
      setLoading(false);
      return;
    }

    // Иначе загружаем данные
    const fetchSeason = async () => {
      setLoading(true);
      setError('');
      try {
        const path = location.pathname;
        const cleanPath = path.startsWith('/') ? path.substring(1) : path;
        
        const res = await publicApi.getKvnByPath(cleanPath);
        const data = res.data;
        
        // Проверяем наличие season_data
        if (!data.season_data) {
          setError('Сезон ещё не обработан. Используется старый формат.');
          return;
        }
        
        setSeason(data);
      } catch (err) {
        console.error('Error fetching season:', err);
        setError('Сезон не найден');
      } finally {
        setLoading(false);
      }
    };
    fetchSeason();
  }, [location.pathname, initialSeasonData]);

  // Загружаем полные названия команд из базы данных для winners и all_teams
  useEffect(() => {
    const loadTeamNames = async () => {
      if (!season?.season_data) return;
      
      const { winners = [], all_teams = [] } = season.season_data;
      const slugsToLoad = new Set();
      
      // Собираем все slug из winners и all_teams
      winners.forEach(winner => {
        const slug = typeof winner === 'string' ? winner : (winner.slug || '');
        if (slug && !teamNames[slug]) {
          slugsToLoad.add(slug);
        }
      });
      
      all_teams.forEach(team => {
        const slug = typeof team === 'string' ? team : (team.slug || '');
        if (slug && !teamNames[slug]) {
          slugsToLoad.add(slug);
        }
      });
      
      if (slugsToLoad.size === 0) return;
      
      const namesMap = { ...teamNames };
      
      // Загружаем команды параллельно
      await Promise.all(
        Array.from(slugsToLoad).map(async (slug) => {
          try {
            const res = await publicApi.getTeam(slug);
            const teamData = res.data;
            // Используем полное название из базы данных
            const teamName = teamData.name || teamData.title || '';
            const cityFromFacts = getCityFromFacts(teamData.facts);
            namesMap[slug] = {
              name: teamName,
              city: cityFromFacts
            };
          } catch (err) {
            // Если команда не найдена, используем данные из сезона
            const winner = winners.find(w => (typeof w === 'string' ? w : w.slug) === slug);
            const team = all_teams.find(t => (typeof t === 'string' ? t : t.slug) === slug);
            const teamData = winner || team;
            if (teamData) {
              const name = typeof teamData === 'string' ? teamData : (teamData.name || slug);
              const city = typeof teamData === 'object' ? (teamData.city || '') : '';
              namesMap[slug] = { name, city };
            }
          }
        })
      );
      
      setTeamNames(namesMap);
    };
    
    loadTeamNames();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !season) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
        <p className="text-gray-500 mb-4">{error || 'Сезон не найден'}</p>
        <Button asChild>
          <Link to="/">Вернуться на главную</Link>
        </Button>
      </div>
    );
  }

  const seasonData = season.season_data || {};
  const { 
    stages = [], 
    winners = [], 
    all_teams = [], 
    jury = [], 
    editors = [], 
    hosts = [],
    host = '', 
    year = 0, 
    league_slug: seasonLeagueSlug = '',
    intro_html = '',
    extra_sections = [],
    metadata = {}
  } = seasonData;
  const prevSeason = seasonData.prev_season;
  const nextSeason = seasonData.next_season;
  
  // Извлекаем league_slug из текущего URL, если он не заполнен в seasonData
  // Формат URL: /kvn/vl-kvn/vl-2010 -> league_slug = "vl-kvn"
  let league_slug = seasonLeagueSlug;
  if (!league_slug && location.pathname) {
    const pathParts = location.pathname.split('/').filter(Boolean);
    // Ищем структуру: kvn / league-slug / season-slug
    if (pathParts.length >= 3 && pathParts[0] === 'kvn') {
      league_slug = pathParts[1];
    } else if (pathParts.length >= 2 && pathParts[0] === 'kvn') {
      // Если только 2 части, возможно это лига без сезона
      league_slug = pathParts[1];
    }
  }
  
  // Если все еще нет league_slug, пытаемся извлечь из full_path сезона
  if (!league_slug && season?.full_path) {
    const pathParts = season.full_path.split('/').filter(Boolean);
    if (pathParts.length >= 2 && pathParts[0] === 'kvn') {
      league_slug = pathParts[1];
    }
  }
  
  // Функция для извлечения года из slug
  const extractYearFromSlug = (slug) => {
    if (!slug) return '';
    // Ищем 4-значное число в slug
    const match = slug.match(/\d{4}/);
    return match ? match[0] : slug;
  };
  
  // Извлекаем годы для отображения
  const prevSeasonYear = prevSeason ? extractYearFromSlug(prevSeason) : '';
  const nextSeasonYear = nextSeason ? extractYearFromSlug(nextSeason) : '';
  
  // Ведущие - используем список hosts или одиночный host
  const hostsList = hosts.length > 0 ? hosts : (host ? [host] : []);

  // Определяем название лиги
  const leagueNames = {
    'vl-kvn': 'Высшая лига КВН',
    'premier-liga': 'Премьер-лига КВН',
    '1l-kvn': 'Первая лига КВН',
    'ml-kvn': 'Международная лига КВН',
    'vul': 'Высшая украинская лига КВН',
  };
  const leagueName = leagueNames[league_slug] || league_slug;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumbs */}
      {season.breadcrumbs && season.breadcrumbs.length > 0 && (
        <nav className="mb-6">
          <ol className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
            <li>
              <Link to="/" className="hover:text-blue-600">
                Главная
              </Link>
            </li>
            {season.breadcrumbs.map((crumb, idx) => (
              <li key={idx} className="flex items-center gap-2">
                <ChevronRight className="h-4 w-4" />
                <Link to={`/${crumb.full_path}`} className="hover:text-blue-600">
                  {crumb.title}
                </Link>
              </li>
            ))}
            <li className="flex items-center gap-2">
              <ChevronRight className="h-4 w-4" />
              <span className="text-gray-900">{season.name || season.title}</span>
            </li>
          </ol>
        </nav>
      )}

      {/* Header with navigation */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          {prevSeason && league_slug && (
            <Button variant="outline" asChild>
              <Link to={`/kvn/${league_slug}/${prevSeason}`}>
                <ChevronLeft className="mr-2 h-4 w-4" />
                {prevSeasonYear}
              </Link>
            </Button>
          )}
          {(!prevSeason || !league_slug) && <div />}
          
          <div className="text-center">
            <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-2">
              {season.name || season.title}
            </h1>
            <p className="text-xl text-gray-600">
              {leagueName} • {year}
            </p>
          </div>
          
          {nextSeason && league_slug && (
            <Button variant="outline" asChild>
              <Link to={`/kvn/${league_slug}/${nextSeason}`}>
                {nextSeasonYear}
                <ChevronRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          )}
          {(!nextSeason || !league_slug) && <div />}
        </div>
      </div>

      {/* Poster/Image */}
      {season.poster && (
        <div className="mb-8">
          <img
            src={season.poster.url || season.poster}
            alt={season.poster.alt || season.name || season.title}
            className="w-full h-auto rounded-lg shadow-lg object-cover max-h-[500px]"
          />
        </div>
      )}

      {/* Tags */}
      {season.tags && season.tags.length > 0 && (
        <div className="mb-8 flex flex-wrap gap-2">
          {season.tags.map((tag, idx) => (
            <Badge key={idx} variant="secondary" asChild>
              <Link to={`/tags/${tag}`}>{tag}</Link>
            </Badge>
          ))}
        </div>
      )}

      {/* Информационная таблица сезона */}
      {(() => {
        // Приоритет: используем facts из админки, если есть, иначе используем данные из seasonData
        const facts = season?.facts || {};
        const hasFacts = facts && Object.keys(facts).length > 0;
        const hasMetadata = seasonData.metadata && Object.keys(seasonData.metadata).length > 0;
        const hasSeasonData = seasonData.season_number > 0 || all_teams.length > 0 || stages.length > 0 || hostsList.length > 0 || editors.length > 0 || winners.length > 0;
        
        if (!hasFacts && !hasSeasonData) return null;
        
        // Функция для проверки, содержит ли строка HTML
        const containsHTML = (str) => {
          if (typeof str !== 'string') return false;
          return /<[a-z][\s\S]*>/i.test(str);
        };
        
        return (
          <div className="mb-8">
            <Card>
              <CardContent className="pt-6">
                <Table>
                  <TableBody>
                    {hasFacts ? (
                      // Используем данные из facts (редактор в админке)
                      Object.entries(facts)
                        .filter(([key, value]) => {
                          if (!key) return false;
                          const valueStr = String(value || '').trim();
                          return valueStr.length > 0;
                        })
                        .map(([key, value]) => {
                          const valueStr = String(value).trim();
                          
                          return (
                            <TableRow key={key}>
                              <TableCell className="font-medium bg-gray-50 w-[200px]">{key}</TableCell>
                              <TableCell>
                                {containsHTML(valueStr) ? (
                                  <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: valueStr }} />
                                ) : (
                                  valueStr
                                )}
                              </TableCell>
                            </TableRow>
                          );
                        })
                    ) : (
                      // Fallback: используем данные из seasonData (старая логика)
                      <>
                        {seasonData.season_number > 0 && (
                          <TableRow>
                            <TableCell className="font-medium bg-gray-50 w-[200px]">Сезон</TableCell>
                            <TableCell>{seasonData.season_number}</TableCell>
                          </TableRow>
                        )}
                        {all_teams.length > 0 && (
                          <TableRow>
                            <TableCell className="font-medium bg-gray-50">Количество команд</TableCell>
                            <TableCell>{all_teams.length}</TableCell>
                          </TableRow>
                        )}
                        {stages.length > 0 && (
                          <TableRow>
                            <TableCell className="font-medium bg-gray-50">Количество игр</TableCell>
                            <TableCell>
                              {stages.reduce((sum, stage) => sum + (stage.games?.length || 0), 0)}
                            </TableCell>
                          </TableRow>
                        )}
                        {hostsList.length > 0 && (
                          <TableRow>
                            <TableCell className="font-medium bg-gray-50">Ведущий</TableCell>
                            <TableCell>
                              {hostsList.map((host, idx) => (
                                <span key={idx}>
                                  {host}
                                  {idx < hostsList.length - 1 && ', '}
                                </span>
                              ))}
                            </TableCell>
                          </TableRow>
                        )}
                        {editors.length > 0 && (
                          <TableRow>
                            <TableCell className="font-medium bg-gray-50">Редактор</TableCell>
                            <TableCell>
                              {editors.map((editor, idx) => (
                                <span key={idx}>
                                  {editor}
                                  {idx < editors.length - 1 && ', '}
                                </span>
                              ))}
                            </TableCell>
                          </TableRow>
                        )}
                        {winners.length > 0 && (
                          <TableRow>
                            <TableCell className="font-medium bg-gray-50">Чемпионы</TableCell>
                            <TableCell>
                              {winners.map((winner, idx) => {
                                // Поддерживаем как старый формат (строка), так и новый (объект с name и slug)
                                const winnerName = typeof winner === 'string' ? winner : winner.name;
                                const winnerSlug = typeof winner === 'string' ? null : winner.slug;
                                
                                return (
                                  <span key={idx}>
                                    {winnerSlug ? (
                                      <Link to={`/kvn/teams/${winnerSlug}`} className="text-blue-600 hover:underline">
                                        {winnerName}
                                      </Link>
                                    ) : (
                                      winnerName
                                    )}
                                    {idx < winners.length - 1 && ', '}
                                  </span>
                                );
                              })}
                            </TableCell>
                          </TableRow>
                        )}
                      </>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        );
      })()}

      {/* Intro HTML (текст до результатов) - базовая информация, должна быть вверху */}
      {intro_html && (
        <div className="mb-8">
          <Card>
            <CardHeader>
              <CardTitle>О сезоне</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: intro_html }} />
            </CardContent>
          </Card>
        </div>
      )}

      {/* Winners */}
      {winners.length > 0 && (
        <div className="mb-8 bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <Trophy className="h-6 w-6 text-yellow-600" />
            <h2 className="text-2xl font-bold text-gray-900">
              {winners.length === 1 ? 'Победитель сезона' : 'Победители сезона'}
            </h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {winners.map((winner, idx) => {
              // Поддерживаем как старый формат (строка), так и новый (объект с name и slug)
              const winnerSlug = typeof winner === 'string' ? winner : (winner.slug || '');
              
              // Используем полное название из базы данных, если оно загружено
              let winnerName;
              let winnerCity = '';
              
              if (winnerSlug && teamNames[winnerSlug]) {
                // Используем название из базы данных
                winnerName = teamNames[winnerSlug].name;
                winnerCity = teamNames[winnerSlug].city || '';
              } else {
                // Fallback на данные из сезона
                winnerName = typeof winner === 'string' ? winner : winner.name;
                winnerCity = typeof winner === 'object' && winner !== null ? (winner.city || '') : '';
              }
              
              // Формируем полное название с городом, если город есть и его еще нет в названии
              if (winnerCity && !winnerName.includes(`(${winnerCity})`)) {
                winnerName = `${winnerName} (${winnerCity})`;
              }
              
              return (
                <Badge key={idx} variant="default" className="bg-yellow-600 text-white">
                  {winnerSlug ? (
                    <Link to={`/kvn/teams/${winnerSlug}`} className="hover:underline">
                      {winnerName}
                    </Link>
                  ) : (
                    winnerName
                  )}
                </Badge>
              );
            })}
          </div>
        </div>
      )}

      {/* Teams list */}
      {all_teams.length > 0 && (
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Users className="h-6 w-6" />
            Команды-участники
          </h2>
          <div className="flex flex-wrap gap-2">
            {all_teams.map((team, idx) => {
              // Поддерживаем старый формат (строка) и новый (объект)
              const teamSlug = typeof team === 'string' ? team : (team.slug || '');
              
              // Используем полное название из базы данных, если оно загружено
              let teamName;
              let teamCity = '';
              
              if (teamSlug && teamNames[teamSlug]) {
                // Используем название из базы данных
                teamName = teamNames[teamSlug].name;
                teamCity = teamNames[teamSlug].city || '';
              } else {
                // Fallback на данные из сезона
                teamName = typeof team === 'string' ? team : (team.name || team.slug || '');
                teamCity = typeof team === 'object' && team !== null ? (team.city || '') : '';
              }
              
              // Формируем полное название с городом, если город есть и его еще нет в названии
              if (teamCity && !teamName.includes(`(${teamCity})`)) {
                teamName = `${teamName} (${teamCity})`;
              }
              
              return (
                <Badge key={idx} variant="outline" asChild>
                  {teamSlug ? (
                    <Link to={`/kvn/teams/${teamSlug}`}>{teamName}</Link>
                  ) : (
                    <span>{teamName}</span>
                  )}
                </Badge>
              );
            })}
          </div>
        </div>
      )}

      {/* Stages */}
      {stages.length > 0 && (
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-gray-900 mb-6">Результаты</h2>
          {stages.map((stage, idx) => (
            <StageSection key={idx} stage={stage} />
          ))}
        </div>
      )}

      {/* Extra sections (Кубок мэра и другие) */}
      {extra_sections.length > 0 && extra_sections.map((section, idx) => (
        section.title && section.html && (
          <div key={idx} className="mb-8">
            <Card>
              <CardHeader>
                <CardTitle>{section.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: section.html }} />
              </CardContent>
            </Card>
          </div>
        )
      ))}

      {/* Season navigation (оглавление) */}
      <div className="mt-12 pt-8 border-t">
        <h3 className="text-xl font-bold text-gray-900 mb-4">Все сезоны {leagueName}</h3>
        <p className="text-gray-600 mb-4">
          Навигация по сезонам будет добавлена позже
        </p>
      </div>
    </div>
  );
}

