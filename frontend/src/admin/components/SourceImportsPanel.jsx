import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { ExternalLink, Loader2 } from 'lucide-react';
import DOMPurify from 'dompurify';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import ContentRelationSelector from './ContentRelationSelector';
import { contentApi, editorialImportsApi, getErrorMessage } from '../utils/api';

const RichTextEditor = lazy(() => import('./RichTextEditor'));
const SOURCES = [['24smi', '24СМИ'], ['vokrugtv', 'Вокруг ТВ'], ['gostandup', 'GoStandup'], ['zhaba', 'ЖАБА — медиа-болото']];
const sourceLabel = (sourceId) => SOURCES.find(([id]) => id === sourceId)?.[1] || '24СМИ';

const STATUSES = [['', 'Все'], ['pending', 'Ожидают'], ['accepted', 'Принятые'], ['rejected', 'Отклонённые'], ['conflict', 'Конфликты'], ['publishing', 'Публикуются']];
const STATUS_LABELS = { pending: 'Ожидает решения', accepted: 'Принято', rejected: 'Отклонено', conflict: 'Конфликт', publishing: 'Публикация' };
const emptySettings = { enabled: false, hour_moscow: 10, running: false, last_result: null };
const toDateInput = (value) => value ? String(value).slice(0, 10) : '';
const fromDateInput = (value) => value || null;
const formatTime = (value) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Moscow' }).format(date)} МСК`;
};

function PersonLinks({ value = [], onChange, title, editable = true }) {
  const [query, setQuery] = useState('');
  const [items, setItems] = useState([]);
  const [names, setNames] = useState({});
  useEffect(() => {
    let alive = true;
    Promise.all(value.map(async (id) => {
      try { const { data } = await contentApi.getPerson(id); return [id, data.title || data.full_name || id]; }
      catch { return [id, id]; }
    })).then((pairs) => { if (alive) setNames(Object.fromEntries(pairs)); });
    return () => { alive = false; };
  }, [value]);
  useEffect(() => {
    let alive = true;
    if (!editable || query.trim().length < 2) { setItems([]); return undefined; }
    const timer = setTimeout(() => contentApi.searchPeople(query.trim(), 15)
      .then(({ data }) => { if (alive) setItems(data || []); })
      .catch(() => { if (alive) setItems([]); }), 250);
    return () => { alive = false; clearTimeout(timer); };
  }, [editable, query]);
  return <div className="space-y-2">
    <label className="text-sm font-medium">{title}</label>
    {editable && <Input aria-label={title} placeholder="Найти человека..." value={query} onChange={(e) => setQuery(e.target.value)} />}
    {editable && items.filter((person) => !value.includes(person.id || person._id)).map((person) => <button type="button" className="mr-2 text-sm text-blue-700 underline" key={person.id || person._id} onClick={() => { onChange([...value, person.id || person._id]); setQuery(''); }}>{person.title || person.name || person.full_name}</button>)}
    <div className="flex flex-wrap gap-2">{value.map((id) => <Badge variant="secondary" key={id}>{names[id] || 'Загрузка…'}{editable && <button type="button" className="ml-2" aria-label={`Удалить ${names[id] || id}`} onClick={() => onChange(value.filter((entry) => entry !== id))}>×</button>}</Badge>)}</div>
  </div>;
}

function PersonTargetPicker({ targetId, matches = [], onChange, disabled }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  useEffect(() => {
    let alive = true;
    if (query.trim().length < 2) { setResults([]); return undefined; }
    const timer = setTimeout(() => contentApi.searchPeople(query.trim(), 15)
      .then(({ data }) => { if (alive) setResults(data || []); })
      .catch(() => { if (alive) setResults([]); }), 250);
    return () => { alive = false; clearTimeout(timer); };
  }, [query]);
  const label = (person) => person.title || person.name || person.full_name || person.id || person._id;
  const selected = [...matches, ...results].find((person) => (person.id || person._id) === targetId);
  return <div className="space-y-2">
    <div className="text-sm font-medium">Целевая персона</div>
    <div className="text-sm">{targetId ? `Выбрано: ${selected ? label(selected) : targetId}` : 'Будет создана новая страница'}</div>
    <Input aria-label="Поиск целевой персоны" disabled={disabled} placeholder="Найти существующего человека..." value={query} onChange={(e) => setQuery(e.target.value)} />
    {matches.length > 0 && <div className="text-xs text-muted-foreground">Совпадения источника</div>}
    <div className="flex flex-wrap gap-2">{matches.map((person) => <Button key={person.id} type="button" size="sm" variant={targetId === person.id ? 'default' : 'outline'} disabled={disabled} onClick={() => onChange(person.id)}>{label(person)}</Button>)}</div>
    {results.filter((person) => !matches.some((match) => match.id === (person.id || person._id))).map((person) => <Button key={person.id || person._id} type="button" size="sm" variant="outline" disabled={disabled} onClick={() => { onChange(person.id || person._id); setQuery(''); }}>{label(person)}</Button>)}
    {targetId && <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => onChange('')}>Создать новую страницу</Button>}
  </div>;
}

