import { useCallback, useEffect, useState } from 'react';
import { Loader2, Search, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { contentApi } from '../utils/api';

export default function RelatedArticlesSelector({ value = [], onChange, currentId }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all(value.map(async (id) => {
      try {
        const response = await contentApi.getArticle(id);
        return { id, title: response.data.title || id };
      } catch {
        return { id, title: `${id} (не найдено)` };
      }
    })).then((items) => active && setSelected(items));
    return () => { active = false; };
  }, [value]);

  useEffect(() => {
    const text = query.trim();
    if (text.length < 2) {
      setResults([]);
      return undefined;
    }
    const timeout = setTimeout(async () => {
      setLoading(true);
      try {
        const response = await contentApi.listArticles({ search: text, status: 'published', limit: 10 });
        setResults((response.data.items || []).filter((item) => {
          const id = item._id || item.id;
          return id !== currentId && !value.includes(id);
        }));
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(timeout);
  }, [query, value, currentId]);

  const add = useCallback((item) => {
    const id = item._id || item.id;
    if (id && !value.includes(id)) onChange([...value, id]);
    setQuery('');
    setResults([]);
  }, [value, onChange]);

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input value={query} onChange={(event) => setQuery(event.target.value)} className="pl-9" placeholder="Найти опубликованную статью..." />
      </div>
      {loading && <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Поиск...</div>}
      {results.length > 0 && (
        <div className="rounded-md border divide-y">
          {results.map((item) => (
            <button key={item._id || item.id} type="button" onClick={() => add(item)} className="block w-full p-2 text-left text-sm hover:bg-muted">
              {item.title}
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {selected.map((item) => (
          <Badge key={item.id} variant="secondary" className="gap-1">
            {item.title}
            <Button type="button" variant="ghost" size="icon" className="h-5 w-5" onClick={() => onChange(value.filter((id) => id !== item.id))} aria-label={`Удалить ${item.title}`}>
              <X className="h-3 w-3" />
            </Button>
          </Badge>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">Порядок выбранных статей сохраняется; они показываются раньше автоматических рекомендаций.</p>
    </div>
  );
}
