import { useState, useEffect, useMemo } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Loader2, ChevronRight, Users, Filter, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import MultiSelectWithSearch from '../components/MultiSelectWithSearch';
import publicApi from '../utils/api';

export default function JuryStatsPage() {
  const location = useLocation();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Filter states - теперь множественный выбор
  const [selectedYears, setSelectedYears] = useState([]);
  const [selectedTeams, setSelectedTeams] = useState([]);
  const [selectedJury, setSelectedJury] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Team names mapping (slug -> name)
  const [teamNames, setTeamNames] = useState({});
  // Jury cards data (photo and text for each jury member)
  const [juryCards, setJuryCards] = useState({});

  useEffect(() => {
    const fetchStats = async () => {
      setLoading(true);
      setError('');
      try {
        // Load jury statistics
        const statsRes = await publicApi.getKvnJuryStats({
          league_slug: 'vl-kvn',
          min_year: 1987,
          max_year: 2015
        });
        setStats(statsRes.data);
        // Use team_names from API response
        if (statsRes.data.team_names) {
          setTeamNames(statsRes.data.team_names);
        }

        // Load page data to get jury cards
        try {
          const pageRes = await publicApi.getKvnByPath('kvn/vl-kvn/vl-jury');
          if (pageRes.data.jury_cards) {
            setJuryCards(pageRes.data.jury_cards);
          }
        } catch (pageErr) {
          console.warn('Could not load jury cards:', pageErr);
          // Not critical, continue without cards
        }
      } catch (err) {
        console.error('Error fetching jury stats:', err);
        setError('Не удалось загрузить статистику жюри');
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  // Filtered data with recalculated game counts based on all filters
  const filteredJuryMembers = useMemo(() => {
    if (!stats) return [];
    
    let filtered = stats.jury_members.map(jury => {
      // Filter games based on all active filters
      let filteredGames = jury.games;
      
      // Filter by years
      if (selectedYears.length > 0) {
        filteredGames = filteredGames.filter(game => 
          selectedYears.includes(String(game.year))
        );
      }
      
      // Filter by teams
      if (selectedTeams.length > 0) {
        filteredGames = filteredGames.filter(game =>
          selectedTeams.some(team => game.teams.includes(team))
        );
      }
      
      // Return jury member with filtered games and recalculated count
      return {
        ...jury,
        filteredGames,
        filteredGamesCount: filteredGames.length
      };
    });
    
    // Filter by jury members (multiple)
    if (selectedJury.length > 0) {
      filtered = filtered.filter(jury => selectedJury.includes(jury.name));
    }
    
    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(jury => 
        jury.name.toLowerCase().includes(query)
      );
    }
    
    // Only return jury members that have at least one game matching all filters
    return filtered.filter(jury => jury.filteredGamesCount > 0);
  }, [stats, selectedYears, selectedTeams, selectedJury, searchQuery]);

  // Get teams for selected jury members (with counts, filtered by years and teams)
  const teamsForSelectedJury = useMemo(() => {
    if (selectedJury.length === 0 || !stats) return [];
    const allTeams = new Set();
    selectedJury.forEach(juryName => {
      const jury = stats.jury_members.find(j => j.name === juryName);
      if (jury) {
        // Use filteredGames if available (from filteredJuryMembers), otherwise use all games
        const juryData = filteredJuryMembers.find(j => j.name === juryName);
        const gamesToUse = juryData?.filteredGames || jury.games;
        
        gamesToUse.forEach(game => {
          game.teams.forEach(team => {
            // If teams filter is active, only include selected teams
            if (selectedTeams.length === 0 || selectedTeams.includes(team)) {
              allTeams.add(team);
            }
          });
        });
      }
    });
    return Array.from(allTeams);
  }, [selectedJury, stats, filteredJuryMembers, selectedTeams]);

  // Get years for selected jury members (filtered by selected years and teams)
  const yearsForSelectedJury = useMemo(() => {
    if (selectedJury.length === 0 || !stats) return [];
    
    const yearCounts = {};
    selectedJury.forEach(juryName => {
      const jury = stats.jury_members.find(j => j.name === juryName);
      if (jury) {
        // Use filteredGames if available (from filteredJuryMembers), otherwise use all games
        const juryData = filteredJuryMembers.find(j => j.name === juryName);
        const gamesToUse = juryData?.filteredGames || jury.games;
        
        gamesToUse.forEach(game => {
          yearCounts[game.year] = (yearCounts[game.year] || 0) + 1;
        });
      }
    });
    
    return Object.entries(yearCounts)
      .map(([year, count]) => ({ year: parseInt(year), count }))
      .sort((a, b) => b.year - a.year);
  }, [selectedJury, stats, filteredJuryMembers]);

  // Available teams for selection (filtered by selected years)
  const availableTeams = useMemo(() => {
    if (!stats) return [];
    
    let teams = stats.all_teams;
    
    // Filter by selected years
    if (selectedYears.length > 0) {
      const teamsInYears = new Set();
      stats.jury_members.forEach(jury => {
        jury.games.forEach(game => {
          if (selectedYears.includes(String(game.year))) {
            game.teams.forEach(team => teamsInYears.add(team));
          }
        });
      });
      teams = teams.filter(team => teamsInYears.has(team));
    }
    
    return teams;
  }, [stats, selectedYears]);

  // Available jury members for selection (filtered by selected years)
  const availableJury = useMemo(() => {
    if (!stats) return [];
    
    let jury = stats.jury_members;
    
    // Filter by selected years
    if (selectedYears.length > 0) {
      jury = jury.filter(j => {
        return selectedYears.some(year => j.years.includes(parseInt(year)));
      });
    }
    
    return jury;
  }, [stats, selectedYears]);

  // Remove selected teams/jury that don't match selected years
  useEffect(() => {
    if (!stats || selectedYears.length === 0) return;
    
    // Filter teams
    if (selectedTeams.length > 0) {
      const validTeams = selectedTeams.filter(team => availableTeams.includes(team));
      if (validTeams.length !== selectedTeams.length) {
        setSelectedTeams(validTeams);
      }
    }
    
    // Filter jury
    if (selectedJury.length > 0) {
      const validJury = selectedJury.filter(juryName => {
        return availableJury.some(j => j.name === juryName);
      });
      if (validJury.length !== selectedJury.length) {
        setSelectedJury(validJury);
      }
    }
  }, [selectedYears, stats, availableTeams, availableJury]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
        <p className="text-gray-500 mb-4">{error || 'Статистика не найдена'}</p>
        <Button asChild>
          <Link to="/">Вернуться на главную</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumbs */}
      <nav className="mb-6">
        <ol className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
          <li>
            <Link to="/" className="hover:text-blue-600">
              Главная
            </Link>
          </li>
          <li className="flex items-center gap-2">
            <ChevronRight className="h-4 w-4" />
            <Link to="/kvn" className="hover:text-blue-600">
              КВН
            </Link>
          </li>
          <li className="flex items-center gap-2">
            <ChevronRight className="h-4 w-4" />
            <Link to="/kvn/vl-kvn" className="hover:text-blue-600">
              Высшая лига
            </Link>
          </li>
          <li className="flex items-center gap-2">
            <ChevronRight className="h-4 w-4" />
            <span className="text-gray-900">Статистика жюри</span>
          </li>
        </ol>
      </nav>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-2">
          Статистика жюри Высшей лиги КВН
        </h1>
        <p className="text-lg text-gray-600">
          Сезоны 1987-2015 • Всего игр: {stats.total_games} • Членов жюри: {stats.jury_members.length}
        </p>
      </div>

      <Tabs defaultValue="cards" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="cards">Карточки жюри</TabsTrigger>
          <TabsTrigger value="filters">Фильтры и анализ</TabsTrigger>
        </TabsList>

        {/* Tab 1: Jury Cards */}
        <TabsContent value="cards" className="mt-6">
          <div className="mb-6">
            <div className="flex gap-4 items-center">
              <Input
                placeholder="Поиск по имени..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="max-w-sm"
              />
              {(selectedYears.length > 0 || selectedTeams.length > 0 || selectedJury.length > 0 || searchQuery) && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setSelectedYears([]);
                    setSelectedTeams([]);
                    setSelectedJury([]);
                    setSearchQuery('');
                  }}
                >
                  <X className="h-4 w-4 mr-2" />
                  Сбросить фильтры
                </Button>
              )}
            </div>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredJuryMembers
              .sort((a, b) => b.games_count - a.games_count)
              .map((jury) => (
                <Card key={jury.name} className="hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-lg">{jury.name}</CardTitle>
                      <Badge variant="secondary">{jury.games_count}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 text-sm text-gray-600">
                      <div>
                        <span className="font-medium">Игр в жюри:</span> {jury.games_count}
                      </div>
                      <div>
                        <span className="font-medium">Годы:</span> {jury.years.join(', ')}
                      </div>
                      <div>
                        <span className="font-medium">Команд судил:</span> {jury.teams.length}
                      </div>
                    </div>
                    {/* Photo and text from jury_cards */}
                    {juryCards[jury.name] && (
                      <div className="mt-4 pt-4 border-t space-y-3">
                        {juryCards[jury.name].photo && (
                          <div className="w-full">
                            <img
                              src={juryCards[jury.name].photo.url || juryCards[jury.name].photo}
                              alt={juryCards[jury.name].photo.alt || jury.name}
                              className="w-full h-auto rounded-lg object-cover"
                            />
                          </div>
                        )}
                        {juryCards[jury.name].text && (
                          <div className="text-sm text-gray-700 whitespace-pre-line">
                            {juryCards[jury.name].text}
                          </div>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
          </div>

          {filteredJuryMembers.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>Не найдено членов жюри по заданным фильтрам</p>
            </div>
          )}
        </TabsContent>

        {/* Tab 2: Filters and Analysis */}
        <TabsContent value="filters" className="mt-6">
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Filter className="h-5 w-5" />
                Фильтры
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-3 gap-4">
                <div>
                  <label className="text-sm font-medium mb-2 block">Год</label>
                  <MultiSelectWithSearch
                    value={selectedYears}
                    onChange={setSelectedYears}
                    options={stats.all_years.map(year => String(year))}
                    placeholder="Выберите годы..."
                    searchPlaceholder="Поиск года..."
                    getOptionLabel={(option) => option}
                    getOptionValue={(option) => option}
                  />
                </div>

                <div>
                  <label className="text-sm font-medium mb-2 block">Команда</label>
                  <MultiSelectWithSearch
                    value={selectedTeams}
                    onChange={setSelectedTeams}
                    options={availableTeams}
                    placeholder="Выберите команды..."
                    searchPlaceholder="Поиск команды..."
                    getOptionLabel={(option) => teamNames[option] || option}
                    getOptionValue={(option) => option}
                    filterOptions={(options, search) => {
                      const query = search.toLowerCase();
                      return options.filter(team => {
                        const teamName = (teamNames[team] || team).toLowerCase();
                        return teamName.includes(query) || team.toLowerCase().includes(query);
                      });
                    }}
                  />
                </div>

                <div>
                  <label className="text-sm font-medium mb-2 block">Член жюри</label>
                  <MultiSelectWithSearch
                    value={selectedJury}
                    onChange={setSelectedJury}
                    options={availableJury}
                    placeholder="Выберите судей..."
                    searchPlaceholder="Поиск судьи..."
                    getOptionLabel={(option) => option.name}
                    getOptionValue={(option) => option.name}
                    filterOptions={(options, search) => {
                      const query = search.toLowerCase();
                      return options.filter(jury => jury.name.toLowerCase().includes(query));
                    }}
                  />
                </div>
              </div>

              <div className="mt-4 flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setSelectedYears([]);
                    setSelectedTeams([]);
                    setSelectedJury([]);
                  }}
                >
                  <X className="h-4 w-4 mr-2" />
                  Сбросить все фильтры
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Results based on filters */}
          <div className="space-y-6">
            {/* Show results when filters are active */}
            {(selectedYears.length > 0 || selectedTeams.length > 0 || selectedJury.length > 0) && (
              <>
                {/* Show jury members matching all filters */}
                {filteredJuryMembers.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>
                        {selectedJury.length > 0 
                          ? `Результаты для ${selectedJury.length === 1 ? selectedJury[0] : `выбранных судей`}`
                          : selectedTeams.length > 0
                          ? `Судьи ${selectedTeams.length === 1 
                              ? `команды "${teamNames[selectedTeams[0]] || selectedTeams[0]}"`
                              : `команд: ${selectedTeams.map(t => teamNames[t] || t).join(', ')}`}`
                          : selectedYears.length > 0
                          ? `Судьи в ${selectedYears.length === 1 ? `${selectedYears[0]} году` : `годах: ${selectedYears.join(', ')}`}`
                          : 'Результаты'}
                        {selectedYears.length > 0 && selectedTeams.length > 0 && ' (с учетом выбранных команд и годов)'}
                        {selectedJury.length > 0 && selectedTeams.length > 0 && ' (с учетом выбранных команд)'}
                        {selectedJury.length > 0 && selectedYears.length > 0 && ' (с учетом выбранных годов)'}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Судья</TableHead>
                            <TableHead className="text-right">Количество игр</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {filteredJuryMembers
                            .sort((a, b) => b.filteredGamesCount - a.filteredGamesCount)
                            .map(jury => (
                              <TableRow key={jury.name}>
                                <TableCell>{jury.name}</TableCell>
                                <TableCell className="text-right">{jury.filteredGamesCount}</TableCell>
                              </TableRow>
                            ))}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>
                )}

                {/* Show teams for selected jury members (with counts if teams are also selected) */}
                {selectedJury.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>
                        Команды, которые судил {selectedJury.length === 1 ? selectedJury[0] : `${selectedJury.length} судей`}
                        {selectedTeams.length > 0 && ' (с учетом выбранных команд)'}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      {selectedTeams.length > 0 ? (
                        // Show table with counts when teams are selected
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Судья → Команда</TableHead>
                              <TableHead className="text-right">Количество игр</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {selectedJury.map(juryName => {
                              const jury = stats.jury_members.find(j => j.name === juryName);
                              if (!jury) return null;
                              
                              // Filter games based on all active filters
                              let filteredGames = jury.games;
                              
                              if (selectedYears.length > 0) {
                                filteredGames = filteredGames.filter(game => 
                                  selectedYears.includes(String(game.year))
                                );
                              }
                              
                              // Count games for each selected team
                              const teamCounts = {};
                              filteredGames.forEach(game => {
                                game.teams.forEach(team => {
                                  if (selectedTeams.includes(team)) {
                                    teamCounts[team] = (teamCounts[team] || 0) + 1;
                                  }
                                });
                              });
                              
                              return Object.entries(teamCounts).map(([team, count]) => (
                                <TableRow key={`${juryName}-${team}`}>
                                  <TableCell>
                                    {juryName} → {teamNames[team] || team}
                                  </TableCell>
                                  <TableCell className="text-right">{count}</TableCell>
                                </TableRow>
                              ));
                            }).flat().filter(Boolean)}
                          </TableBody>
                        </Table>
                      ) : (
                        // Show badges when teams are not selected
                        <div className="flex flex-wrap gap-2">
                          {teamsForSelectedJury.map(team => (
                            <Badge key={team} variant="outline">
                              {teamNames[team] || team}
                            </Badge>
                          ))}
                        </div>
                      )}
                      {teamsForSelectedJury.length === 0 && (
                        <p className="text-gray-500">Нет данных</p>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Show years for selected jury members */}
                {selectedJury.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>
                        Статистика по годам для {selectedJury.length === 1 ? selectedJury[0] : `${selectedJury.length} судей`}
                        {selectedYears.length > 0 && ' (с учетом выбранных годов)'}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Год</TableHead>
                            <TableHead className="text-right">Количество игр</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {yearsForSelectedJury
                            .filter(({ year }) => 
                              selectedYears.length === 0 || selectedYears.includes(String(year))
                            )
                            .map(({ year, count }) => (
                              <TableRow key={year}>
                                <TableCell>{year}</TableCell>
                                <TableCell className="text-right">{count}</TableCell>
                              </TableRow>
                            ))}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>
                )}

                {filteredJuryMembers.length === 0 && (
                  <Card>
                    <CardContent className="py-8 text-center text-gray-500">
                      Нет результатов, соответствующих выбранным фильтрам
                    </CardContent>
                  </Card>
                )}
              </>
            )}

            {/* Default message when no filters */}
            {selectedYears.length === 0 && selectedTeams.length === 0 && selectedJury.length === 0 && (
              <Card>
                <CardContent className="py-12 text-center text-gray-500">
                  <Filter className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Выберите фильтры для анализа статистики</p>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
