import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, Loader2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { contentApi, editorialProposalsApi, getErrorMessage } from '../utils/api';

const KINDS = [
  ['update_person', 'Обновления страниц'],
  ['new_person', 'Новые люди'],
];

const STATUSES = [
  ['', 'Все'], ['new', 'Новые'], ['in_review', 'В работе'],
  ['conflict', 'Конфликты'], ['accepted', 'Принятые'], ['rejected', 'Отклонённые'],
];

const STATUS_LABELS = {
  new: 'Новое', in_review: 'В работе', conflict: 'Конфликт',
  accepted: 'Принято', rejected: 'Отклонено', pending: 'Ожидает решения',
};

const FIELD_LABELS = {
  'bio.birth_date': 'Дата рождения',
  'bio.death_date': 'Дата смерти',
  'bio.birth_place': 'Место рождения',
  'bio.current_city': 'Текущий город',
  'bio.occupation': 'Профессии',
  'bio.achievements': 'Достижения',
};

const fieldLabel = (field) => {
  if (FIELD_LABELS[field]) return FIELD_LABELS[field];
  if (field?.startsWith('facts.')) return `Факт: ${field.slice(6)}`;
  if (field?.startsWith('module.')) return 'Текст раздела страницы';
  if (field?.startsWith('appearance.')) return 'Участие в шоу';
  return field;
};

const formatValue = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
};

const isEditable = (status) => !status || status === 'pending' || status === 'new';

function Sources({ sources = [] }) {
  return (
    <div className="space-y-2 text-sm">
      <strong>Источники</strong>
      {sources.map((source, index) => (
        <div key={`${source.url}-${index}`} className="rounded border p-2">
          {/^https?:\/\//i.test(source.url || '') ? (
            <a className="inline-flex items-center gap-1 text-blue-700 underline break-all" href={source.url} target="_blank" rel="noopener noreferrer">
              {source.title || source.url}<ExternalLink className="h-3 w-3 shrink-0" />
            </a>
          ) : <span>{source.title || source.url}</span>}
          {(source.published_at || source.checked_at) && (
            <div className="text-muted-foreground">
              {source.published_at && `Опубликовано: ${source.published_at}`}
              {source.published_at && source.checked_at && ' · '}
              {source.checked_at && `Проверено: ${source.checked_at}`}
            </div>
          )}
          {source.excerpt && <p className="mt-1 whitespace-pre-wrap">{source.excerpt}</p>}
        </div>
      ))}
    </div>
  );
}

function ChangeReview({ change, choice, editedText, onChoice, onEdit }) {
  const pending = isEditable(change.status);
  const label = change.label || fieldLabel(change.field);
  return (
    <section className="rounded-lg border p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">{label}</h3>
        <Badge variant="secondary">{STATUS_LABELS[change.status] || change.status || 'Ожидает решения'}</Badge>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <div className="mb-1 text-sm font-medium">Сейчас</div>
          <pre className="rounded bg-muted p-3 text-sm whitespace-pre-wrap break-words font-sans">{formatValue(change.old_value)}</pre>
        </div>
        <div>
          <div className="mb-1 text-sm font-medium">Предлагается</div>
          {pending ? (
            <Textarea
              aria-label={`Предлагаемое значение: ${label}`}
              className="min-h-28 font-mono text-sm"
              value={editedText}
              onChange={(event) => onEdit(event.target.value)}
            />
          ) : (
            <pre className="rounded bg-muted p-3 text-sm whitespace-pre-wrap break-words font-sans">{formatValue(change.final_value ?? change.proposed_value)}</pre>
          )}
          {pending && typeof change.proposed_value !== 'string' && (
            <p className="mt-1 text-xs text-muted-foreground">Для списка или участия в шоу сохраняйте формат JSON.</p>
          )}
        </div>
      </div>
      <Sources sources={change.sources} />
      {pending && (
        <div className="flex flex-wrap gap-2" aria-label={`Решение: ${label}`}>
          <Button type="button" size="sm" variant={choice === 'accept' ? 'default' : 'outline'} onClick={() => onChoice('accept')}>
            {editedText === formatValue(change.proposed_value) ? 'Принять' : 'Принять с изменениями'}
          </Button>
          <Button type="button" size="sm" variant={choice === 'reject' ? 'destructive' : 'outline'} onClick={() => onChoice('reject')}>Отклонить</Button>
          {choice && <Button type="button" size="sm" variant="ghost" onClick={() => onChoice('')}>Снять решение</Button>}
        </div>
      )}
    </section>
  );
}

