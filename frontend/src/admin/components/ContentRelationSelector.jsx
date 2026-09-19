import { useEffect, useMemo, useState } from 'react';
import { Loader2, Search, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { contentApi } from '../utils/api';

const LABELS = {
  team: { plural: 'команды', search: 'Поиск команды...' },
  show: { plural: 'шоу', search: 'Поиск шоу...' },
};

export default function ContentRelationSelector({ type, value = [], onChange }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState([]);
  const [loading, setLoading] = useState(false);
  const labels = LABELS[type];

  useEffect(() => {
    let active = true;
    Promise.all(value.map(async id => {
      try {
        const response = type === 'team'
          ? await contentApi.getTeam(id)
          : await contentApi.getShow(id);
        const item = response.data;
        return { id, title: item.title || item.name || id };
      } catch {
        return { id, title: id };
      }
    })).then(items => { if (active) setSelected(items); });
    return () => { active = false; };
  }, [type, value]);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return undefined;
    }
    let active = true;
    const timeout = setTimeout(async () => {
      setLoading(true);
      try {
        const response = await contentApi.searchForLinks(query.trim(), type, 15);
        if (active) setResults((response.data.results || []).filter(item => item.type === type));
      } catch {
        if (active) setResults([]);
      } finally {
        if (active) setLoading(false);
      }
    }, 250);
    return () => { active = false; clearTimeout(timeout); };
  }, [query, type]);

  const available = useMemo(
    () => results.filter(item => !value.includes(item.id)),
    [results, value],
  );

  if (!labels) return null;

  return (
    <div className="space-y-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" className="w-full justify-between font-normal">
            <span className="text-muted-foreground">Выберите {labels.plural}...</span>
            <Search className="h-4 w-4 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[420px] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput placeholder={labels.search} value={query} onValueChange={setQuery} />
            <CommandList>
              {loading && <div className="flex justify-center p-4"><Loader2 className="h-4 w-4 animate-spin" /></div>}
              {!loading && query.trim().length < 2 && <CommandEmpty>Введите минимум два символа</CommandEmpty>}
              {!loading && query.trim().length >= 2 && available.length === 0 && <CommandEmpty>Ничего не найдено</CommandEmpty>}
              {available.length > 0 && <CommandGroup heading="Результаты">
                {available.map(item => <CommandItem
                  key={item.id}
                  onSelect={() => {
                    onChange([...value, item.id]);
                    setQuery('');
                    setOpen(false);
                  }}
                >{item.title}</CommandItem>)}
              </CommandGroup>}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      <div className="flex flex-wrap gap-1.5">
        {selected.map(item => <Badge key={item.id} variant="secondary" className="pr-1">
          {item.title}
          <button type="button" className="ml-1 hover:text-destructive" onClick={() => onChange(value.filter(id => id !== item.id))}>
            <X className="h-3 w-3" />
          </button>
        </Badge>)}
      </div>
    </div>
  );
}