function ImportCard({ item, onChanged }) {
  const [draft, setDraft] = useState(() => ({ ...item.payload, bio: { ...(item.payload?.bio || {}) }, related_person_ids: item.payload?.related_person_ids || [], related_show_ids: item.payload?.related_show_ids || [] }));
  const [targetId, setTargetId] = useState(item.target_id || '');
  const [revision, setRevision] = useState(item.revision);
  const [targetConflict, setTargetConflict] = useState(item.status === 'conflict');
  const savedSnapshot = useRef({ payload: JSON.parse(JSON.stringify(item.payload)), targetId: item.target_id || null });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const canEdit = ['pending', 'conflict'].includes(item.status);
  const patchDraft = (key, value) => setDraft((old) => ({ ...old, [key]: value }));
  const patchBio = (key, value) => setDraft((old) => ({ ...old, bio: { ...(old.bio || {}), [key]: value } }));
  const currentTargetId = item.kind === 'news' ? (item.target_id || null) : (targetId || null);
  const snapshotPayload = (payload) => JSON.parse(JSON.stringify(payload));
  const saveSnapshot = (payload, nextTargetId) => { savedSnapshot.current = { payload: snapshotPayload(payload), targetId: nextTargetId }; };
  const hasUnsavedChanges = () => JSON.stringify(savedSnapshot.current.payload) !== JSON.stringify(draft) || savedSnapshot.current.targetId !== currentTargetId;
  const save = async () => {
    setBusy(true); setError('');
    try {
      const response = await editorialImportsApi.update(item._id, { revision, payload: draft, target_id: currentTargetId });
      setRevision(response.data.revision);
      saveSnapshot(draft, currentTargetId);
      setTargetConflict(false);
      await onChanged(response.data);
    } catch (err) { if (err.response?.status === 409) setTargetConflict(true); setError(getErrorMessage(err, err.response?.status === 409 ? 'Карточка изменилась на сервере. Сверьте целевую страницу перед повтором.' : 'Не удалось сохранить карточку')); }
    finally { setBusy(false); }
  };
  const decide = async (action) => {
    setBusy(true); setError('');
    try {
      if (action === 'reject') {
        await editorialImportsApi.reject(item._id, { revision });
      } else {
        let approveRevision = revision;
        if (canEdit && hasUnsavedChanges()) {
          const updated = await editorialImportsApi.update(item._id, { revision, payload: draft, target_id: currentTargetId });
          approveRevision = updated.data.revision;
          setRevision(approveRevision);
          saveSnapshot(draft, currentTargetId);
        }
        await editorialImportsApi.approve(item._id, { revision: approveRevision });
        setTargetConflict(false);
      }
      await onChanged();
    } catch (err) { if (err.response?.status === 409) setTargetConflict(true); setError(getErrorMessage(err, err.response?.status === 409 ? 'Конфликт версии: сверьте целевую страницу перед повтором.' : 'Не удалось выполнить решение')); }
    finally { setBusy(false); }
  };
  const refreshTarget = async () => {
    setBusy(true); setError('');
    try {
      const response = await editorialImportsApi.update(item._id, { revision, payload: draft, target_id: currentTargetId, refresh_target: true });
      setRevision(response.data.revision);
      saveSnapshot(draft, currentTargetId);
      setTargetConflict(false);
      await onChanged(response.data);
    } catch (err) { setError(getErrorMessage(err, err.response?.status === 409 ? 'Версия карточки изменилась. Обновите очередь.' : 'Не удалось обновить базовую версию')); }
    finally { setBusy(false); }
  };
  const conflictTargetId = item.kind === 'news' ? item.target_id : targetId;
  const conflictTargetPath = conflictTargetId ? `/admin/${item.kind === 'news' ? 'news' : 'people'}/${conflictTargetId}` : null;
  return <Card><CardContent className="space-y-4 p-5">
    <p className="max-w-full break-words text-sm font-medium text-muted-foreground">{sourceLabel(item.source_id)}</p>
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><div className="flex flex-wrap items-center gap-2"><h2 className="text-xl font-semibold">{draft.title || item.source?.title || 'Импортированный материал'}</h2><Badge>{item.kind === 'biography' ? 'Биография' : item.source_id === 'zhaba' ? 'Пост' : 'Новость'}</Badge><Badge variant="secondary">{STATUS_LABELS[item.status] || item.status}</Badge></div>{item.target_title && <p className="text-sm text-muted-foreground">Целевая страница: {item.target_title}</p>}</div>
      {item.published?.id && <span className="text-sm">Опубликовано: {item.published.slug}</span>}
    </header>
    <div className="rounded border p-3 text-sm"><a className="inline-flex items-center gap-1 break-all text-blue-700 underline" href={item.source?.url} target="_blank" rel="noopener noreferrer">{item.source?.title || item.source?.url}<ExternalLink className="h-3 w-3" /></a><div className="mt-1 text-muted-foreground">{[['Опубликовано', item.source?.published_at], ['Изменено', item.source?.modified_at], ['Проверено', item.source?.checked_at]].filter((entry) => entry[1]).map(([label, value]) => `${label}: ${formatTime(value)}`).join(' · ')}</div>{item.warnings?.length > 0 && <ul className="mt-2 list-disc pl-5 text-amber-800">{item.warnings.map((warning, i) => <li key={`${warning}-${i}`}>{warning}</li>)}</ul>}</div>
    <div className="grid gap-3 md:grid-cols-2"><label className="text-sm font-medium">Заголовок<Input aria-label="Заголовок" disabled={!canEdit} value={draft.title || ''} onChange={(e) => patchDraft('title', e.target.value)} /></label><label className="text-sm font-medium">Slug<Input aria-label="Slug" disabled={!canEdit} value={draft.slug || ''} onChange={(e) => patchDraft('slug', e.target.value)} /></label><label className="text-sm font-medium md:col-span-2">Краткое описание<Textarea aria-label="Краткое описание" disabled={!canEdit} value={draft.excerpt || ''} onChange={(e) => patchDraft('excerpt', e.target.value)} /></label></div>
    {item.kind === 'biography' && <div className="space-y-3 rounded border p-3"><h3 className="font-semibold">Карточка человека</h3><label className="block text-sm font-medium">Полное имя<Input aria-label="Полное имя" disabled={!canEdit} value={draft.full_name || ''} onChange={(e) => patchDraft('full_name', e.target.value)} /></label><label className="block text-sm font-medium">Дата рождения<Input aria-label="Дата рождения" disabled={!canEdit} type="date" value={toDateInput(draft.bio?.birth_date)} onChange={(e) => patchBio('birth_date', fromDateInput(e.target.value))} /></label><label className="block text-sm font-medium">Место рождения<Input aria-label="Место рождения" disabled={!canEdit} value={draft.bio?.birth_place || ''} onChange={(e) => patchBio('birth_place', e.target.value)} /></label><PersonTargetPicker targetId={targetId} matches={item.matches || []} onChange={setTargetId} disabled={!canEdit} /></div>}
    <div><label className="mb-2 block text-sm font-medium">Полный текст источника</label>{canEdit ? <Suspense fallback={<div className="min-h-40 rounded border p-4 text-sm text-muted-foreground">Загрузка редактора…</div>}><RichTextEditor content={draft.content || ''} onChange={(value) => patchDraft('content', value)} minHeight={300} /></Suspense> : <div className="prose prose-sm max-w-none rounded border p-4" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(draft.content || '') }} />}</div>
    {item.kind === 'news' ? <div className="grid gap-4 md:grid-cols-2"><PersonLinks title="Связанные люди" value={draft.related_person_ids} onChange={(ids) => patchDraft('related_person_ids', ids)} editable={canEdit} />{canEdit ? <ContentRelationSelector type="show" value={draft.related_show_ids} onChange={(ids) => patchDraft('related_show_ids', ids)} /> : <div className="text-sm">Связанные шоу: {draft.related_show_ids.join(', ') || '—'}</div>}</div> : canEdit ? <ContentRelationSelector type="show" value={draft.related_show_ids} onChange={(ids) => patchDraft('related_show_ids', ids)} /> : <div className="text-sm">Шоу: {draft.related_show_ids.join(', ') || '—'}</div>}
    {(targetConflict || item.status === 'conflict') && <div className="rounded border border-amber-400 bg-amber-50 p-3 text-sm"><p>Проверьте актуальную целевую страницу перед продолжением.</p>{conflictTargetPath && <a className="text-blue-700 underline" href={conflictTargetPath}>Открыть целевую страницу</a>}{conflictTargetId && canEdit && <Button className="ml-2" size="sm" variant="outline" disabled={busy} onClick={refreshTarget}>Я сверил страницу — обновить версию</Button>}</div>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {item.status === 'publishing' && <div className="space-y-2 text-sm"><p>Если утверждение прервалось, его можно завершить повторно после освобождения блокировки (до 5 минут).</p><Button disabled={busy} onClick={() => decide('approve')}>Завершить утверждение</Button></div>}
    {canEdit && <div className="flex flex-wrap gap-2"><Button disabled={busy} onClick={save}>{busy ? 'Сохранение…' : 'Сохранить'}</Button><Button disabled={busy} onClick={() => decide('approve')}>{busy ? 'Обработка…' : 'Утвердить и опубликовать'}</Button><Button disabled={busy} variant="destructive" onClick={() => decide('reject')}>Отклонить</Button></div>}
  </CardContent></Card>;
}

