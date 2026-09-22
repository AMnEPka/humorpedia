import { useCallback, useEffect, useState } from 'react';
import { Check, ExternalLink, Loader2, Mail, PencilLine, Search, X } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { correctionSuggestionsApi } from '../utils/api';

const FILTERS = [
  ['new', 'Новые'],
  ['in_review', 'В работе'],
  ['fixed', 'Исправленные'],
  ['rejected', 'Отклонённые'],
  ['', 'Все'],
];

const STATUS_LABELS = {
  new: 'Новое',
  in_review: 'В работе',
  fixed: 'Исправлено',
  rejected: 'Отклонено',
};

function SuggestionCard({ item, busy, onReview }) {
  const [comment, setComment] = useState(item.admin_comment || '');
  const emailSubject = encodeURIComponent(`Предложение исправления на Humorpedia: ${item.page_title}`);
  const isOpen = item.status === 'new' || item.status === 'in_review';

  return (
    <Card>
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold">{item.page_title}</h2>
              <Badge variant={item.status === 'new' ? 'default' : 'secondary'}>
                {STATUS_LABELS[item.status] || item.status}
              </Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {item.section} · {new Date(item.created_at).toLocaleString('ru-RU')}
            </p>
          </div>
          <Button variant="outline" size="sm" asChild>
            <a href={item.page_path} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-2 h-4 w-4" />Открыть страницу
            </a>
          </Button>
        </div>

        <div className="rounded-md bg-muted p-4 whitespace-pre-wrap text-sm">{item.message}</div>

        {item.source && (
          <div className="text-sm">
            <span className="font-medium">Источник: </span>
            {/^https?:\/\//i.test(item.source) ? (
              <a className="text-blue-600 hover:underline break-all" href={item.source} target="_blank" rel="noopener noreferrer">
                {item.source}
              </a>
            ) : item.source}
          </div>
        )}

        {isOpen ? (
          <div className="space-y-2">
            <label htmlFor={`comment-${item._id}`} className="text-sm font-medium">Комментарий редакции</label>
            <Textarea
              id={`comment-${item._id}`}
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              maxLength={2000}
              rows={2}
              placeholder="Внутренняя заметка или текст ответа"
            />
          </div>
        ) : item.admin_comment ? (
          <div className="rounded-md border p-3 text-sm whitespace-pre-wrap">
            <span className="font-medium">Комментарий редакции: </span>{item.admin_comment}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {isOpen && item.status === 'new' && (
            <Button size="sm" variant="outline" disabled={busy} onClick={() => onReview(item._id, 'in_review', comment)}>
              <Search className="mr-2 h-4 w-4" />Взять в работу
            </Button>
          )}
          {isOpen && (
            <Button size="sm" disabled={busy} onClick={() => onReview(item._id, 'fixed', comment)}>
              <Check className="mr-2 h-4 w-4" />Исправлено
            </Button>
          )}
          {isOpen && (
            <Button size="sm" variant="destructive" disabled={busy} onClick={() => onReview(item._id, 'rejected', comment)}>
              <X className="mr-2 h-4 w-4" />Отклонить
            </Button>
          )}
          {item.email && (
            <Button size="sm" variant="outline" asChild>
              <a href={`mailto:${item.email}?subject=${emailSubject}`}>
                <Mail className="mr-2 h-4 w-4" />Ответить: {item.email}
              </a>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function CorrectionSuggestionsPage() {
  const [status, setStatus] = useState('new');
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await correctionSuggestionsApi.list({ status: status || undefined, limit: 100 });
      setData(response.data);
    } catch {
      setError('Не удалось загрузить предложения');
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => { load(); }, [load]);

  const review = async (id, nextStatus, adminComment) => {
    setBusyId(id);
    setError('');
    try {
      await correctionSuggestionsApi.review(id, { status: nextStatus, admin_comment: adminComment || null });
      await load();
    } catch {
      setError('Не удалось обновить предложение');
    } finally {
      setBusyId('');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Предложения правок</h1>
        <p className="mt-1 text-muted-foreground">Обращения читателей, привязанные к страницам сайта</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map(([value, label]) => (
          <Button key={label} variant={status === value ? 'default' : 'outline'} size="sm" onClick={() => setStatus(value)}>
            {label}
          </Button>
        ))}
      </div>

      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <div className="flex h-48 items-center justify-center"><Loader2 className="h-8 w-8 animate-spin" /></div>
      ) : data.items?.length ? (
        <div className="space-y-4">
          {data.items.map((item) => (
            <SuggestionCard key={item._id} item={item} busy={busyId === item._id} onReview={review} />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border bg-white py-12 text-center text-muted-foreground">
          <PencilLine className="mx-auto mb-3 h-10 w-10 opacity-40" />
          Предложений с таким статусом нет
        </div>
      )}
    </div>
  );
}
