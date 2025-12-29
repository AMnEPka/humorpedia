import { useState, useEffect, useCallback } from 'react';
import { X, Search, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
import { cn } from '@/lib/utils';

export default function PersonSelector({ value = [], onChange, placeholder = "Выберите людей..." }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedPeople, setSelectedPeople] = useState([]);

  // Load selected people details
  useEffect(() => {
    const loadSelectedPeople = async () => {
      if (value.length === 0) {
        setSelectedPeople([]);
        return;
      }

      const people = [];
      for (const personId of value) {
        try {
          const res = await contentApi.getPerson(personId);
          people.push({
            id: res.data._id || res.data.id,
            name: res.data.full_name || res.data.title || personId
          });
        } catch (err) {
          // If person not found, just use ID
          people.push({ id: personId, name: personId });
        }
      }
      setSelectedPeople(people);
    };

    loadSelectedPeople();
  }, [value]);

  // Search people when search term changes
  useEffect(() => {
    if (!search.trim() || search.length < 2) {
      setSearchResults([]);
      return;
    }

    const searchPeople = async () => {
      setLoading(true);
      try {
        const res = await contentApi.searchPeople(search, 10);
        setSearchResults(res.data || []);
      } catch (err) {
        console.error('Error searching people:', err);
        setSearchResults([]);
      } finally {
        setLoading(false);
      }
    };

    const timeoutId = setTimeout(searchPeople, 300); // Debounce
    return () => clearTimeout(timeoutId);
  }, [search]);

  // Filter out already selected people
  const availableResults = searchResults.filter(
    person => !value.includes(person.id)
  );

  const addPerson = useCallback((person) => {
    if (person && !value.includes(person.id)) {
      onChange([...value, person.id]);
    }
    setSearch('');
    setOpen(false);
  }, [value, onChange]);

  const removePerson = useCallback((personId) => {
    onChange(value.filter(id => id !== personId));
  }, [value, onChange]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && availableResults.length > 0) {
      e.preventDefault();
      addPerson(availableResults[0]);
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
            <span className="text-muted-foreground">{placeholder}</span>
            <Search className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[400px] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput 
              placeholder="Поиск по имени..." 
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
                    <CommandEmpty>Введите имя для поиска</CommandEmpty>
                  )}
                  {search.trim() && search.length < 2 && (
                    <CommandEmpty>Введите минимум 2 символа</CommandEmpty>
                  )}
                  {search.trim() && search.length >= 2 && availableResults.length === 0 && !loading && (
                    <CommandEmpty>Люди не найдены</CommandEmpty>
                  )}
                  
                  {availableResults.length > 0 && (
                    <CommandGroup heading="Результаты поиска">
                      {availableResults.map((person) => (
                        <CommandItem
                          key={person.id}
                          onSelect={() => addPerson(person)}
                          className="cursor-pointer"
                        >
                          {person.name}
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

      {/* Selected people */}
      {selectedPeople.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selectedPeople.map((person) => (
            <Badge key={person.id} variant="secondary" className="pr-1">
              {person.name}
              <button
                type="button"
                onClick={() => removePerson(person.id)}
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

