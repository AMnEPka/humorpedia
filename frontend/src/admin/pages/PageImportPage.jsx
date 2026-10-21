import { useState } from 'react';
import { Link } from 'react-router-dom';
import { getErrorMessage, pagePackagesApi } from '../utils/api';
import PageBuilderPreview from '../components/page-builder/PageBuilderPreview';

export default function PageImportPage() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [omitRelations, setOmitRelations] = useState([]);
  const [reviewed, setReviewed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadPreview = async () => {
    if (!file) return;
    setLoading(true);
    setError('');
    setPreview(null);
    setReviewed(false);
    setOmitRelations([]);
    try {
      const response = await pagePackagesApi.preview(file);
      setPreview(response.data);
    } catch (err) { setError(getErrorMessage(err, 'Не удалось проверить архив')); }
    finally { setLoading(false); }
  };

  const toggleOmit = (id) => {
    setReviewed(false);
    setOmitRelations((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  };
  const apply = async () => {
    if (!preview || !reviewed || preview.conflicts?.length) return;
    setLoading(true);
    setError('');
    try {
      const response = await pagePackagesApi.apply(preview.id, { hash: preview.hash, reviewed: true, omit_relations: omitRelations });
      setPreview(response.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось импортировать страницу'));
      try {
        const response = await pagePackagesApi.getPreview(preview.id);
        setPreview(response.data);
        if (response.data?.status === 'error' && response.data.error) setError('');
      } catch { /* The original apply error remains visible and the same package can still be retried. */ }
    }
    finally { setLoading(false); }
  };

  const applied = preview?.status === 'applied' || Boolean(preview?.result);
  const retrying = preview?.status === 'error' || Boolean(error);
  const blocked = loading || !reviewed || Boolean(preview?.conflicts?.length);
  return (
    <main className="mx-auto max-w-7xl space-y-6">
      <header><h1 className="text-2xl font-bold">Импорт страницы</h1><p className="text-muted-foreground">ZIP сначала проверяется и показывается в предпросмотре. Публичная страница создаётся только после отдельного подтверждения.</p></header>
      {error && <p role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}
      {applied ? <section className="rounded-lg border bg-white p-5"><h2 className="text-xl font-semibold">Страница импортирована</h2><p className="mt-2">Теперь её можно продолжить редактировать обычной админкой.</p><div className="mt-4 flex gap-4">{preview.result?.edit_url && <Link className="text-blue-700 underline" to={preview.result.edit_url}>Открыть редактор страницы</Link>}{preview.result?.url && <a className="text-blue-700 underline" href={preview.result.url} target="_blank" rel="noreferrer">Открыть публичную страницу</a>}</div></section> : <>
        <section className="rounded-lg border bg-white p-5"><label className="block font-medium">Пакет страницы (.zip)<input className="mt-2 block" type="file" accept=".zip,application/zip" onChange={(event) => { setFile(event.target.files?.[0] || null); setPreview(null); setReviewed(false); }} /></label><button type="button" className="mt-4 rounded bg-primary px-4 py-2 text-primary-foreground" disabled={!file || loading} onClick={loadPreview}>{loading ? 'Проверяем…' : 'Проверить архив'}</button></section>
        {preview && <>
          <section className="rounded-lg border bg-white p-5"><h2 className="text-xl font-semibold">Проверка пакета</h2><p className="mt-1">Тип: {preview.kind}. Статус проверки: {preview.status}</p><p>SHA-256: <code className="break-all">{preview.hash}</code></p>
            {preview.warnings?.length > 0 && <div className="mt-3 rounded border border-amber-300 bg-amber-50 p-3"><h3 className="font-semibold">Предупреждения</h3><ul className="list-inside list-disc">{preview.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></div>}
            {retrying && preview.error && <div role="alert" className="mt-3 rounded border border-red-300 bg-red-50 p-3 text-red-800"><h3 className="font-semibold">Импорт не завершён</h3><p>{preview.error}</p></div>}
            {preview.conflicts?.length > 0 && <div role="alert" className="mt-3 rounded border border-red-300 bg-red-50 p-3"><h3 className="font-semibold">Конфликты блокируют импорт</h3><ul className="list-inside list-disc">{preview.conflicts.map((conflict, index) => <li key={index}>{conflict}</li>)}</ul></div>}
          </section>
          <section className="rounded-lg border bg-white p-5"><h2 className="mb-3 text-xl font-semibold">Связи</h2>{preview.relations?.length ? preview.relations.map((relation) => <label key={relation.id} className="mb-2 flex items-start gap-2 rounded border p-3"><input type="checkbox" checked={omitRelations.includes(relation.id)} onChange={() => toggleOmit(relation.id)} /><span><strong>{relation.kind === 'appearance' ? 'Участие в шоу' : relation.kind === 'membership' ? 'Состав команды' : relation.kind}</strong><span className="ml-2">{relation.target?.slug || relation.name || relation.target?.name || 'Связь из пакета'}</span><span className="mt-1 block text-sm text-muted-foreground">Отметьте, если эту связь нужно пропустить.</span></span></label>) : <p>В пакете нет дополнительных связей.</p>}</section>
          <section className="rounded-lg border bg-white p-5"><h2 className="mb-3 text-xl font-semibold">Предпросмотр страницы: {preview.page?.title || preview.page?.name}</h2><PageBuilderPreview kind={preview.kind} page={preview.page} assets={preview.assets} ownerId={preview.id} getAsset={pagePackagesApi.getAsset} relations={preview.relations} /></section>
          <section className="rounded-lg border bg-white p-5"><label className="flex items-start gap-2"><input aria-label="Я проверил страницу и связи" type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} /><span>Я проверил текст, изображения и связи. Импорт создаст страницу в публичном каталоге.</span></label><button type="button" className="mt-3 rounded bg-primary px-4 py-2 text-primary-foreground" disabled={blocked} onClick={apply}>{loading ? 'Импортируем…' : retrying ? 'Повторить импорт' : 'Создать и опубликовать'}</button></section>
        </>}
      </>}
    </main>
  );
}
