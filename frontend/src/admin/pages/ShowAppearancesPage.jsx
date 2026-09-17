import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { contentApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';

const ranks = { participant: 'Участник', finalist: 'Финалист', winner: 'Победитель' };
const kinds = { '': 'Без состава', team: 'Команда', duet: 'Дуэт', trio: 'Трио', group: 'Группа' };

function ReviewRow({ row, refresh, onError }) {
  const [editing, setEditing] = useState(false);
  const [search, setSearch] = useState('');
  const [people, setPeople] = useState([]);
  const [name, setName] = useState(row.person_name);
  const [slug, setSlug] = useState(row.person_slug || '');
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [achievement, setAchievement] = useState(row.manual_achievement ?? row.achievement);
  const [kind, setKind] = useState(row.manual_group_kind ?? row.group_kind);
  const [group, setGroup] = useState(row.manual_group_name ?? row.group_name);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      if (search.trim().length < 2) { setPeople([]); return; }
      contentApi.searchPeople(search).then(({ data }) => { if (active) setPeople(data); }).catch(() => { if (active) setPeople([]); });
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [search]);
  const run = async (action) => {
    setBusy(true);
    try { await action(); refresh(); }
    catch (e) { onError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Не удалось сохранить изменения'); }
    finally { setBusy(false); }
  };
  const patch = values => run(() => api.patch(`/show-appearances/review/${row._id}`, values));
  return (
    <Card className={row.excluded ? 'opacity-60' : ''}>
      <CardContent className="p-4 space-y-3">
        <div className="flex flex-wrap justify-between gap-3">
          <div>
            <strong>{row.person_name}</strong>{' · '}
            {row.person ? <Link className="text-blue-700 underline" to={`/admin/people/${row.person._id}`}>{row.person.title} ({row.person.status === 'published' ? 'опубликован' : 'черновик / архив'})</Link> : <span className="text-amber-800">Страница не связана</span>}
            <div><Link className="text-blue-700 underline" to={`/shows/${row.source_path}`}>{row.show_path} — {row.source_title}</Link></div>
            <div className="text-sm text-gray-600">{row.evidence}</div>
            <div className="text-sm">{ranks[row.manual_achievement ?? row.achievement]}{group ? ` · ${kinds[kind]} «${group}»` : ''}
              {row.appearances > 0 && ` · Участий: ${row.appearances}`}{row.first_episode != null && ` · Первый выпуск: ${row.first_episode}`}
              {row.preferred && ' · Основной состав закреплён'}</div>
          </div>
          <div className="flex flex-wrap items-start gap-2">
            <Button variant="outline" disabled={busy} onClick={() => setEditing(!editing)}>{editing ? 'Свернуть' : 'Проверить'}</Button>
            {row.person_id && <Button variant="outline" disabled={busy} onClick={() => patch({ preferred: !row.preferred })}>{row.preferred ? 'Выбирать автоматически' : 'Закрепить состав'}</Button>}
            <Button variant="outline" disabled={busy} onClick={() => patch({ excluded: !row.excluded })}>{row.excluded ? 'Включить' : 'Исключить'}</Button>
          </div>
        </div>
        {editing && <div className="space-y-3 border-t pt-3">
          <div className="flex flex-wrap gap-2">
            <label>Статус участия<select aria-label="Статус участия" className="block border rounded p-2" value={achievement} onChange={e => setAchievement(e.target.value)}>{Object.entries(ranks).map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Состав<select aria-label="Вид состава" className="block border rounded p-2" value={kind} onChange={e => { setKind(e.target.value); if (!e.target.value) setGroup(''); }}>{Object.entries(kinds).map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            {kind && <label>Название<Input value={group} onChange={e => setGroup(e.target.value)} /></label>}
            <Button disabled={busy} onClick={() => patch({ achievement, group_kind: kind, group_name: group })}>Сохранить участие</Button>
          </div>
          <label className="block">Связать с существующей страницей<Input placeholder="Имя человека" value={search} onChange={e => setSearch(e.target.value)} /></label>
          <div className="flex flex-wrap gap-2">{people.map(p => <Button key={p.id} variant="outline" disabled={busy} onClick={() => patch({ person_id: p.id })}>{p.name}</Button>)}</div>
          {!row.person_id && <>
            <Button variant="outline" disabled={busy} onClick={() => setCreating(!creating)}>Создать страницу этого человека</Button>
            {creating && <form className="space-y-2" onSubmit={e => { e.preventDefault(); run(async () => {
              const { data } = await api.post(`/show-appearances/review/${row._id}/create-person`, { full_name: name, slug });
              window.location.assign(`/admin/people/${data.id}`);
            }); }}>
              <p className="text-sm">Будет создан только выбранный человек. Страница сохранится черновиком; заполнение и публикация — в редакторе.</p>
              <label className="block">Имя и фамилия<Input required value={name} onChange={e => setName(e.target.value)} /></label>
              <label className="block">Адрес страницы (латиницей)<Input required pattern="[a-z0-9]+(-[a-z0-9]+)*" value={slug} onChange={e => setSlug(e.target.value)} /></label>
              <Button disabled={busy} type="submit">Создать черновик и открыть</Button>
            </form>}
          </>}
        </div>}
      </CardContent>
    </Card>
  );
}

export default function ShowAppearancesPage() {
  const [data, setData] = useState({ items: [], shows: [], total: 0 });
  const [q, setQ] = useState('');
  const [show, setShow] = useState('');
  const [unresolved, setUnresolved] = useState(true);
  const [skip, setSkip] = useState(0);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(() => setVersion(v => v + 1), []);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      api.get('/show-appearances/review', { params: { q, show_id: show || undefined, unresolved, skip } })
        .then(({ data }) => { if (active) setData(data); }).catch(() => { if (active) setError('Не удалось загрузить записи'); });
    }, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [q, show, unresolved, skip, version]);
  return <div className="space-y-5">
    <Link className="text-blue-700 underline" to="/admin/shows">← Шоу</Link>
    <h1 className="text-3xl font-bold">Участники шоу</h1>
    <p>Проверяйте связи и выбирайте людей для добавления. Пересчёт обрабатывает только согласованный список шоу и сохраняет ручные решения.</p>
    {error && <div role="alert" className="text-red-700">{error}</div>}
    <div className="flex flex-wrap items-center gap-3">
      <Input className="max-w-xs" aria-label="Поиск участника" placeholder="Найти участника" value={q} onChange={e => { setQ(e.target.value); setSkip(0); }} />
      <select aria-label="Шоу" className="border rounded p-2" value={show} onChange={e => { setShow(e.target.value); setSkip(0); }}><option value="">Все выбранные шоу</option>{data.shows.map(s => <option key={s._id} value={s._id}>{s.title}</option>)}</select>
      <label><input type="checkbox" checked={unresolved} onChange={e => { setUnresolved(e.target.checked); setSkip(0); }} /> Только без страницы</label>
      <Button disabled={busy} variant="outline" onClick={async () => { setBusy(true); setError(''); try { await api.post('/show-appearances/sync'); refresh(); } catch { setError('Не удалось пересчитать связи'); } finally { setBusy(false); } }}>{busy ? 'Пересчёт…' : 'Пересчитать связи'}</Button>
    </div>
    <p>Записей: {data.total}. Один человек может иметь несколько вариантов участия.</p>
    {data.items.map(row => <ReviewRow key={row._id + ':' + version} row={row} refresh={refresh} onError={setError} />)}
    {!data.items.length && <p>Записей по выбранным условиям нет.</p>}
    <div className="flex gap-3"><Button variant="outline" disabled={!skip} onClick={() => setSkip(Math.max(0, skip - 50))}>Назад</Button><Button variant="outline" disabled={skip + 50 >= data.total} onClick={() => setSkip(skip + 50)}>Далее</Button></div>
  </div>;
}
