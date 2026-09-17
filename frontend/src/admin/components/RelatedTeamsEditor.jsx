import { useEffect, useState } from 'react';
import { X, Loader2 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { contentApi } from '../utils/api';
import { teamSubtitle, teamUrl } from '@/utils/teams';

// Та же команда в других шоу (related_team_ids). Связь двусторонняя — сервер допишет её и второй команде.
export default function RelatedTeamsEditor({ teamId, ids = [], teams = [], onChange }) {
  const [search, setSearch] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const query = search.trim();
    if (query.length < 2) {
      setResults([]);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(() => {
      contentApi.listTeams({ search: query, limit: 10 })
        .then(res => { if (!cancelled) setResults(res.data?.items || []); })
        .catch(() => { if (!cancelled) setResults([]); })
        .finally(() => { if (!cancelled) setLoading(false); });
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [search]);

  const add = (item) => {
    if (item._id === teamId || ids.includes(item._id)) return;
    const card = { id: item._id, name: item.name || item.title, url: teamUrl(item), show: item.show, status: item.status };
    onChange([...ids, item._id], [...teams, card]);
    setSearch('');
    setResults([]);
  };

  const remove = (id) => onChange(ids.filter(i => i !== id), teams.filter(t => t.id !== id));

  return (
    <div className="space-y-3">
      {teams.length === 0 && <p className="text-sm text-muted-foreground">Связей нет</p>}
      {teams.map(t => (
        <div key={t.id} className="flex items-center justify-between gap-2 rounded border p-2">
          <div className="min-w-0">
            <a href={t.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">{t.name}</a>
            <div className="text-xs text-muted-foreground">
              {teamSubtitle(t)}{t.status === 'draft' ? ' · черновик' : ''}
            </div>
          </div>
          <Button type="button" variant="ghost" size="icon" onClick={() => remove(t.id)} title="Убрать связь">
            <X className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <div className="relative">
        <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Найти команду по названию…" />
        {loading && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />}
        {results.length > 0 && (
          <div className="absolute z-20 mt-1 w-full rounded border bg-white shadow">
            {results.filter(r => r._id !== teamId && !ids.includes(r._id)).map(r => (
              <button key={r._id} type="button" onClick={() => add(r)}
                className="block w-full px-3 py-2 text-left text-sm hover:bg-gray-100">
                {r.name || r.title}
                <span className="ml-2 text-xs text-muted-foreground">{teamSubtitle(r)}{r.facts?.['Город'] ? ` · ${r.facts['Город']}` : ''}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
