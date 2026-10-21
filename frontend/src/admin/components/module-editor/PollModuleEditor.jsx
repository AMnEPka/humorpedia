import { Loader2, Trash2, Plus } from 'lucide-react';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useState, useEffect } from 'react';
import { contentApi } from '../../utils/api';
export default function PollModuleEditor({ data, updateData }) {
  const [poll, setPoll] = useState({
    question: '',
    status: 'draft',
    show_results_before_vote: false,
    options: [
      { id: crypto.randomUUID(), text: '', historical_votes: 0 },
      { id: crypto.randomUUID(), text: '', historical_votes: 0 }
    ]
  });
  const [loading, setLoading] = useState(Boolean(data.poll_id));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    let active = true;
    if (!data.poll_id) return undefined;
    contentApi.getPollForEdit(data.poll_id)
      .then((response) => active && setPoll({ ...response.data, options: response.data.options || [] }))
      .catch(() => active && setMessage('Не удалось загрузить выбранный опрос'))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [data.poll_id]);

  const setOption = (index, text) => setPoll((current) => ({
    ...current,
    options: current.options.map((option, optionIndex) => optionIndex === index ? { ...option, text } : option)
  }));

  const save = async () => {
    setSaving(true);
    setMessage('');
    try {
      const payload = {
        question: poll.question,
        status: poll.status,
        show_results_before_vote: Boolean(poll.show_results_before_vote),
        options: poll.options.map(({ id, text, historical_votes = 0 }) => ({ id, text, historical_votes }))
      };
      let pollId = data.poll_id;
      if (pollId) {
        await contentApi.updatePoll(pollId, payload);
      } else {
        const response = await contentApi.createPoll(payload);
        pollId = response.data.id;
        updateData({ ...data, poll_id: pollId });
      }
      setMessage('Опрос сохранён');
    } catch (error) {
      setMessage(error.response?.data?.detail || 'Не удалось сохранить опрос');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Загрузка опроса...</div>;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Вопрос</Label>
        <Textarea value={poll.question} onChange={(event) => setPoll((current) => ({ ...current, question: event.target.value }))} rows={2} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label>Статус</Label>
          <Select value={poll.status} onValueChange={(status) => setPoll((current) => ({ ...current, status }))}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="draft">Черновик</SelectItem>
              <SelectItem value="published">Опубликован</SelectItem>
              <SelectItem value="archived">Скрыт</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-end gap-2 pb-2">
          <Switch checked={Boolean(poll.show_results_before_vote)} onCheckedChange={(value) => setPoll((current) => ({ ...current, show_results_before_vote: value }))} />
          <Label>Показывать результаты до голосования</Label>
        </div>
      </div>
      <div className="space-y-2">
        <Label>Варианты ответа</Label>
        {poll.options.map((option, index) => (
          <div key={option.id} className="flex gap-2">
            <Input value={option.text} onChange={(event) => setOption(index, event.target.value)} placeholder={`Вариант ${index + 1}`} />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={poll.options.length <= 2 || Number(option.historical_votes || 0) > 0}
              onClick={() => setPoll((current) => ({ ...current, options: current.options.filter((_, itemIndex) => itemIndex !== index) }))}
              aria-label={`Удалить вариант ${index + 1}`}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
        <Button type="button" variant="outline" onClick={() => setPoll((current) => ({ ...current, options: [...current.options, { id: crypto.randomUUID(), text: '', historical_votes: 0 }] }))}>
          <Plus className="mr-2 h-4 w-4" />Добавить вариант
        </Button>
      </div>
      <div className="flex items-center gap-3">
        <Button type="button" onClick={save} disabled={saving}>
          {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Сохранить опрос
        </Button>
        {data.poll_id && <span className="text-xs text-muted-foreground">ID: {data.poll_id}</span>}
      </div>
      {message && <Alert><AlertDescription>{message}</AlertDescription></Alert>}
    </div>
  );
}
