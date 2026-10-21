import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { pageBuilderApi, getErrorMessage } from '../utils/api';
import FactsEditor from '../components/FactsEditor';
import ModuleEditor from '../components/ModuleEditor';
import PageBuilderPreview from '../components/page-builder/PageBuilderPreview';

const KIND_LABELS = { person: 'Человек', team: 'Команда КВН', show: 'Шоу' };
const UNSUPPORTED_MODULES = { person: ['video'], team: ['video', 'team_members', 'tv_appearances', 'games_list'], show: ['video', 'episodes_list'] };
const DEFAULT_MATERIALS = { name: '', birth_date: '', birth_place: '', occupation: '', notes: '', achievements: '', sources: '' };
const EMPTY_PAGE = {};
const activeJob = (job) => job && ['queued', 'running', 'pending', 'started'].includes(job.status);
const jobStatusLabels = { queued: 'В очереди', running: 'Идёт сборка', pending: 'Ожидает запуска', started: 'Идёт сборка', completed: 'Готово', error: 'Ошибка', cancelled: 'Отменена' };

function persistableRelations(kind, relations = []) {
  return relations.filter((relation) => kind === 'person'
    ? Boolean(relation.target?.slug?.trim())
    : kind === 'team' && Boolean(relation.name?.trim()))
    .map((relation) => {
      if (kind !== 'team') return relation;
      const next = { ...relation, from_year: relation.from_year === '' ? null : relation.from_year, to_year: relation.to_year === '' ? null : relation.to_year };
      if (!next.target?.slug?.trim()) delete next.target;
      return next;
    });
}

function updateField(document, field, value) {
  if (field.startsWith('bio.')) return { ...document, bio: { ...(document.bio || {}), [field.slice(4)]: value } };
  if (field.startsWith('seo.')) return { ...document, seo: { ...(document.seo || {}), [field.slice(4)]: value } };
  if (field.startsWith('social_links.')) return { ...document, social_links: { ...(document.social_links || {}), [field.slice(13)]: value } };
  return { ...document, [field]: value };
}

function moduleReviewText(module) {
  const data = module.data || {};
  if (module.type === 'text_block') {
    return String(data.content || '').replace(/<br\s*\/?\s*>/gi, '\n').replace(/<\/p\s*>/gi, '\n').replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim();
  }
  if (module.type === 'timeline') return (data.events || []).map((event) => `${event.date || event.year || ''} ${event.title || ''}${event.description ? ` — ${event.description}` : ''}`).join('\n');
  if (module.type === 'table') return (data.rows || []).map((row) => Array.isArray(row) ? row.join(' · ') : Object.values(row || {}).join(' · ')).join('\n');
  if (module.type === 'quote') return data.text || data.quote || '';
  if (module.type === 'participants') return (data.participants || []).map((person) => `${person.name || person.title || ''}${person.role ? ` — ${person.role}` : ''}`).join('\n');
  return data.title || module.type;
}

function PageReviewSummary({ page = {} }) {
  const modules = (page.modules || []).filter((module) => module.visible !== false);
  return <div className="space-y-3 text-sm">
    <p><strong>{page.title || 'Без заголовка'}</strong>{page.slug ? ` · /${page.slug}` : ''}</p>
    {page.facts && Object.keys(page.facts).length > 0 && <div><strong>Факты</strong><ul className="list-inside list-disc">{(page.facts_order || Object.keys(page.facts)).map((key) => page.facts[key] !== undefined && <li key={key}>{key}: {page.facts[key]}</li>)}</ul></div>}
    {page.description && <div><strong>Описание</strong><p className="whitespace-pre-wrap">{page.description.replace(/<br\s*\/?\s*>/gi, '\n').replace(/<\/p\s*>/gi, '\n').replace(/<[^>]*>/g, '')}</p></div>}
    {modules.map((module, index) => <section key={module.id || index} className="rounded border p-2"><strong>{module.data?.title || module.type}</strong><p className="mt-1 whitespace-pre-wrap">{moduleReviewText(module) || 'Раздел без текста'}</p></section>)}
    {page.tags?.length > 0 && <p><strong>Теги:</strong> {page.tags.map((tag) => typeof tag === 'string' ? tag : tag.name).join(', ')}</p>}
  </div>;
}

