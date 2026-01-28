import { useState, useEffect, useCallback } from 'react';
import { X, Search, Loader2, List } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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

export default function TeamSelector({ 
  value = [], 
  onChange, 
  placeholder = "Выберите команды...",
  allowCustom = false // Если true, позволяет добавлять команды текстом, если не найдены
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedTeams, setSelectedTeams] = useState([]);
  const [showBulkDialog, setShowBulkDialog] = useState(false);
  const [bulkInput, setBulkInput] = useState('');
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkResults, setBulkResults] = useState([]);

  // Load selected teams details
  useEffect(() => {
    const loadSelectedTeams = async () => {
      if (value.length === 0) {
        setSelectedTeams([]);
        return;
      }

      const teams = [];
      for (const teamItem of value) {
        // Поддерживаем как объекты {slug, name, city}, так и строки (slug или name)
        let teamId, teamName, teamSlug, teamCity;
        
        if (typeof teamItem === 'object' && teamItem !== null) {
          teamId = teamItem.slug || teamItem.id || '';
          teamName = teamItem.name || '';
          teamSlug = teamItem.slug || '';
          teamCity = teamItem.city || '';
        } else {
          // Старый формат - строка (slug)
          teamId = teamItem;
          teamSlug = teamItem;
        }

        if (teamId) {
          try {
            const res = await contentApi.getTeam(teamId);
            const teamData = res.data;
            // Извлекаем город из facts
            const cityFromFacts = getCityFromFacts(teamData.facts);
            teams.push({
              id: teamData._id || teamData.id || teamId,
              slug: teamData.slug || teamSlug,
              name: teamData.name || teamData.title || teamName || teamId,
              city: cityFromFacts || teamCity || ''
            });
          } catch (err) {
            // If team not found, use provided data or ID
            teams.push({
              id: teamId,
              slug: teamSlug,
              name: teamName || teamId,
              city: teamCity || ''
            });
          }
        } else if (teamName) {
          // Команда только по имени (не найдена в базе)
          teams.push({
            id: null,
            slug: '',
            name: teamName,
            city: teamCity || ''
          });
        }
      }
      setSelectedTeams(teams);
    };

    loadSelectedTeams();
  }, [value]);

  // Search teams when search term changes
  useEffect(() => {
    if (!search.trim() || search.length < 2) {
      setSearchResults([]);
      return;
    }

    const searchTeams = async () => {
      setLoading(true);
      try {
        const searchTerm = search.trim();
        const res = await contentApi.listTeams({ 
          search: searchTerm,
          limit: 20
          // Не фильтруем по team_type, так как не у всех команд он указан
        });
        // Добавляем город из facts для каждой команды
        let teamsWithCity = (res.data.items || []).map(team => ({
          ...team,
          city: getCityFromFacts(team.facts)
        }));
        
        // Если поиск не дал результатов, пробуем найти по slug напрямую
        if (teamsWithCity.length === 0 && searchTerm.length >= 2) {
          // Нормализуем поисковый запрос (убираем пробелы, приводим к нижнему регистру)
          const normalizedSearch = searchTerm.toLowerCase().replace(/\s+/g, '');
          try {
            // Пробуем получить команду по slug
            const teamBySlug = await contentApi.getTeam(normalizedSearch);
            if (teamBySlug.data) {
              const teamData = teamBySlug.data;
              const cityFromFacts = getCityFromFacts(teamData.facts);
              teamsWithCity = [{
                ...teamData,
                city: cityFromFacts
              }];
            }
          } catch (slugErr) {
            // Игнорируем ошибку, если команда не найдена по slug
          }
        }
        
        setSearchResults(teamsWithCity);
      } catch (err) {
        console.error('Error searching teams:', err);
        setSearchResults([]);
      } finally {
        setLoading(false);
      }
    };

    const timeoutId = setTimeout(searchTeams, 300); // Debounce
    return () => clearTimeout(timeoutId);
  }, [search]);

  // Filter out already selected teams
  const availableResults = searchResults.filter(
    team => {
      const teamSlug = team.slug || team.id;
      return !value.some(v => {
        if (typeof v === 'object') {
          return (v.slug || v.id) === teamSlug;
        }
        return v === teamSlug;
      });
    }
  );

  const addTeam = useCallback(async (team) => {
    if (!team) return;
    
    // Если у команды есть slug, загружаем полную информацию из базы данных
    // чтобы получить актуальное название и город
    const teamSlug = team.slug || team.id;
    
    if (teamSlug) {
      try {
        // Загружаем полную информацию о команде из базы данных
        const res = await contentApi.getTeam(teamSlug);
        const teamData = res.data;
        // Извлекаем город из facts
        const cityFromFacts = getCityFromFacts(teamData.facts);
        // Используем полное название из базы данных
        const teamName = teamData.name || teamData.title || team.name || team.title || '';
        
        const teamValue = {
          slug: teamData.slug || teamSlug,
          name: teamName,
          city: cityFromFacts || ''
        };
        
        // Проверяем, не добавлена ли уже команда
        const isAlreadyAdded = value.some(v => {
          if (typeof v === 'object') {
            return (v.slug || v.id) === teamValue.slug;
          }
          return v === teamValue.slug;
        });

        if (!isAlreadyAdded) {
          onChange([...value, teamValue]);
        }
      } catch (err) {
        // Если команда не найдена в базе, используем данные из поиска
        const teamCity = team.city || '';
        const teamValue = {
          slug: teamSlug,
          name: team.name || team.title || '',
          city: teamCity
        };
        
        const isAlreadyAdded = value.some(v => {
          if (typeof v === 'object') {
            return (v.slug || v.id) === teamValue.slug;
          }
          return v === teamValue.slug;
        });

        if (!isAlreadyAdded) {
          onChange([...value, teamValue]);
        }
      }
    } else {
      // Команда без slug (текстовая)
      const teamValue = team.name || team.title || '';
      const isAlreadyAdded = value.some(v => {
        if (typeof v === 'string') {
          return v === teamValue;
        }
        return false;
      });

      if (!isAlreadyAdded) {
        onChange([...value, teamValue]);
      }
    }
    
    setSearch('');
    setOpen(false);
  }, [value, onChange]);

  const addCustomTeam = useCallback(() => {
    if (!search.trim() || search.length < 2) return;
    
    // Добавляем команду как объект с именем, но без slug
    const customTeam = { slug: '', name: search.trim(), city: '' };
    onChange([...value, customTeam]);
    setSearch('');
    setOpen(false);
  }, [search, value, onChange]);

  const removeTeam = useCallback((index) => {
    onChange(value.filter((_, i) => i !== index));
  }, [value, onChange]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (availableResults.length > 0) {
        addTeam(availableResults[0]);
      } else if (allowCustom && search.trim().length >= 2) {
        addCustomTeam();
      }
    }
  };

  // Парсинг строки формата "Название (Город)" или просто "Название"
  const parseTeamLine = (line) => {
    const trimmed = line.trim();
    if (!trimmed) return null;

    // Пытаемся найти паттерн "Название (Город)"
    const match = trimmed.match(/^(.+?)\s*\(([^)]+)\)\s*$/);
    if (match) {
      return {
        name: match[1].trim(),
        city: match[2].trim()
      };
    }

    // Если нет скобок, возвращаем только название
    return {
      name: trimmed,
      city: ''
    };
  };

  // Поиск команды в БД по названию и городу
  const findTeamInDB = async (teamName, city) => {
    try {
      // Сначала ищем по названию
      const res = await contentApi.listTeams({ 
        search: teamName,
        limit: 50
      });

      const teams = (res.data.items || []).map(team => ({
        ...team,
        city: getCityFromFacts(team.facts)
      }));

      // Нормализуем названия для сравнения
      const normalizedName = teamName.toLowerCase().trim();
      const normalizedCity = city.toLowerCase().trim();

      // Ищем точное совпадение по названию
      let match = teams.find(team => {
        const teamNameNorm = (team.name || team.title || '').toLowerCase().trim();
        return teamNameNorm === normalizedName;
      });

      // Если есть город, проверяем его тоже
      if (match && normalizedCity) {
        const teamCityNorm = (match.city || '').toLowerCase().trim();
        if (teamCityNorm && !teamCityNorm.includes(normalizedCity) && !normalizedCity.includes(teamCityNorm)) {
          // Город не совпадает, ищем дальше
          match = teams.find(team => {
            const teamNameNorm = (team.name || team.title || '').toLowerCase().trim();
            const teamCityNorm = (team.city || '').toLowerCase().trim();
            return teamNameNorm === normalizedName && 
                   teamCityNorm && 
                   (teamCityNorm.includes(normalizedCity) || normalizedCity.includes(teamCityNorm));
          });
        }
      }

      // Если не нашли точное совпадение, ищем частичное
      if (!match) {
        match = teams.find(team => {
          const teamNameNorm = (team.name || team.title || '').toLowerCase().trim();
          return teamNameNorm.includes(normalizedName) || normalizedName.includes(teamNameNorm);
        });
      }

      if (match) {
        return {
          id: match._id || match.id,
          slug: match.slug || match.id,
          name: match.name || match.title || '',
          city: match.city || ''
        };
      }

      return null;
    } catch (err) {
      console.error('Error finding team:', err);
      return null;
    }
  };

  // Обработка массовой вставки
  const handleBulkInsert = async () => {
    if (!bulkInput.trim()) return;

    setBulkLoading(true);
    setBulkResults([]);

    const lines = bulkInput.split('\n').filter(line => line.trim());
    const results = [];

    for (const line of lines) {
      const parsed = parseTeamLine(line);
      if (!parsed) continue;

      const found = await findTeamInDB(parsed.name, parsed.city);
      results.push({
        original: line,
        parsed,
        found,
        alreadyAdded: found ? value.some(v => {
          if (typeof v === 'object') {
            return (v.slug || v.id) === found.slug;
          }
          return v === found.slug;
        }) : false
      });
    }

    setBulkResults(results);
    setBulkLoading(false);
  };

  // Применение результатов массовой вставки
  const applyBulkInsert = () => {
    const newTeams = bulkResults
      .filter(r => r.found && !r.alreadyAdded)
      .map(r => ({
        slug: r.found.slug,
        name: r.found.name,
        city: r.found.city
      }));

    if (newTeams.length > 0) {
      onChange([...value, ...newTeams]);
    }

    setShowBulkDialog(false);
    setBulkInput('');
    setBulkResults([]);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className="flex-1">
        <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between font-normal"
          >
            <span className="text-muted-foreground">{placeholder}</span>
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
                    <CommandEmpty>Введите название команды для поиска</CommandEmpty>
                  )}
                  {search.trim() && search.length < 2 && (
                    <CommandEmpty>Введите минимум 2 символа</CommandEmpty>
                  )}
                  {search.trim() && search.length >= 2 && availableResults.length === 0 && !loading && (
                    <>
                      <CommandEmpty>Команда не найдена</CommandEmpty>
                      {allowCustom && (
                        <CommandGroup>
                          <CommandItem
                            onSelect={addCustomTeam}
                            className="cursor-pointer text-muted-foreground"
                          >
                            Добавить "{search.trim()}" как текст
                          </CommandItem>
                        </CommandGroup>
                      )}
                    </>
                  )}
                  
                  {availableResults.length > 0 && (
                    <CommandGroup heading="Результаты поиска">
                      {availableResults.map((team) => (
                        <CommandItem
                          key={team.id || team.slug}
                          onSelect={() => addTeam(team)}
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
      </div>
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => {
            setBulkInput('');
            setBulkResults([]);
            setShowBulkDialog(true);
          }}
          title="Вставить список команд"
        >
          <List className="h-4 w-4" />
        </Button>
      </div>

      {/* Диалог массовой вставки */}
      <Dialog open={showBulkDialog} onOpenChange={setShowBulkDialog}>
        <DialogContent className="max-w-3xl max-h-[90vh]">
          <DialogHeader>
            <DialogTitle>Вставить список команд</DialogTitle>
            <DialogDescription>
              Вставьте список команд, каждая строка в формате "Название (Город)" или просто "Название".
              Команды, найденные в базе данных, будут автоматически добавлены в сезон.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Список команд</Label>
              <Textarea
                value={bulkInput}
                onChange={(e) => setBulkInput(e.target.value)}
                placeholder={`Сега Мега Драйв 16 бит (Москва)\nСборная ДГТУ (Ростов-на-Дону)\nМалина (Красноярск)`}
                rows={10}
                className="font-mono text-sm"
              />
            </div>
            <div className="flex justify-end">
              <Button
                onClick={handleBulkInsert}
                disabled={!bulkInput.trim() || bulkLoading}
              >
                {bulkLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Поиск...
                  </>
                ) : (
                  'Найти команды'
                )}
              </Button>
            </div>
            {bulkResults.length > 0 && (
              <div className="space-y-2">
                <Label className="text-sm">Результаты сопоставления:</Label>
                <div className="border rounded p-2 bg-muted max-h-60 overflow-auto">
                  <table className="text-xs w-full">
                    <thead>
                      <tr>
                        <th className="text-left pr-4">Исходная строка</th>
                        <th className="text-left pr-4">Статус</th>
                        <th className="text-left">Найдено</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bulkResults.map((result, idx) => (
                        <tr key={idx} className="border-t">
                          <td className="pr-4 py-1">{result.original}</td>
                          <td className="pr-4 py-1">
                            {result.found ? (
                              result.alreadyAdded ? (
                                <span className="text-muted-foreground">Уже добавлена</span>
                              ) : (
                                <span className="text-green-600">✓ Найдена</span>
                              )
                            ) : (
                              <span className="text-orange-600">✗ Не найдена</span>
                            )}
                          </td>
                          <td className="py-1">
                            {result.found ? (
                              <span>
                                {result.found.name}
                                {result.found.city && <span className="text-muted-foreground"> ({result.found.city})</span>}
                              </span>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="text-sm text-muted-foreground">
                  Найдено: {bulkResults.filter(r => r.found && !r.alreadyAdded).length} из {bulkResults.length}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowBulkDialog(false)}>
              Отмена
            </Button>
            <Button
              onClick={applyBulkInsert}
              disabled={!bulkResults.some(r => r.found && !r.alreadyAdded)}
            >
              Добавить найденные команды ({bulkResults.filter(r => r.found && !r.alreadyAdded).length})
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Selected teams */}
      {selectedTeams.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selectedTeams.map((team, index) => (
            <Badge key={index} variant="secondary" className="pr-1">
              {team.name}
              {team.city && <span className="ml-1 text-xs opacity-75">({team.city})</span>}
              {!team.slug && <span className="ml-1 text-xs opacity-50">[текст]</span>}
              <button
                type="button"
                onClick={() => removeTeam(index)}
                className="ml-1 hover:text-destructive"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
