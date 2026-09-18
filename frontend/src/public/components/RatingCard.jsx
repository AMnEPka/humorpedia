import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import useRating from '../hooks/useRating';

const SCORES = [
  { value: 1, emoji: '😡' },
  { value: 2, emoji: '😠' },
  { value: 3, emoji: '😟' },
  { value: 4, emoji: '😕' },
  { value: 5, emoji: '😐' },
  { value: 6, emoji: '🙂' },
  { value: 7, emoji: '😊' },
  { value: 8, emoji: '😃' },
  { value: 9, emoji: '😄' },
  { value: 10, emoji: '🤩' },
];

export default function RatingCard({ entityType, entityId, className = '' }) {
  const { rating, loading, submitting, error, submitScore } = useRating(entityType, entityId);
  const hasAverage = rating.average !== null && Number.isFinite(Number(rating.average));
  const disabled = loading || submitting || !entityId;

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg">Оценка</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-center text-sm text-gray-600" aria-live="polite">
          {loading ? (
            'Загружаем рейтинг…'
          ) : hasAverage ? (
            <>
              <span className="font-semibold text-gray-900">{Number(rating.average).toFixed(1)} / 10</span>
              {rating.votes_label && <span> ({rating.votes_label})</span>}
            </>
          ) : (
            'Пока нет оценок'
          )}
        </div>

        <div className="grid grid-cols-5 gap-1 sm:grid-cols-10 lg:grid-cols-5 xl:grid-cols-10" aria-label="Оценка от 1 до 10">
          {SCORES.map(({ value, emoji }) => {
            const selected = rating.my_score === value;
            return (
              <button
                key={value}
                type="button"
                aria-label={`Поставить оценку ${value} из 10`}
                aria-pressed={selected}
                disabled={disabled}
                onClick={() => submitScore(value)}
                className={`flex min-h-11 flex-col items-center justify-center rounded-md border px-1 py-1 text-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${selected ? 'border-blue-600 bg-blue-50' : 'border-gray-200 bg-white hover:border-blue-400 hover:bg-blue-50/50'}`}
              >
                <span aria-hidden="true">{emoji}</span>
                <span className="text-[10px] leading-none text-gray-600">{value}</span>
              </button>
            );
          })}
        </div>

        <div className="min-h-5 text-center text-sm" aria-live="polite">
          {submitting ? (
            <span className="text-gray-500">Сохраняем оценку…</span>
          ) : rating.my_score !== null ? (
            <span className="font-medium text-gray-700">Ваша оценка: {rating.my_score}</span>
          ) : null}
        </div>

        {error && <p className="text-center text-sm text-red-600" role="alert">{error}</p>}
      </CardContent>
    </Card>
  );
}