export default function SourceImportsPanel() {
  const [sourceId, setSourceId] = useState('24smi');
  const sourceName = sourceLabel(sourceId);
  const [kind, setKind] = useState('');
  const [status, setStatus] = useState('pending');
  const [skip, setSkip] = useState(0);
  const [data, setData] = useState({ items: [], total: 0 });
  const [urlsText, setUrlsText] = useState('');
  const [settings, setSettings] = useState(emptySettings);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState('');
  const pollTimer = useRef(null);
  const stopped = useRef(false);
  const loadSequence = useRef(0);
  const load = useCallback(async ({ silent = false, settingsData } = {}) => {
    const sequence = ++loadSequence.current;
    if (!silent) setLoading(true);
    setError('');
    try {
      const [queue, schedule] = await Promise.all([
        editorialImportsApi.list({ source_id: sourceId, kind: kind || undefined, status: status || undefined, skip, limit: 20 }),
        settingsData ? Promise.resolve({ data: settingsData }) : editorialImportsApi.getSettings(sourceId),
      ]);
      if (sequence === loadSequence.current) {
        setData(queue.data);
        setSettings({ ...emptySettings, ...schedule.data });
      }
    } catch (err) {
      if (sequence === loadSequence.current) setError(getErrorMessage(err, 'Не удалось загрузить очередь импорта'));
    } finally {
      if (sequence === loadSequence.current && !silent) setLoading(false);
    }
  }, [sourceId, kind, status, skip]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    stopped.current = false;
    return () => { stopped.current = true; clearTimeout(pollTimer.current); };
  }, []);
  const changed = async () => { await load(); };
  useEffect(() => {
    if (!settings.running) return undefined;
    let active = true;
    const poll = async () => {
      if (!active || stopped.current) return;
      try {
        const response = await editorialImportsApi.getSettings(sourceId);
        if (!active || stopped.current) return;
        const next = { ...emptySettings, ...response.data };
        setSettings(next);
        if (!next.running) {
          await load({ silent: true, settingsData: response.data });
          return;
        }
      } catch (err) {
        if (active && !stopped.current) setError(getErrorMessage(err, 'Не удалось проверить состояние сбора'));
      }
      if (active && !stopped.current) pollTimer.current = setTimeout(poll, 5000);
    };
    pollTimer.current = setTimeout(poll, 5000);
    return () => { active = false; clearTimeout(pollTimer.current); };
  }, [settings.running, load, sourceId]);
  const startScan = async () => {
    setBusy(true); setError(''); setReport('');
    try { await editorialImportsApi.scan({ source_id: sourceId, days: 3, limit: 100 }); setSettings((old) => ({ ...old, running: true })); }
    catch (err) { setError(getErrorMessage(err, 'Не удалось запустить сбор')); }
    finally { setBusy(false); }
  };
  const saveSchedule = async (enabled) => {
    setBusy(true); setError('');
    try { const response = await editorialImportsApi.updateSettings({ source_id: sourceId, enabled }); setSettings({ ...emptySettings, ...response.data }); }
    catch (err) { setError(getErrorMessage(err, 'Не удалось изменить расписание')); }
    finally { setBusy(false); }
  };
  const importUrls = async () => {
    const urls = urlsText.split(/\r?\n/).map((url) => url.trim()).filter(Boolean);
    if (!urls.length) return;
    if (urls.length > 10) { setError('Можно отправить не более 10 ссылок за раз'); return; }
    setBusy(true); setError(''); setReport('Импортируем материалы…');
    try { const { data: result } = await editorialImportsApi.importUrls(urls); const rows = result.results || []; setReport(rows.map((row) => `${row.url}: ${row.status === 'created' ? 'добавлено' : row.status === 'duplicate' ? 'дубликат' : `ошибка — ${row.error || 'неизвестная ошибка'}`}`).join('\n') || 'Результатов нет'); setUrlsText(''); await load(); }
    catch (err) { setError(getErrorMessage(err, 'Не удалось выполнить импорт')); }
    finally { setBusy(false); }
  };
  const selectSource = (id) => {
    if (id === sourceId) return;
    loadSequence.current += 1;
    setData({ items: [], total: 0 });
    setLoading(true);
    setSourceId(id);
    setSkip(0);
    setReport('');
    setSettings(emptySettings);
    setUrlsText('');
  };
  const last = settings.last_result;
  return <div className="space-y-5">
    <div className="flex flex-wrap gap-2" aria-label="Источник импорта">{SOURCES.map(([id, name]) => <Button key={id} className="whitespace-normal break-words text-left" disabled={busy} variant={sourceId === id ? 'default' : 'outline'} onClick={() => selectSource(id)}>{name}</Button>)}</div>
    <Card><CardContent className="space-y-4 p-5"><h2 className="text-xl font-semibold">Импорт материалов {sourceName}</h2><label className="block text-sm font-medium">{sourceId === 'zhaba' ? 'Ссылки на текстовые посты или подписи к медиа (до 10, по одной на строку). Фото и видео не загружаются.' : 'Ссылки на биографии или новости (до 10, по одной на строку)'}<Textarea aria-label="Ссылки для импорта" className="mt-1 min-h-28" value={urlsText} onChange={(e) => setUrlsText(e.target.value)} /></label><Button disabled={busy || !urlsText.trim()} onClick={importUrls}>{busy ? 'Обработка…' : 'Импортировать ссылки'}</Button>{report && <pre role="status" className="whitespace-pre-wrap rounded bg-muted p-3 text-sm">{report}</pre>}
      <div className="flex flex-wrap items-center gap-3 border-t pt-4"><Button disabled={busy || settings.running} variant="outline" onClick={startScan}>{settings.running ? 'Сбор выполняется…' : sourceId === 'zhaba' ? 'Собрать новые посты' : 'Собрать новости за 3 дня'}</Button><label className="flex items-center gap-2 text-sm"><input aria-label="Ежедневный сбор в 10:00 по Москве" type="checkbox" checked={!!settings.enabled} disabled={busy} onChange={(e) => saveSchedule(e.target.checked)} />Ежедневный сбор в 10:00 по Москве</label><span className="text-xs text-muted-foreground">{settings.next_run_at ? `Следующий запуск: ${formatTime(settings.next_run_at)}` : ''}</span></div>
      {last && <div className="text-sm" role="status">Последний сбор: просмотрено {last.checked}, добавлено {last.created}, дубликатов {last.duplicates}, неподходящих {last.unrelated}, ошибок {last.errors?.length || 0}{sourceId === 'zhaba' && Number.isFinite(last.without_text) ? `, без текста ${last.without_text}, страниц ${last.pages || 0}` : ''}{last.truncated ? sourceId === 'zhaba' ? '. Следующий запуск продолжит сбор.' : ', список ограничен' : ''}{last.errors?.length > 0 && <ul className="list-disc pl-5">{last.errors.map((entry, i) => <li key={`${entry.url}-${i}`}>{entry.url}: {entry.error}</li>)}</ul>}</div>}</CardContent></Card>
    <div className="flex flex-wrap gap-2">{[['', 'Все типы'], ['biography', 'Биографии'], ['news', sourceId === 'zhaba' ? 'Посты' : 'Новости']].map(([value, label]) => <Button key={value} size="sm" variant={kind === value ? 'default' : 'outline'} onClick={() => { setKind(value); setSkip(0); }}>{label}</Button>)}</div><div className="flex flex-wrap gap-2">{STATUSES.map(([value, label]) => <Button key={value} size="sm" variant={status === value ? 'secondary' : 'outline'} onClick={() => { setStatus(value); setSkip(0); }}>{label}</Button>)}</div>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}{loading ? <div className="flex h-32 items-center justify-center"><Loader2 className="h-8 w-8 animate-spin" /></div> : data.items?.length ? <div className="space-y-4"><p className="text-sm text-muted-foreground">Отобрано карточек: {data.total}</p>{data.items.map((item) => <ImportCard key={item._id} item={item} onChanged={changed} />)}<div className="flex gap-2"><Button variant="outline" disabled={!skip} onClick={() => setSkip(Math.max(0, skip - 20))}>Назад</Button><Button variant="outline" disabled={skip + 20 >= data.total} onClick={() => setSkip(skip + 20)}>Далее</Button></div></div> : <p className="rounded-lg border p-10 text-center text-muted-foreground">Карточек в этой категории нет.</p>}
  </div>;
}