function ProposalCard({ item, onSaved }) {
  const [choices, setChoices] = useState({});
  const [edited, setEdited] = useState(() => Object.fromEntries((item.changes || []).map((change) => [change.id, formatValue(change.proposed_value)])));
  const [person, setPerson] = useState({
    title: item.candidate_name || '', full_name: item.candidate_name || '', slug: item.slug || '',
  });
  const [matches, setMatches] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const isNew = item.kind === 'new_person';
  const pendingChanges = (item.changes || []).filter((change) => isEditable(change.status));
  const active = pendingChanges.length > 0;

  useEffect(() => {
    if (!isNew || !person.full_name.trim()) return undefined;
    let alive = true;
    const tokens = person.full_name.trim().split(/\s+/);
    const surname = tokens[tokens.length - 1];
    if (surname.length < 2) return undefined;
    contentApi.searchPeople(surname, 20)
      .then(({ data }) => { if (alive) setMatches(data); })
      .catch(() => { if (alive) setMatches([]); });
    return () => { alive = false; };
  }, [isNew, person.full_name]);

  const submit = async () => {
    setError('');
    const decisions = [];
    try {
      for (const change of pendingChanges) {
        const decision = choices[change.id];
        if (!decision) continue;
        const entry = { change_id: change.id, decision };
        if (decision === 'accept' && edited[change.id] !== formatValue(change.proposed_value)) {
          if (typeof change.proposed_value === 'string') entry.edited_value = edited[change.id];
          else entry.edited_value = JSON.parse(edited[change.id]);
        }
        decisions.push(entry);
      }
    } catch {
      setError('Проверьте JSON в изменённом значении');
      return;
    }
    if (!decisions.length) { setError('Выберите хотя бы одно решение'); return; }
    if (isNew && decisions.length !== pendingChanges.length) {
      setError('Для новой страницы выберите решение по каждому факту');
      return;
    }
    if (isNew && decisions.some((entry) => entry.decision === 'accept') && (!person.title.trim() || !person.full_name.trim() || !person.slug.trim())) {
      setError('Для новой страницы укажите название, полное имя и адрес');
      return;
    }
    setBusy(true);
    try {
      await editorialProposalsApi.decide(item._id, {
        decisions,
        ...(isNew && decisions.some((entry) => entry.decision === 'accept') ? { person } : {}),
      });
      await onSaved();
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось сохранить решение'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold">{item.candidate_name || item.person_title || 'Страница человека'}</h2>
              <Badge>{STATUS_LABELS[item.status] || item.status}</Badge>
            </div>
            {item.reason && <p className="mt-1 text-sm text-muted-foreground">{item.reason}</p>}
            {item.created_at && <p className="mt-1 text-xs text-muted-foreground">Найдено: {new Date(item.created_at).toLocaleString('ru-RU')}</p>}
          </div>
          {item.created_person_id ? (
            <Link className="text-blue-700 underline" to={`/admin/people/${item.created_person_id}`}>Открыть созданную страницу</Link>
          ) : item.person_id ? (
            <Link className="text-blue-700 underline" to={`/admin/people/${item.person_id}`}>Открыть страницу</Link>
          ) : null}
        </div>

        {isNew && active && !item.created_person_id && (
          <div className="rounded-lg border bg-amber-50 p-4 space-y-3">
            <p className="text-sm">Новая страница появится на сайте после решения по всем фактам и принятия хотя бы одного. Проверьте совпадения и заполните данные человека перед сохранением.</p>
            {matches.length > 0 && (
              <div className="text-sm">
                <strong>Похожие страницы:</strong>{' '}
                {matches.map((match) => <Link key={match.id} className="mr-3 text-blue-700 underline" to={`/admin/people/${match.id}`}>{match.name}</Link>)}
              </div>
            )}
            <div className="grid gap-3 md:grid-cols-3">
              <label className="text-sm font-medium">Заголовок страницы<Input value={person.title} onChange={(event) => setPerson((old) => ({ ...old, title: event.target.value }))} /></label>
              <label className="text-sm font-medium">Полное имя<Input value={person.full_name} onChange={(event) => setPerson((old) => ({ ...old, full_name: event.target.value }))} /></label>
              <label className="text-sm font-medium">Адрес страницы<Input value={person.slug} onChange={(event) => setPerson((old) => ({ ...old, slug: event.target.value }))} placeholder="imya-familiya" /></label>
            </div>
          </div>
        )}

        {(item.changes || []).map((change) => (
          <ChangeReview
            key={change.id}
            change={change}
            choice={choices[change.id] || ''}
            editedText={edited[change.id] ?? formatValue(change.proposed_value)}
            onChoice={(decision) => setChoices((old) => ({ ...old, [change.id]: decision }))}
            onEdit={(value) => setEdited((old) => ({ ...old, [change.id]: value }))}
          />
        ))}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        {active && <Button disabled={busy} onClick={submit}>{busy ? 'Сохранение…' : isNew && Object.values(choices).includes('accept') && !item.created_person_id ? 'Сохранить решения и создать страницу' : 'Сохранить решения'}</Button>}
      </CardContent>
    </Card>
  );
}

export default function EditorialProposalsPage() {
  const [kind, setKind] = useState('update_person');
  const [status, setStatus] = useState('');
  const [skip, setSkip] = useState(0);
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [importFile, setImportFile] = useState(null);
  const [importText, setImportText] = useState('');
  const [importBusy, setImportBusy] = useState(false);
  const [importResult, setImportResult] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await editorialProposalsApi.list({ kind, status: status || undefined, skip, limit: 20 });
      setData(response.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось загрузить редакционные находки'));
    } finally {
      setLoading(false);
    }
  }, [kind, status, skip]);

  useEffect(() => { load(); }, [load]);

  const importProposals = async () => {
    if (!importFile && !importText.trim()) return;
    setImportBusy(true);
    setImportResult('');
    let imported = 0;
    try {
      const parsed = JSON.parse(importText.trim() || await importFile.text());
      const proposals = Array.isArray(parsed) ? parsed : parsed?.proposals;
      if (!Array.isArray(proposals) || proposals.length === 0) {
        throw new Error('В JSON нужен непустой массив предложений или объект с полем proposals');
      }
      for (const proposal of proposals) {
        await editorialProposalsApi.create(proposal);
        imported += 1;
      }
      setImportResult(`Обработано предложений: ${imported}. Повторные карточки сервер не добавляет.`);
      setImportFile(null);
      setImportText('');
      setSkip(0);
      await load();
    } catch (err) {
      setImportResult(`Обработано: ${imported}. ${getErrorMessage(err, err.message || 'Не удалось загрузить JSON')}`);
      if (imported) await load();
    } finally {
      setImportBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Редакционные находки</h1>
        <p className="mt-1 text-muted-foreground">Факты из ручного исследования. Каждое изменение применяется только после решения редактора.</p>
      </div>
      <details className="rounded-lg border bg-white p-4">
        <summary className="cursor-pointer font-medium">Загрузить предложения из JSON</summary>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Input aria-label="Файл предложений JSON" type="file" accept=".json,application/json" className="max-w-md" onChange={(event) => setImportFile(event.target.files?.[0] || null)} />
          <Button disabled={(!importFile && !importText.trim()) || importBusy} onClick={importProposals}>{importBusy ? 'Загрузка…' : 'Загрузить в очередь'}</Button>
        </div>
        <Textarea aria-label="Текст предложений JSON" className="mt-3 min-h-28 font-mono text-xs" placeholder="Или вставьте JSON с массивом предложений" value={importText} onChange={(event) => setImportText(event.target.value)} />
        {importResult && <p role="status" className="mt-2 text-sm">{importResult}</p>}
      </details>
      <div className="flex flex-wrap gap-2">
        {KINDS.map(([value, label]) => <Button key={value} size="sm" variant={kind === value ? 'default' : 'outline'} onClick={() => { setKind(value); setStatus(''); setSkip(0); }}>{label}</Button>)}
      </div>
      <div className="flex flex-wrap gap-2">
        {STATUSES.map(([value, label]) => <Button key={value} size="sm" variant={status === value ? 'secondary' : 'outline'} onClick={() => { setStatus(value); setSkip(0); }}>{label}</Button>)}
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {loading ? (
        <div className="flex h-40 items-center justify-center"><Loader2 className="h-8 w-8 animate-spin" /></div>
      ) : data.items?.length ? (
        <div className="space-y-5">
          <p className="text-sm text-muted-foreground">Найдено: {data.total}</p>
          {data.items.map((item) => <ProposalCard key={`${item._id}:${item.updated_at || ''}`} item={item} onSaved={load} />)}
          <div className="flex gap-2">
            <Button variant="outline" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - 20))}>Назад</Button>
            <Button variant="outline" disabled={skip + 20 >= data.total} onClick={() => setSkip(skip + 20)}>Далее</Button>
          </div>
        </div>
      ) : <p className="rounded-lg border bg-white p-10 text-center text-muted-foreground">Предложений в этой категории нет.</p>}
    </div>
  );
}
