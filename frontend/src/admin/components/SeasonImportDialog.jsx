import { useState } from 'react';
import { Link } from 'react-router-dom';
import { contentApi, getErrorMessage } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Upload, Loader2 } from 'lucide-react';

export default function SeasonImportDialog({ onImported }) {
  const [text, setText] = useState('');
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const changeText = (value) => {
    setText(value);
    setPreview(null);
    setResult(null);
    setError('');
  };

  const readFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      changeText(await file.text());
    } catch {
      setError('Не удалось прочитать файл');
    }
    event.target.value = '';
  };

  const check = async () => {
    setBusy(true);
    setError('');
    setPreview(null);
    setResult(null);
    try {
      const response = await contentApi.previewSeasonImport({ package: JSON.parse(text) });
      setPreview(response.data);
    } catch (err) {
      setError(err instanceof SyntaxError ? 'Неверный формат JSON' : getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const apply = async () => {
    setBusy(true);
    setError('');
    try {
      const response = await contentApi.importSeason({ package: JSON.parse(text), preview_token: preview.preview_token });
      setResult(response.data);
      onImported?.();
    } catch (err) {
      setError(getErrorMessage(err));
      setPreview(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog>
      <DialogTrigger asChild><Button variant="outline"><Upload className="mr-2 h-4 w-4" />Импорт сезона</Button></DialogTrigger>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Импорт нового сезона КВН</DialogTitle>
        <DialogDescription>
          Загрузите подготовленный пакет сезона. Проверка покажет связи с командами и новые карточки.
          После создания результаты можно редактировать в обычном редакторе сезона.
        </DialogDescription></DialogHeader>
        <label className="text-sm space-y-2">Файл сезона (JSON)
          <input aria-label="Файл сезона" type="file" accept=".json,application/json" onChange={readFile} disabled={busy} className="block" />
        </label>
        <Textarea aria-label="Пакет сезона" value={text} onChange={(event) => changeText(event.target.value)}
          disabled={busy} className="min-h-[200px] font-mono text-xs" placeholder="Вставьте JSON или выберите файл" />
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        <Button onClick={check} disabled={busy || !text.trim()}>{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Проверить пакет</Button>
        {preview && <div className="space-y-3">
          <h3 className="font-semibold">{preview.title}</h3>
          <p className="text-sm">{preview.teams.length} команд · {preview.games_count} игр · {preview.results_count} результатов.
            Новых карточек команд: {preview.teams_to_create}.</p>
          <ul className="text-sm space-y-1">{preview.teams.map((team) => <li key={team.key}>
            <strong>{team.name}</strong>{team.city && ` (${team.city})`} — {team.action === 'link' ? `связать с «${team.existing_name}»` : 'создать пустую команду'}
            {team.warning && <div className="text-amber-700">{team.warning}</div>}
            {team.candidates?.map((candidate) => <div key={candidate.slug}>Совпадение: {candidate.name} ({candidate.slug})</div>)}
          </li>)}</ul>
          {preview.errors.length > 0 && <Alert variant="destructive"><AlertDescription><ul>{preview.errors.map((message) => <li key={message}>{message}</li>)}</ul></AlertDescription></Alert>}
          {(JSON.parse(text).stages || []).map((stage) => <details key={stage.order} className="border rounded p-2">
            <summary>{stage.name} — {(stage.games || []).length} игр</summary>
            {(stage.games || []).map((game) => <div key={game.order} className="my-3 overflow-x-auto">
              <p className="font-medium">{game.name} · {game.date}</p>
              <table className="text-xs w-full"><thead><tr><th className="text-left">Команда</th>
                {(game.contests || []).map((contest) => <th key={contest}>{contest}</th>)}<th>Итого</th><th>Место</th><th>Проход</th></tr></thead>
                <tbody>{(game.results || []).map((row) => <tr key={row.team_key}>
                  <td>{preview.teams.find((team) => team.key === row.team_key)?.name}</td>
                  {(game.contests || []).map((contest) => <td className="text-center" key={contest}>{row.scores?.[contest] ?? '—'}</td>)}
                  <td className="text-center">{row.total ?? '—'}</td><td className="text-center">{row.place ?? '—'}</td>
                  <td>{row.is_additional ? 'Добор' : row.passed ? 'Да' : '—'}</td>
                </tr>)}</tbody></table>
            </div>)}
          </details>)}
          {!result && <Button onClick={apply} disabled={busy || preview.errors.length > 0}>
            {preview.unchanged ? 'Проверить существующий сезон' : 'Создать сезон и недостающие команды'}
          </Button>}
        </div>}
        {result && <Alert><AlertDescription>
          {result.created ? 'Сезон создан.' : 'Этот пакет уже импортирован.'} Новых команд: {result.created_teams.length}.{' '}
          <Link className="underline" to={`/admin/kvn/${result.page_id}`}>Открыть редактор</Link>{' · '}
          <a className="underline" href={`/${result.path}`} target="_blank" rel="noreferrer">Страница сезона</a>
        </AlertDescription></Alert>}
      </DialogContent>
    </Dialog>
  );
}
