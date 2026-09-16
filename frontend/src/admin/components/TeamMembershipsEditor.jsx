import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Plus, RefreshCw, Save, Trash2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { contentApi, getErrorMessage } from '../utils/api';
import { useAuth } from '../hooks/useAuth';
import PersonSelector from './PersonSelector';

const emptyRow = { person_id: null, person_name: '', roles: [], from_year: null, to_year: null, status: 'current', note: '' };

const toPayload = (teamId, row) => ({
  team_id: teamId,
  person_id: row.person_id || null,
  person_name: row.person_name || '',
  person_slug: row.person_slug || null,
  roles: row.roles || [],
  from_year: row.from_year ? Number(row.from_year) : null,
  to_year: row.to_year ? Number(row.to_year) : null,
  status: row.status || 'current',
  season_ids: row.season_ids || [],
  note: row.note || '',
  order: row.order || 0,
});

// Состав команды: записи «человек — роль — годы». Импортированные из текста записи
// при правке становятся ручными и больше не перезаписываются разбором текста.
export default function TeamMembershipsEditor({ teamId }) {
  const { isAdmin } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [newRow, setNewRow] = useState(emptyRow);

  const load = useCallback(async () => {
    try {
      const res = await contentApi.getTeamMembers(teamId);
      setData(res.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось загрузить состав'));
    }
  }, [teamId]);

  useEffect(() => { load(); }, [load]);

  const run = async (action) => {
    setBusy(true);
    setError('');
    try {
      await action();
      await load();
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось сохранить'));
    } finally {
      setBusy(false);
    }
  };

  if (!data) {
    return error
      ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
      : <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }

  const rows = [...data.current, ...data.former];
  const incomplete = (data.roster_blocks || []).filter(b => b.count > 0 && !b.complete);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>Состав команды ({rows.length})</CardTitle>
            <CardDescription>
              Записи из блока «Состав команды» разбираются автоматически при сохранении модулей.
              Люди без страницы связываются сами, когда страница появится (по slug старого сайта или имени).
            </CardDescription>
          </div>
          {isAdmin && (
            <Button variant="outline" size="sm" disabled={busy} onClick={() => run(() => contentApi.importTeamRoster(teamId))}>
              <RefreshCw className="h-4 w-4 mr-2" /> Разобрать текст заново
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-3">
          {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
          {incomplete.length > 0 && (
            <Alert>
              <AlertDescription>
                Текст состава разобран не полностью — на сайте показывается исходный текст.
                Проверьте записи ниже и при необходимости поправьте текст в модуле.
              </AlertDescription>
            </Alert>
          )}
          {rows.length === 0 && <p className="text-sm text-gray-500">Записей нет.</p>}
          {rows.map(row => (
            <MembershipRow
              key={row._id}
              row={row}
              busy={busy}
              onSave={(value) => run(() => contentApi.updateMembership(row._id, toPayload(teamId, value)))}
              onDelete={() => run(() => contentApi.deleteMembership(row._id))}
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Добавить участника</CardTitle></CardHeader>
        <CardContent>
          <RowFields value={newRow} onChange={setNewRow} />
          <Button
            className="mt-3"
            disabled={busy || (!newRow.person_id && !newRow.person_name.trim())}
            onClick={() => run(async () => {
              await contentApi.createMembership(toPayload(teamId, newRow));
              setNewRow(emptyRow);
            })}
          >
            <Plus className="h-4 w-4 mr-2" /> Добавить
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function MembershipRow({ row, busy, onSave, onDelete }) {
  const [value, setValue] = useState(row);
  useEffect(() => setValue(row), [row]);
  const dirty = JSON.stringify(toPayload('', value)) !== JSON.stringify(toPayload('', row));

  return (
    <div className="border rounded-lg p-3 space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {row.person ? (
          <Link to={`/people/${row.person.slug}`} target="_blank" className="font-medium text-blue-700 hover:underline">
            {row.person.name}
          </Link>
        ) : (
          <span className="font-medium">{row.person_name}</span>
        )}
        <Badge variant={row.source === 'manual' ? 'default' : 'secondary'}>
          {row.source === 'manual' ? 'вручную' : 'из текста'}
        </Badge>
        {!row.person_id && <Badge variant="outline">нет страницы человека</Badge>}
        {row.person_slug && !row.person_id && <span className="text-xs text-gray-500">slug: {row.person_slug}</span>}
      </div>
      <RowFields value={value} onChange={setValue} />
      <div className="flex gap-2">
        <Button size="sm" disabled={busy || !dirty} onClick={() => onSave(value)}>
          <Save className="h-4 w-4 mr-1" /> Сохранить
        </Button>
        <Button size="sm" variant="ghost" className="text-red-600" disabled={busy} onClick={onDelete}>
          <Trash2 className="h-4 w-4 mr-1" /> Удалить
        </Button>
      </div>
    </div>
  );
}

function RowFields({ value, onChange }) {
  const set = (patch) => onChange({ ...value, ...patch });
  return (
    <div className="grid md:grid-cols-12 gap-2 items-start">
      <div className="md:col-span-4 space-y-1">
        <PersonSelector
          value={value.person_id ? [value.person_id] : []}
          onChange={(ids) => set({ person_id: ids.length ? ids[ids.length - 1] : null })}
          placeholder="Страница человека…"
        />
        {!value.person_id && (
          <Input placeholder="Имя (если страницы нет)" value={value.person_name || ''} onChange={e => set({ person_name: e.target.value })} />
        )}
      </div>
      <Input
        className="md:col-span-3"
        placeholder="Роли через запятую"
        value={(value.roles || []).join(', ')}
        onChange={e => set({ roles: e.target.value.split(',').map(r => r.trim()).filter(Boolean) })}
      />
      <Input className="md:col-span-1" type="number" placeholder="с" value={value.from_year || ''} onChange={e => set({ from_year: e.target.value })} />
      <Input className="md:col-span-1" type="number" placeholder="по" value={value.to_year || ''} onChange={e => set({ to_year: e.target.value })} />
      <select
        className="md:col-span-2 h-10 rounded-md border border-input bg-background px-2 text-sm"
        value={value.status || 'current'}
        onChange={e => set({ status: e.target.value })}
      >
        <option value="current">в составе</option>
        <option value="former">бывший</option>
      </select>
      <Input className="md:col-span-12" placeholder="Примечание" value={value.note || ''} onChange={e => set({ note: e.target.value })} />
    </div>
  );
}
