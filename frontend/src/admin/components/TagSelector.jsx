import { useState, useEffect, useRef, useCallback } from 'react';
import { X, Check, ChevronsUpDown, Plus } from 'lucide-react';
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
import { tagsApi } from '../utils/api';
import { cn } from '@/lib/utils';

export default function TagSelector({ value = [], onChange, placeholder = "Добавить тег..." }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [allTags, setAllTags] = useState([]);
  const [loading, setLoading] = useState(false);

  // Load all tags on mount
  useEffect(() => {
    const fetchTags = async () => {
      setLoading(true);
      try {
        const res = await tagsApi.list({ limit: 500 });
        setAllTags(res.data.items?.map(t => t.name) || []);
      } catch (err) {
        console.error('Error loading tags:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchTags();
  }, []);

  // Filter tags based on search
  const filteredTags = allTags.filter(tag => 
    tag.toLowerCase().includes(search.toLowerCase()) && 
    !value.includes(tag)
  );

  // Check if search term is a new tag (not in allTags)
  const isNewTag = search.trim() && 
    !allTags.some(t => t.toLowerCase() === search.toLowerCase()) &&
    !value.some(t => t.toLowerCase() === search.toLowerCase());

  const addTag = useCallback((tag) => {
    if (tag && !value.includes(tag)) {
      onChange([...value, tag]);
    }
    setSearch('');
    setOpen(false);
  }, [value, onChange]);

  const removeTag = useCallback((tagToRemove) => {
    onChange(value.filter(t => t !== tagToRemove));
  }, [value, onChange]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && search.trim()) {
      e.preventDefault();
      addTag(search.trim());
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
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[300px] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput 
              placeholder="Поиск тега..." 
              value={search}
              onValueChange={setSearch}
              onKeyDown={handleKeyDown}
            />
            <CommandList>
              {loading ? (
                <div className="p-4 text-sm text-center text-muted-foreground">
                  Загрузка...
                </div>
              ) : (
                <>
                  {filteredTags.length === 0 && !isNewTag && (
                    <CommandEmpty>Теги не найдены</CommandEmpty>
                  )}
                  
                  {isNewTag && (
                    <CommandGroup heading="Создать новый тег">
                      <CommandItem
                        onSelect={() => addTag(search.trim())}
                        className="cursor-pointer"
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        Добавить "{search.trim()}"
                      </CommandItem>
                    </CommandGroup>
                  )}
                  
                  {filteredTags.length > 0 && (
                    <CommandGroup heading="Существующие теги">
                      {filteredTags.slice(0, 20).map((tag) => (
                        <CommandItem
                          key={tag}
                          onSelect={() => addTag(tag)}
                          className="cursor-pointer"
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              value.includes(tag) ? "opacity-100" : "opacity-0"
                            )}
                          />
                          {tag}
                        </CommandItem>
                      ))}
                      {filteredTags.length > 20 && (
                        <div className="p-2 text-xs text-center text-muted-foreground">
                          Ещё {filteredTags.length - 20} тегов...
                        </div>
                      )}
                    </CommandGroup>
                  )}
                </>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {/* Selected tags */}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((tag) => (
            <Badge key={tag} variant="secondary" className="pr-1">
              {tag}
              <button
                type="button"
                onClick={() => removeTag(tag)}
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
