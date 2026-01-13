import { useState, useEffect, useCallback, useMemo } from 'react';
import { X, Search, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { contentApi } from '../utils/api';

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

// Функция для очистки названия команды от города в скобках в конце
// Удаляет только скобки с городом (без кавычек и других специальных символов)
function cleanTeamName(teamName) {
  if (!teamName) return '';
  let cleaned = teamName.trim();
  // Убираем последние скобки в конце строки, но только если они не содержат кавычек
  // Это позволяет сохранить скобки как часть названия (например, "НГУ («В джазе только девушки»)")
  const lastParenMatch = cleaned.match(/\s+\(([^)]*)\)\s*$/);
  if (lastParenMatch) {
    const content = lastParenMatch[1];
    // Если в скобках нет кавычек и других специальных символов - это скорее всего город
    if (!content.includes('«') && !content.includes('»') && !content.includes('"') && !content.includes("'")) {
      cleaned = cleaned.replace(/\s+\([^)]*\)\s*$/, '').trim();
    }
  }
  return cleaned;
}

/**
 * Компонент для выбора команды из уже добавленных команд в игре
 * Также позволяет искать команды в базе и добавлять новые
 */
export default function GameTeamSelector({ 
  value, // Текущая команда: {team_slug, team_name, city} или строка
  onChange, // (team) => void
  existingTeams = [], // Массив уже добавленных команд в игре
  seasonAllTeams = [], // Массив всех команд сезона (из "Команды-участники")
  placeholder = "Выберите команду...",
  allowCustom = true
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState(null);

  // Загружаем информацию о выбранной команде
  useEffect(() => {
    const loadTeam = async () => {
      if (!value) {
        setSelectedTeam(null);
        return;
      }

      let teamId, teamName, teamSlug, teamCity;
      
      if (typeof value === 'object' && value !== null) {
        teamId = value.team_slug || value.slug || value.id || '';
        teamName = value.team_name || value.name || '';
        teamSlug = value.team_slug || value.slug || '';
        teamCity = value.city || '';
      } else {
        teamId = value;
        teamSlug = value;
      }

      if (teamId) {
        try {
          const res = await contentApi.getTeam(teamId);
          const teamData = res.data;
          const cityFromFacts = getCityFromFacts(teamData.facts);
          // Используем название из базы данных напрямую (без очистки, так как оно уже правильное)
          const teamNameFromDb = teamData.name || teamData.title || teamName || teamId;
          setSelectedTeam({
            id: teamData._id || teamData.id || teamId,
            slug: teamData.slug || teamSlug,
            name: teamNameFromDb,
            city: cityFromFacts || teamCity || ''
          });
        } catch (err) {
          // Если команда не найдена, используем предоставленные данные и очищаем от города
          const cleanName = cleanTeamName(teamName || teamId);
          setSelectedTeam({
            id: teamId,
            slug: teamSlug,
            name: cleanName,
            city: teamCity || ''
          });
        }
      } else if (teamName) {
        // Команда только по имени - очищаем от города
        const cleanName = cleanTeamName(teamName);
        setSelectedTeam({
          id: null,
          slug: teamSlug || '',
          name: cleanName,
          city: teamCity || ''
        });
      } else {
        setSelectedTeam(null);
      }
    };

    loadTeam();
  }, [value]);

  // Поиск команд только среди команд сезона
  useEffect(() => {
    if (!search.trim() || search.length < 1) {
      setSearchResults([]);
      return;
    }

    const searchTeams = () => {
      setLoading(true);
      try {
        const searchLower = search.trim().toLowerCase();
        // Нормализуем поисковый запрос (убираем пробелы, приводим к нижнему регистру)
        const normalizedSearch = searchLower.replace(/\s+/g, '');
        
        // Ищем только среди команд сезона
        const filtered = (seasonAllTeams || []).filter(team => {
          const teamName = (typeof team === 'object' && team !== null)
            ? (team.name || team.team_name || '').toLowerCase()
            : String(team).toLowerCase();
          const teamSlug = (typeof team === 'object' && team !== null)
            ? (team.slug || team.team_slug || team.id || '').toLowerCase()
            : String(team).toLowerCase();
          
          // Нормализуем названия команд (убираем пробелы для сравнения)
          const normalizedName = teamName.replace(/\s+/g, '');
          const normalizedSlug = teamSlug.replace(/\s+/g, '');
          
          // Поиск по названию, slug или частичному совпадению (включая нормализованные версии)
          return teamName.includes(searchLower) || 
                 teamSlug.includes(searchLower) ||
                 normalizedName.includes(normalizedSearch) ||
                 normalizedSlug.includes(normalizedSearch) ||
                 teamName.startsWith(searchLower) ||
                 teamSlug.startsWith(searchLower) ||
                 normalizedName.startsWith(normalizedSearch) ||
                 normalizedSlug.startsWith(normalizedSearch);
        });
        
        // Загружаем полную информацию о найденных командах
        const loadTeamDetails = async () => {
          const teamsWithDetails = [];
          for (const team of filtered) {
            let teamSlug, teamName, teamCity;
            
            if (typeof team === 'object' && team !== null) {
              teamSlug = team.slug || team.team_slug || team.id || '';
              teamName = team.name || team.team_name || '';
              teamCity = team.city || '';
            } else {
              teamSlug = team;
              teamName = team;
            }
            
            if (teamSlug) {
              try {
                const res = await contentApi.getTeam(teamSlug);
                const teamData = res.data;
                const cityFromFacts = getCityFromFacts(teamData.facts);
                // Используем название из базы данных напрямую (без очистки)
                const teamNameFromDb = teamData.name || teamData.title || teamName;
                teamsWithDetails.push({
                  id: teamData._id || teamData.id || teamSlug,
                  slug: teamData.slug || teamSlug,
                  name: teamNameFromDb,
                  city: cityFromFacts || teamCity || ''
                });
              } catch (err) {
                // Если команда не найдена в базе, используем данные из сезона и очищаем от города
                const cleanName = cleanTeamName(teamName);
                teamsWithDetails.push({
                  id: teamSlug,
                  slug: teamSlug,
                  name: cleanName,
                  city: teamCity || ''
                });
              }
            } else {
              // Очищаем название от города, если оно есть
              const cleanName = cleanTeamName(teamName);
              teamsWithDetails.push({
                id: null,
                slug: '',
                name: cleanName,
                city: teamCity || ''
              });
            }
          }
          setSearchResults(teamsWithDetails);
          setLoading(false);
        };
        
        loadTeamDetails();
      } catch (err) {
        console.error('Error searching teams:', err);
        setSearchResults([]);
        setLoading(false);
      }
    };

    const timeoutId = setTimeout(searchTeams, 300);
    return () => clearTimeout(timeoutId);
  }, [search, seasonAllTeams]);

  // Фильтруем команды, которые уже добавлены в игру
  const availableResults = searchResults.filter(
    team => {
      const teamSlug = team.slug || team.id;
      return !existingTeams.some(existing => {
        const existingSlug = existing.team_slug || existing.slug || existing.id;
        return existingSlug === teamSlug;
      });
    }
  );

  // Команды из уже добавленных в игру (для быстрого выбора)
  const existingTeamOptions = existingTeams
    .filter(t => t.team_name || t.name)
    .map(t => ({
      id: t.team_slug || t.slug || t.id || null,
      slug: t.team_slug || t.slug || '',
      name: t.team_name || t.name || '',
      city: t.city || ''
    }))
    .filter((t, idx, arr) => 
      // Убираем дубликаты по slug или name
      arr.findIndex(tt => (tt.slug && tt.slug === t.slug) || (!tt.slug && tt.name === t.name)) === idx
    );

  // Все команды сезона (для отображения при пустом поиске)
  const seasonTeamOptions = useMemo(() => {
    return (seasonAllTeams || []).map(team => {
      if (typeof team === 'object' && team !== null) {
        // Если есть slug, загружаем название из базы, иначе очищаем от города
        const teamName = team.name || team.team_name || '';
        return {
          id: team.slug || team.team_slug || team.id || null,
          slug: team.slug || team.team_slug || '',
          name: teamName, // Используем название как есть, очистка будет при сохранении если нужно
          city: team.city || ''
        };
      }
      const cleanName = cleanTeamName(String(team));
      return {
        id: null,
        slug: '',
        name: cleanName,
        city: ''
      };
    }).filter(t => t.name);
  }, [seasonAllTeams]);

  const handleSelectTeam = useCallback((team) => {
    if (!team) return;
    
    // Используем название команды напрямую из базы данных (без очистки)
    // Город хранится отдельно в поле city
    const teamValue = {
      team_slug: team.slug || team.id || '',
      team_name: team.name || team.title || '',
      city: team.city || ''
    };
    
    onChange(teamValue);
    setSearch('');
    setOpen(false);
  }, [onChange]);

  const handleSelectExisting = useCallback((existingTeam) => {
    handleSelectTeam(existingTeam);
  }, [handleSelectTeam]);


  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (availableResults.length > 0) {
        handleSelectTeam(availableResults[0]);
      }
    }
  };

  return (
    <div className="space-y-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between font-normal"
          >
            <span className="text-muted-foreground">
              {selectedTeam ? `${selectedTeam.name}${selectedTeam.city ? ` (${selectedTeam.city})` : ''}` : placeholder}
            </span>
            <Search className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[400px] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput 
              placeholder="Поиск команды..." 
              value={search}
              onValueChange={setSearch}
              onKeyDown={handleKeyDown}
            />
            <CommandList>
              {loading ? (
                <div className="p-4 text-sm text-center text-muted-foreground flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Поиск...
                </div>
              ) : (
                <>
                  {!search.trim() && (
                    <>
                      {existingTeamOptions.length > 0 && (
                        <CommandGroup heading="Уже добавленные команды">
                          {existingTeamOptions.map((team, idx) => (
                            <CommandItem
                              key={`existing-${idx}`}
                              onSelect={() => handleSelectExisting(team)}
                              className="cursor-pointer"
                            >
                              <div className="flex flex-col">
                                <span>{team.name}</span>
                                {team.city && (
                                  <span className="text-xs text-muted-foreground">{team.city}</span>
                                )}
                              </div>
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      )}
                      
                      {seasonTeamOptions.length > 0 && (
                        <CommandGroup heading="Команды сезона">
                          {seasonTeamOptions
                            .filter(team => {
                              // Исключаем уже добавленные команды
                              return !existingTeamOptions.some(existing => 
                                (existing.slug && existing.slug === team.slug) || 
                                (!existing.slug && existing.name === team.name)
                              );
                            })
                            .map((team, idx) => (
                              <CommandItem
                                key={`season-${idx}`}
                                onSelect={() => handleSelectTeam(team)}
                                className="cursor-pointer"
                              >
                                <div className="flex flex-col">
                                  <span>{team.name}</span>
                                  {team.city && (
                                    <span className="text-xs text-muted-foreground">{team.city}</span>
                                  )}
                                </div>
                              </CommandItem>
                            ))}
                        </CommandGroup>
                      )}
                      
                      {existingTeamOptions.length === 0 && seasonTeamOptions.length === 0 && (
                        <CommandEmpty>Нет доступных команд</CommandEmpty>
                      )}
                    </>
                  )}
                  
                  {search.trim() && search.length < 1 && (
                    <CommandEmpty>Введите название команды для поиска</CommandEmpty>
                  )}
                  
                  {search.trim() && search.length >= 1 && availableResults.length === 0 && !loading && (
                    <CommandEmpty>Команда не найдена среди команд сезона</CommandEmpty>
                  )}
                  
                  {availableResults.length > 0 && (
                    <CommandGroup heading="Результаты поиска">
                      {availableResults.map((team) => (
                        <CommandItem
                          key={team.id || team.slug}
                          onSelect={() => handleSelectTeam(team)}
                          className="cursor-pointer"
                        >
                          <div className="flex flex-col">
                            <span>{team.name || team.title}</span>
                            {team.city && (
                              <span className="text-xs text-muted-foreground">{team.city}</span>
                            )}
                          </div>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  )}
                </>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {/* Показываем выбранную команду */}
      {selectedTeam && (
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="pr-1">
            {selectedTeam.name}
            {selectedTeam.city && <span className="ml-1 text-xs opacity-75">({selectedTeam.city})</span>}
            {!selectedTeam.slug && <span className="ml-1 text-xs opacity-50">[текст]</span>}
            <button
              type="button"
              onClick={() => onChange(null)}
              className="ml-1 hover:text-destructive"
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        </div>
      )}
    </div>
  );
}