export default function PageBuilderPage() {
  const { id: routeId } = useParams();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [draft, setDraft] = useState(null);
  const [kind, setKind] = useState('person');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [actionPending, setActionPending] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [versionToAccept, setVersionToAccept] = useState(null);
  const [reviewedForExport, setReviewedForExport] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [assetFile, setAssetFile] = useState(null);
  const [assetUrls, setAssetUrls] = useState({});
  const draftRef = useRef(null);
  const revisionRef = useRef(null);
  const dirtyRef = useRef(false);
  const changeRef = useRef(0);
  const savePromiseRef = useRef(null);
  const saveTimerRef = useRef(null);
  const actionRef = useRef(false);
  const routeRef = useRef(routeId);
  routeRef.current = routeId;

  const setCurrentDraft = useCallback((next) => {
    draftRef.current = next;
    setDraft(next);
  }, []);

  const loadDraft = useCallback(async (id) => {
    const sequence = changeRef.current;
    const response = await pageBuilderApi.getDraft(id);
    if (routeRef.current !== id) return;
    if (draftRef.current?.id === id && (dirtyRef.current || savePromiseRef.current || actionRef.current
      || sequence !== changeRef.current || response.data.revision < revisionRef.current)) {
      setCurrentDraft({ ...draftRef.current, job: response.data.job, worker: response.data.worker, versions: response.data.versions, warnings: response.data.warnings });
      return;
    }
    revisionRef.current = response.data.revision;
    dirtyRef.current = false;
    setCurrentDraft(response.data);
    setError('');
  }, [setCurrentDraft]);

  const persistLatest = useCallback(async () => {
    const current = draftRef.current;
    if (!current?.id) return current;
    if (savePromiseRef.current) {
      await savePromiseRef.current;
      if (dirtyRef.current) return persistLatest();
      return draftRef.current;
    }
    const run = async () => {
      while (dirtyRef.current) {
        const snapshot = draftRef.current;
        const sequence = changeRef.current;
        const payload = { revision: revisionRef.current, materials: snapshot.materials, page: snapshot.page, relations: persistableRelations(snapshot.kind, snapshot.relations) };
        dirtyRef.current = false;
        setSaving(true);
        try {
          const response = await pageBuilderApi.updateDraft(snapshot.id, payload);
          revisionRef.current = response.data.revision;
          if (sequence !== changeRef.current) dirtyRef.current = true;
          setMessage('Изменения сохранены');
          setError('');
        } catch (err) {
          dirtyRef.current = true;
          setError(getErrorMessage(err, 'Не удалось сохранить изменения. Повторите сохранение.'));
          throw err;
        } finally {
          setSaving(false);
        }
      }
      return draftRef.current;
    };
    savePromiseRef.current = run().finally(() => { savePromiseRef.current = null; });
    return savePromiseRef.current;
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const load = async () => {
      // React Router reuses this component for /new and another draft.
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      await persistLatest();
      if (!active) return;
      if (draftRef.current?.id !== routeId) {
        setCurrentDraft(null);
        revisionRef.current = null;
        dirtyRef.current = false;
        setVersionToAccept(null);
        setReviewedForExport(false);
        setPreviewOpen(false);
        setAssetFile(null);
        setMessage('');
      }
      const { data } = await pageBuilderApi.listDrafts();
      if (!active) return;
      setItems(data.items || []);
      if (routeId && routeId !== 'new') await loadDraft(routeId);
    };
    load().catch((err) => active && setError(getErrorMessage(err, 'Не удалось загрузить заготовки')))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [routeId, loadDraft, persistLatest, setCurrentDraft]);

  const markEdited = useCallback((next) => {
    if (actionRef.current) return;
    setCurrentDraft(next);
    setReviewedForExport(false);
    dirtyRef.current = true;
    changeRef.current += 1;
    setMessage('Есть несохранённые изменения');
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => { persistLatest().catch(() => {}); }, 500);
  }, [persistLatest, setCurrentDraft]);

  useEffect(() => () => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    if (dirtyRef.current) persistLatest().catch(() => {});
  }, [persistLatest]);

  useEffect(() => {
    if (!draft?.id) return undefined;
    const timer = setInterval(() => loadDraft(draft.id).catch(() => {}), activeJob(draft.job) ? 1500 : 5000);
    return () => clearInterval(timer);
  }, [draft?.id, draft?.job, loadDraft]);

  useEffect(() => {
    let active = true;
    const created = [];
    const load = async () => {
      const entries = await Promise.all((draft?.assets || []).map(async (asset) => {
        try {
          const response = await pageBuilderApi.getAsset(draft.id, asset.id);
          const url = URL.createObjectURL(response.data);
          if (!active) {
            URL.revokeObjectURL(url);
            return [asset.id, ''];
          }
          created.push(url);
          return [asset.id, url];
        } catch { return [asset.id, '']; }
      }));
      if (active) setAssetUrls(Object.fromEntries(entries));
    };
    if (draft?.id) load(); else setAssetUrls({});
    return () => { active = false; created.forEach((url) => URL.revokeObjectURL(url)); };
  }, [draft?.id, draft?.assets]);

  const isPerson = draft?.kind === 'person';
  const label = KIND_LABELS[draft?.kind] || 'Страница';
  const page = draft?.page ?? EMPTY_PAGE;
  const setPageField = (field, value) => {
    let nextPage = updateField(page, field, value);
    if (isPerson && field === 'bio.birth_date') {
      const facts = { ...(page.facts || {}) };
      const order = [...(page.facts_order || [])];
      if (value) {
        facts['Дата рождения'] = value;
        if (!order.includes('Дата рождения')) order.push('Дата рождения');
      } else {
        delete facts['Дата рождения'];
        nextPage = { ...nextPage, facts_order: order.filter((item) => item !== 'Дата рождения') };
      }
      nextPage = { ...nextPage, facts, facts_order: value ? order : nextPage.facts_order };
    }
    markEdited({ ...draft, page: nextPage });
  };

  const create = async (event) => {
    event.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError('');
    try {
      const response = await pageBuilderApi.createDraft({ kind, materials: { ...DEFAULT_MATERIALS, name: name.trim() } });
      revisionRef.current = response.data.revision;
      setCurrentDraft(response.data);
      setItems((current) => [response.data, ...current]);
      navigate(`/admin/page-builder/${response.data.id}`);
    } catch (err) { setError(getErrorMessage(err, 'Не удалось создать заготовку')); }
    finally { setLoading(false); }
  };

  const runAction = async (action, successText, preserveEditorState = false) => {
    if (actionRef.current) return;
    actionRef.current = true;
    setActionPending(true);
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    setReviewedForExport(false);
    setError('');
    try {
      await persistLatest();
      const response = await action();
      revisionRef.current = response.data.revision;
      dirtyRef.current = false;
      setCurrentDraft(preserveEditorState
        ? { ...response.data, page: draftRef.current.page, materials: draftRef.current.materials, relations: draftRef.current.relations }
        : response.data);
      setMessage(successText);
    } catch (err) { setError(getErrorMessage(err, 'Действие не выполнено')); }
    finally { actionRef.current = false; setActionPending(false); }
  };

  const navigateTo = async (event, path) => {
    event.preventDefault();
    if (actionRef.current) return;
    actionRef.current = true;
    setActionPending(true);
    try {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      await persistLatest();
      navigate(path);
    } catch (err) { setError(getErrorMessage(err, 'Сохраните изменения перед переходом.')); }
    finally { actionRef.current = false; setActionPending(false); }
  };

  const generate = () => runAction(() => pageBuilderApi.generate(draft.id, { revision: revisionRef.current }), 'Страница поставлена в очередь', true);
  const cancel = () => runAction(() => pageBuilderApi.cancel(draft.id), 'Сборка отменена');
  const download = async () => {
    await runAction(async () => {
      const response = await pageBuilderApi.exportDraft(draft.id, true);
      const url = URL.createObjectURL(response.data);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${page.slug || 'page'}.humorpedia.zip`;
      anchor.click();
      URL.revokeObjectURL(url);
      return { data: { ...draft, revision: revisionRef.current } };
    }, 'Пакет страницы скачан');
  };

  const acceptVersion = () => runAction(() => pageBuilderApi.acceptVersion(draft.id, { revision: revisionRef.current, version_id: versionToAccept.id }), 'Предложение принято; его можно редактировать дальше');
  const addRelation = () => {
    const relation = draft.kind === 'person'
      ? { id: `relation-${Date.now()}`, kind: 'appearance', target: { type: 'show', slug: '' }, achievement: 'participant' }
      : { id: `relation-${Date.now()}`, kind: 'membership', name: '', roles: [], from_year: null, to_year: null };
    markEdited({ ...draft, relations: [...(draft.relations || []), relation] });
  };
  const updateRelation = (index, key, value) => markEdited({ ...draft, relations: (draft.relations || []).map((relation, relationIndex) => relationIndex === index ? { ...relation, [key]: value } : relation) });
  const mediaField = isPerson ? 'photo' : draft?.kind === 'team' ? 'logo' : 'poster';
  const mediaValue = page[mediaField] || {};
  const setMediaValue = (field, value) => setPageField(mediaField, { ...(typeof mediaValue === 'string' ? { url: mediaValue } : mediaValue), [field]: value });
  const selectAsset = (assetId) => setMediaValue('url', assetId ? `asset:${assetId}` : '');

  const versions = draft?.versions || [];
  if (loading && !draft) return <p role="status">Загружаем заготовки…</p>;
  if (!draft) return (
    <main className="mx-auto max-w-4xl space-y-6">
      <header><h1 className="text-2xl font-bold">Конструктор страниц</h1><p className="text-muted-foreground">Подготовьте новую страницу, проверьте её и скачайте пакет для переноса.</p></header>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      <form onSubmit={create} className="space-y-4 rounded-lg border bg-white p-5">
        <label className="block">Тип страницы<select className="mt-1 block w-full rounded border p-2" value={kind} onChange={(event) => setKind(event.target.value)}><option value="person">Человек</option><option value="team">Команда КВН</option><option value="show">Шоу</option></select></label>
        <label className="block">Имя или название<input className="mt-1 block w-full rounded border p-2" value={name} onChange={(event) => setName(event.target.value)} /></label>
        <button className="rounded bg-primary px-4 py-2 text-primary-foreground" disabled={!name.trim() || loading}>Создать заготовку</button>
      </form>
      {!!items.length && <section><h2 className="font-semibold">Сохранённые заготовки</h2><ul className="list-inside list-disc">{items.map((item) => <li key={item.id}><Link className="text-blue-700 underline" to={`/admin/page-builder/${item.id}`}>{item.page?.title || item.materials?.name || KIND_LABELS[item.kind]}</Link></li>)}</ul></section>}
    </main>
  );

  const workerOffline = draft.worker?.status === 'offline' || draft.worker?.status === 'unavailable';
  return (
    <main className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div><Link className="text-sm text-blue-700 underline" to="/admin/page-builder" onClick={(event) => navigateTo(event, '/admin/page-builder')}>← Все заготовки</Link><h1 className="mt-2 text-2xl font-bold">Конструктор: {label}</h1><p className="text-sm text-muted-foreground">Материалы, страница и связи сохраняются как редактируемые поля Humorpedia.</p></div>
        <Link className="rounded border px-3 py-2" to="/admin/page-builder/new" onClick={(event) => navigateTo(event, '/admin/page-builder/new')}>Новая заготовка</Link>
        <span role="status" className="text-sm">{saving ? 'Сохраняем…' : message}</span>
      </header>
      <fieldset disabled={actionPending || loading} className="min-w-0 space-y-6">
      {error && <p role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}
      {draft.warnings?.length > 0 && <section className="rounded border border-amber-300 bg-amber-50 p-3"><h2 className="font-semibold">Проверьте материалы</h2><ul className="list-inside list-disc">{draft.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></section>}

      <section className="rounded-lg border bg-white p-5"><h2 className="mb-4 text-xl font-semibold">Исходные материалы</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <label>Имя / название<input className="mt-1 block w-full rounded border p-2" value={draft.materials?.name || ''} onChange={(e) => markEdited({ ...draft, materials: { ...draft.materials, name: e.target.value } })} /></label>
          {isPerson ? <><label>Дата рождения<input className="mt-1 block w-full rounded border p-2" value={draft.materials?.birth_date || ''} onChange={(e) => markEdited({ ...draft, materials: { ...draft.materials, birth_date: e.target.value } })} /></label><label>Место рождения<input className="mt-1 block w-full rounded border p-2" value={draft.materials?.birth_place || ''} onChange={(e) => markEdited({ ...draft, materials: { ...draft.materials, birth_place: e.target.value } })} /></label><label>Профессия<input className="mt-1 block w-full rounded border p-2" value={draft.materials?.occupation || ''} onChange={(e) => markEdited({ ...draft, materials: { ...draft.materials, occupation: e.target.value } })} /></label></> : draft.kind === 'team' ? <><label>Год основания<input className="mt-1 block w-full rounded border p-2" value={draft.materials?.birth_date || ''} onChange={(e) => markEdited({ ...draft, materials: { ...draft.materials, birth_date: e.target.value } })} /></label><label>Город<input className="mt-1 block w-full rounded border p-2" value={draft.materials?.birth_place || ''} onChange={(e) => markEdited({ ...draft, materials: { ...draft.materials, birth_place: e.target.value } })} /></label></> : <><label>Дата премьеры<input className="mt-1 block w-full rounded border p-2" value={draft.materials?.birth_date || ''} onChange={(e) => markEdited({ ...draft, materials: { ...draft.materials, birth_date: e.target.value } })} /></label><label>Формат<input className="mt-1 block w-full rounded border p-2" value={draft.materials?.occupation || ''} onChange={(e) => markEdited({ ...draft, materials: { ...draft.materials, occupation: e.target.value } })} /></label></>}
          <label className="md:col-span-2">{draft.kind === 'team' ? 'Достижения команды' : draft.kind === 'show' ? 'Достижения / сезоны' : 'Достижения'}<textarea className="mt-1 block w-full rounded border p-2" rows="3" value={draft.materials?.achievements || ''} onChange={(e) => markEdited({ ...draft, materials: { ...draft.materials, achievements: e.target.value } })} /></label>
          <label className="md:col-span-2">{draft.kind === 'team' ? 'Сведения о команде' : draft.kind === 'show' ? 'Сведения о шоу' : 'Что известно'}<textarea className="mt-1 block w-full rounded border p-2" rows="5" value={draft.materials?.notes || ''} onChange={(e) => markEdited({ ...draft, materials: { ...draft.materials, notes: e.target.value } })} /></label>
          <label className="md:col-span-2">Ссылки и источники<textarea className="mt-1 block w-full rounded border p-2" rows="2" value={draft.materials?.sources || ''} onChange={(e) => markEdited({ ...draft, materials: { ...draft.materials, sources: e.target.value } })} /></label>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3"><input type="file" accept="image/*" aria-label="Загрузить изображение" onChange={(e) => setAssetFile(e.target.files?.[0] || null)} /><button type="button" className="rounded border px-3 py-2" disabled={!assetFile} onClick={() => runAction(async () => { await pageBuilderApi.uploadAsset(draft.id, assetFile); const response = await pageBuilderApi.getDraft(draft.id); revisionRef.current = response.data.revision; setCurrentDraft(response.data); return response; }, 'Изображение загружено')}>Загрузить изображение</button></div>
        {draft.assets?.length > 0 && <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{draft.assets.map((asset) => <div key={asset.id} className="rounded border p-2"><img className="mb-2 h-32 w-full object-contain" src={assetUrls[asset.id] || ''} alt={asset.alt || asset.filename} /><div className="break-all text-sm">{asset.filename}</div><label className="mt-2 block text-xs">Ссылка для вставки в модуль<input className="mt-1 w-full rounded border p-1" readOnly value={`asset:${asset.id}`} onFocus={(event) => event.target.select()} /></label><button type="button" className="mt-2 rounded border px-2 py-1 text-sm" onClick={() => selectAsset(asset.id)}>Выбрать как основное изображение</button></div>)}</div>}
      </section>

      <section className="space-y-4 rounded-lg border bg-white p-5"><h2 className="text-xl font-semibold">Редактируемая страница</h2>
        <div className="grid gap-3 md:grid-cols-2"><label>Заголовок<input aria-label="Заголовок страницы" className="mt-1 block w-full rounded border p-2" value={page.title || ''} onChange={(e) => setPageField('title', e.target.value)} /></label><label>Адрес (slug)<input className="mt-1 block w-full rounded border p-2" value={page.slug || ''} onChange={(e) => setPageField('slug', e.target.value)} /><span className="text-xs text-muted-foreground">Короткая часть адреса страницы, латиницей и через дефис.</span></label>
          {isPerson ? <label>Полное имя<input className="mt-1 block w-full rounded border p-2" value={page.full_name || ''} onChange={(e) => setPageField('full_name', e.target.value)} /></label> : <label>Название<input className="mt-1 block w-full rounded border p-2" value={page.name || ''} onChange={(e) => setPageField('name', e.target.value)} /></label>}
          {isPerson && <>
            <label>Дата рождения<input className="mt-1 block w-full rounded border p-2" value={page.bio?.birth_date || ''} onChange={(e) => setPageField('bio.birth_date', e.target.value)} /></label>
            <label>Дата смерти<input className="mt-1 block w-full rounded border p-2" value={page.bio?.death_date || ''} onChange={(e) => setPageField('bio.death_date', e.target.value)} /></label>
            <label>Место рождения<input className="mt-1 block w-full rounded border p-2" value={page.bio?.birth_place || ''} onChange={(e) => setPageField('bio.birth_place', e.target.value)} /></label>
            <label>Текущий город<input className="mt-1 block w-full rounded border p-2" value={page.bio?.current_city || ''} onChange={(e) => setPageField('bio.current_city', e.target.value)} /></label>
            <label>Профессии<input className="mt-1 block w-full rounded border p-2" value={(page.bio?.occupation || []).join(', ')} onChange={(e) => setPageField('bio.occupation', e.target.value.split(',').map((item) => item.trim()).filter(Boolean))} /></label>
            <label>Достижения в профиле<input className="mt-1 block w-full rounded border p-2" value={(page.bio?.achievements || []).join(', ')} onChange={(e) => setPageField('bio.achievements', e.target.value.split(',').map((item) => item.trim()).filter(Boolean))} /></label>
            <label>Псевдонимы<input className="mt-1 block w-full rounded border p-2" value={(page.aliases || []).join(', ')} onChange={(e) => setPageField('aliases', e.target.value.split(',').map((item) => item.trim()).filter(Boolean))} /></label>
          </>}
          {draft.kind === 'show' && <label className="md:col-span-2">Описание шоу<textarea className="mt-1 block w-full rounded border p-2" rows="4" value={page.description || ''} onChange={(e) => setPageField('description', e.target.value)} /></label>}
          <label>Подпись к основному изображению<input className="mt-1 block w-full rounded border p-2" value={mediaValue.caption || ''} onChange={(e) => setMediaValue('caption', e.target.value)} /></label>
          <label>Описание изображения (alt)<input className="mt-1 block w-full rounded border p-2" value={mediaValue.alt || ''} onChange={(e) => setMediaValue('alt', e.target.value)} /></label>
          <div className="md:col-span-2"><h3 className="mb-2 font-medium">Социальные ссылки</h3><div className="grid gap-3 sm:grid-cols-2">{[['vk', 'ВКонтакте'], ['telegram', 'Telegram'], ['youtube', 'YouTube'], ['instagram', 'Instagram'], ['website', 'Сайт']].map(([field, title]) => <label key={field}>{title}<input type="url" className="mt-1 block w-full rounded border p-2" value={page.social_links?.[field] || ''} onChange={(e) => setPageField(`social_links.${field}`, e.target.value)} /></label>)}</div></div>
          <label>Теги<input className="mt-1 block w-full rounded border p-2" value={(page.tags || []).map((tag) => typeof tag === 'string' ? tag : tag.name).join(', ')} onChange={(e) => setPageField('tags', e.target.value.split(',').map((tag) => tag.trim()).filter(Boolean))} /></label>
          <label>Заголовок для поиска<input className="mt-1 block w-full rounded border p-2" value={page.seo?.meta_title || ''} onChange={(e) => setPageField('seo.meta_title', e.target.value)} /></label><label>Описание для поиска<textarea className="mt-1 block w-full rounded border p-2" rows="2" value={page.seo?.meta_description || ''} onChange={(e) => setPageField('seo.meta_description', e.target.value)} /></label>
        </div>
        <div><h3 className="mb-2 font-semibold">Факты</h3><FactsEditor facts={page.facts || {}} factsOrder={page.facts_order || []} onChange={({ facts, facts_order }) => markEdited({ ...draft, page: { ...page, facts, facts_order, ...(isPerson ? { bio: { ...(page.bio || {}), birth_date: facts['Дата рождения'] || '' } } : {}) } })} /><button type="button" className="mt-2 rounded border px-3 py-2" onClick={() => { const facts = { ...(page.facts || {}), [`Новый факт ${Object.keys(page.facts || {}).length + 1}`]: '' }; setPageField('facts', facts); }}>Добавить факт</button></div>
        <div><h3 className="mb-2 font-semibold">Разделы страницы</h3><ModuleEditor modules={page.modules || []} onChange={(modules) => setPageField('modules', modules)} contentType={draft.kind} excludedTypes={UNSUPPORTED_MODULES[draft.kind] || []} /></div>
      </section>

      <section className="rounded-lg border bg-white p-5"><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><h2 className="text-xl font-semibold">Связи страницы</h2>{draft.kind !== 'show' && <button type="button" className="rounded border px-3 py-2" onClick={addRelation}>{isPerson ? 'Добавить участие в шоу' : 'Добавить участника'}</button>}</div>
        {draft.kind === 'show' && <p className="text-sm text-muted-foreground">Добавляйте участников шоу через редактируемый модуль «Участники» в разделах страницы.</p>}
        {draft.relations?.some((relation) => !persistableRelations(draft.kind, [relation]).length) && <p role="status" className="mb-3 rounded bg-amber-50 p-2 text-sm text-amber-900">Заполните имя участника или slug шоу в добавленной связи; незаполненные строки не сохраняются.</p>}
        {(draft.relations || []).map((relation, index) => <div key={relation.id || index} className="mb-3 grid gap-3 rounded border p-3 md:grid-cols-3"><label>{isPerson ? 'Slug шоу' : 'Имя участника'}<input className="mt-1 block w-full rounded border p-2" value={isPerson ? relation.target?.slug || '' : relation.name || ''} onChange={(e) => isPerson ? updateRelation(index, 'target', { ...(relation.target || {}), type: 'show', slug: e.target.value }) : updateRelation(index, 'name', e.target.value)} /></label>{isPerson ? <label>Результат<select className="mt-1 block w-full rounded border p-2" value={relation.achievement || 'participant'} onChange={(e) => updateRelation(index, 'achievement', e.target.value)}><option value="participant">Участник</option><option value="finalist">Финалист</option><option value="winner">Победитель</option></select></label> : <label>Роли, через запятую<input className="mt-1 block w-full rounded border p-2" value={(relation.roles || []).join(', ')} onChange={(e) => updateRelation(index, 'roles', e.target.value.split(',').map((role) => role.trim()).filter(Boolean))} /></label>}{!isPerson && <><label>Slug участника<input className="mt-1 block w-full rounded border p-2" value={relation.target?.slug || ''} onChange={(e) => updateRelation(index, 'target', { type: 'person', slug: e.target.value })} /></label><label>С какого года<input type="number" className="mt-1 block w-full rounded border p-2" value={relation.from_year ?? ''} onChange={(e) => updateRelation(index, 'from_year', e.target.value ? Number(e.target.value) : null)} /></label><label>По какой год<input type="number" className="mt-1 block w-full rounded border p-2" value={relation.to_year ?? ''} onChange={(e) => updateRelation(index, 'to_year', e.target.value ? Number(e.target.value) : null)} /></label></>}<button type="button" className="self-end rounded border border-red-300 px-3 py-2 text-red-700" onClick={() => markEdited({ ...draft, relations: draft.relations.filter((_, relationIndex) => relationIndex !== index) })}>Удалить связь</button></div>)}
      </section>

      <section className="rounded-lg border bg-white p-5"><div className="flex flex-wrap gap-2"><button type="button" className="rounded bg-primary px-4 py-2 text-primary-foreground" disabled={saving || workerOffline || activeJob(draft.job)} onClick={generate}>Собрать страницу</button>{activeJob(draft.job) && <button type="button" className="rounded border px-4 py-2" onClick={cancel}>Отменить сборку</button>}<button type="button" className="rounded border px-4 py-2" onClick={() => setPreviewOpen((open) => !open)}>{previewOpen ? 'Скрыть предпросмотр' : 'Предпросмотр страницы'}</button></div>
        {workerOffline && <p role="status" className="mt-3 text-amber-800">Локальный исполнитель недоступен. Материалы сохранены; запустите его, чтобы собирать предложения.</p>}
        <p className="mt-2 text-sm">Состояние: {jobStatusLabels[draft.job?.status] || draft.job?.status || 'не запускалась'}{draft.job?.error ? ` — ${draft.job.error}` : ''}</p>
        {previewOpen && <div className="mt-5 space-y-4"><h3 className="font-semibold">Предпросмотр в публичном оформлении</h3><PageBuilderPreview kind={draft.kind} page={page} assets={draft.assets} ownerId={draft.id} getAsset={pageBuilderApi.getAsset} relations={draft.relations} /></div>}
      </section>

      {!!versions.length && <section className="rounded-lg border bg-white p-5"><h2 className="mb-3 text-xl font-semibold">Предложения редактору</h2>{versions.map((version) => <article key={version.id} className="mb-4 rounded border p-4"><h3 className="font-semibold">Версия для входных материалов {version.input_revision}</h3><div className="mt-3 grid gap-3 md:grid-cols-2"><div><h4 className="mb-2 font-semibold">Текущая редакция</h4><PageReviewSummary page={page} /></div><div><h4 className="mb-2 font-semibold">Предложение</h4><PageReviewSummary page={version.page} /></div></div>{version.warnings?.length > 0 && <p className="mt-2 text-amber-800">Предупреждения: {version.warnings.join('; ')}</p>}{version.questions?.length > 0 && <p className="mt-2">Нужна проверка: {version.questions.join('; ')}</p>}<button type="button" className="mt-3 rounded border px-3 py-2" onClick={() => setVersionToAccept(version)}>Принять предложение</button></article>)}</section>}

      <section className="rounded-lg border bg-white p-5"><h2 className="mb-3 text-xl font-semibold">Экспорт</h2><label className="flex items-start gap-2"><input aria-label="Я проверил итоговую страницу вручную" type="checkbox" checked={reviewedForExport} onChange={(e) => setReviewedForExport(e.target.checked)} /><span>Я вручную проверил текст, факты, связи и предпросмотр страницы.</span></label><button type="button" className="mt-3 rounded bg-primary px-4 py-2 text-primary-foreground" disabled={!reviewedForExport || saving || draft.relations?.some((relation) => !persistableRelations(draft.kind, [relation]).length)} onClick={download}>Скачать пакет страницы</button></section>
      {versionToAccept && <div role="dialog" aria-modal="true" aria-label="Подтверждение замены страницы" className="fixed inset-0 z-50 flex items-center justify-center overflow-auto bg-black/50 p-4"><div className="my-8 w-full max-w-5xl space-y-4 rounded-lg bg-white p-6"><h2 className="text-xl font-semibold">Заменить текущую редакцию?</h2><p>Сравните заголовок, факты и текст разделов. После подтверждения предложение станет основой страницы; затем его можно редактировать в этом конструкторе.</p><div className="grid gap-4 md:grid-cols-2"><div><h3 className="mb-2 font-semibold">Сейчас</h3><PageReviewSummary page={page} /></div><div><h3 className="mb-2 font-semibold">Предложение</h3><PageReviewSummary page={versionToAccept.page} /></div></div><div className="flex justify-end gap-2"><button type="button" className="rounded border px-3 py-2" onClick={() => setVersionToAccept(null)}>Оставить текущую</button><button type="button" className="rounded bg-primary px-3 py-2 text-primary-foreground" onClick={() => { const selected = versionToAccept; setVersionToAccept(null); runAction(() => pageBuilderApi.acceptVersion(draft.id, { revision: revisionRef.current, version_id: selected.id }), 'Предложение принято; его можно редактировать дальше'); }}>Заменить текущую страницу</button></div></div></div>}
      </fieldset>
    </main>
  );
}
