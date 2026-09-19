import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import PersonSelector from '../components/PersonSelector';
import { contentApi, getErrorMessage } from '../utils/api';

const PAGE_SIZE = 50;

const statusLabels = {
  pending: 'Ожидают решения',
  confirmed: 'Подтверждены',
  rejected: 'Отклонены',
};

const reasonLabels = {
  name_only: 'Совпадение только по имени',
  slug_conflict: 'Конфликт slug',
  slug_unresolved: 'Страница из исходной ссылки не найдена',
};

function personTitle(person) {
  return person?.full_name || person?.name || person?.title || person?.slug || '';
}

function teamTitle(team) {
  return team?.name || team?.title || team?.slug || 'Команда не найдена';
}

function membershipYears(membership) {
  const from = membership?.from_year;
  const to = membership?.to_year;
  if (from && to && from !== to) return `${from}–${to}`;
  return from || to || '';
}

function reviewId(row) {
  return row._id || row.id || row.membership?._id || row.membership?.id;
}

function ReviewCard({ row, busy, onReview }) {
  const [choosing, setChoosing] = useState(false);
  const membership = row.membership || {};
  const team = row.team || {};
  const currentPerson = row.current_person || membership.person || null;
  const suggestedPerson = row.suggested_person || row.person || null;
  const sourcePerson = row.source_person || null;
  const roles = (membership.roles || []).join(', ');
  const years = membershipYears(membership);
  const sourceSlug = membership.person_slug || membership.source_slug || row.source_slug;
  const id = reviewId(row);
  const teamId = team._id || team.id;
  const personLabel = row.review_status === 'pending' ? 'Предложенная страница' : 'Страница человека';

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="text-lg font-semibold">{membership.person_name || personTitle(currentPerson) || 'Имя не указано'}</div>
            <div>
              Команда:{' '}
              {teamId ? <Link className="text-blue-700 underline" to={`/admin/teams/${teamId}`}>{teamTitle(team)}</Link> : teamTitle(team)}
            </div>
            {suggestedPerson ? (
              <div>
                {personLabel}:{' '}
                <Link className="text-blue-700 underline" to={`/admin/people/${suggestedPerson._id || suggestedPerson.id}`}>
                  {personTitle(suggestedPerson)}
                </Link>
              </div>
            ) : <div className="text-amber-800">Предложенная страница не найдена</div>}
            {currentPerson && currentPerson !== suggestedPerson && (
              <div>Текущая страница: {personTitle(currentPerson)}</div>
            )}
            {sourcePerson && (
              <div>
                Страница по исходной ссылке:{' '}
                <Link className="text-blue-700 underline" to={`/admin/people/${sourcePerson._id || sourcePerson.id}`}>
                  {personTitle(sourcePerson)}
                </Link>
              </div>
            )}
            <div className="text-sm text-gray-600">
              Причина: {reasonLabels[row.reason] || row.reason || 'не указана'}
              {roles && ` · Роли: ${roles}`}
              {years && ` · Годы: ${years}`}
              {sourceSlug && ` · Source slug: ${sourceSlug}`}
            </div>
            <div className="text-sm">
              Статус проверки: {statusLabels[row.review_status] || row.review_status}
              {' · '}{row.public_active ? 'Связь сейчас публична' : 'Связь сейчас не показывается публично'}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestedPerson && row.review_status !== 'confirmed' && (
              <Button disabled={busy || !id} onClick={() => onReview(id, { action: 'confirm' })}>
                {row.review_status === 'rejected' ? 'Восстановить связь' : 'Подтвердить'}
              </Button>
            )}
            <Button variant="outline" disabled={busy || !id} onClick={() => setChoosing(value => !value)}>
              {choosing ? 'Скрыть выбор' : 'Выбрать другого'}
            </Button>
            {row.review_status !== 'rejected' && (
              <Button
                variant="outline"
                className="text-red-700"
                disabled={busy || !id}
                onClick={() => onReview(id, { action: 'reject' })}
              >
                Некорректная связь — отвязать
              </Button>
            )}
          </div>
        </div>
        {choosing && (
          <div className="max-w-xl border-t pt-3">
            <PersonSelector
              value={[]}
              placeholder="Найти правильную страницу человека…"
              onChange={(ids) => {
                const personId = ids[ids.length - 1];
                if (personId) onReview(id, { action: 'link', person_id: personId });
              }}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function MembershipLinksPage() {
  const [data, setData] = useState({ items: [], total: 0, skip: 0, limit: PAGE_SIZE, counts: {} });
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('pending');
  const [reason, setReason] = useState('');
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await contentApi.listMembershipLinkReviews({
        q: search || undefined,
        status,
        reason: reason || undefined,
        skip,
        limit: PAGE_SIZE,
      });
      setData(response.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось загрузить связи состава'));
    } finally {
      setLoading(false);
    }
  }, [reason, search, skip, status]);

  useEffect(() => { load(); }, [load, version]);

  const review = async (id, payload) => {
    setBusyId(id);
    setError('');
    try {
      await contentApi.reviewMembershipLink(id, payload);
      setVersion(value => value + 1);
    } catch (err) {
      setError(getErrorMessage(err, 'Не удалось сохранить решение'));
    } finally {
      setBusyId('');
    }
  };

  const counts = data.counts || {};
  const total = data.total || 0;

  return (
    <div className="space-y-5">
      <Link className="text-blue-700 underline" to="/admin/teams">← Команды</Link>
      <div>
        <h1 className="text-3xl font-bold">Проверка связей состава</h1>
        <p className="mt-2 text-muted-foreground">
          Существующие связи со статусом «Ожидает решения» остаются публичными до решения.
          При отклонении имя участника сохранится в составе, но ссылка на страницу человека будет удалена.
        </p>
      </div>

      {error && <div role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</div>}

      <Card>
        <CardContent className="pt-6 space-y-4">
          <div className="flex flex-col gap-3 md:flex-row">
            <Input
              aria-label="Поиск связи"
              placeholder="Имя человека или команда"
              value={query}
              onChange={(event) => { setQuery(event.target.value); setSkip(0); }}
            />
            <select
              aria-label="Статус проверки"
              className="h-10 rounded-md border border-input bg-background px-3 text-sm"
              value={status}
              onChange={(event) => { setStatus(event.target.value); setSkip(0); }}
            >
              <option value="all">Все статусы</option>
              {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <select
              aria-label="Причина проверки"
              className="h-10 rounded-md border border-input bg-background px-3 text-sm"
              value={reason}
              onChange={(event) => { setReason(event.target.value); setSkip(0); }}
            >
              <option value="">Все причины</option>
              {Object.entries(reasonLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600">
            <span>Всего: {total}</span>
            <span>Ожидают: {counts.pending ?? 0}</span>
            <span>Подтверждены: {counts.confirmed ?? 0}</span>
            <span>Отклонены: {counts.rejected ?? 0}</span>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex justify-center py-8" aria-label="Загрузка"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : (
        <>
          <div className="space-y-3">
            {(data.items || []).map(row => (
              <ReviewCard key={reviewId(row)} row={row} busy={busyId === reviewId(row)} onReview={review} />
            ))}
          </div>
          {!data.items?.length && <p>Связей по выбранным условиям нет.</p>}
        </>
      )}

      <div className="flex items-center gap-3">
        <Button variant="outline" disabled={loading || skip === 0} onClick={() => setSkip(value => Math.max(0, value - PAGE_SIZE))}>Назад</Button>
        <span className="text-sm text-gray-600">{total ? `${skip + 1}–${Math.min(skip + PAGE_SIZE, total)} из ${total}` : '0 записей'}</span>
        <Button variant="outline" disabled={loading || skip + PAGE_SIZE >= total} onClick={() => setSkip(value => value + PAGE_SIZE)}>Далее</Button>
      </div>
    </div>
  );
}
