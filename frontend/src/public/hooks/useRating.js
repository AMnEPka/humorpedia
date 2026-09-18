import { useCallback, useEffect, useState } from 'react';
import publicApi from '../utils/api';

const EMPTY_RATING = {
  average: null,
  votes_label: null,
  my_score: null,
};

export default function useRating(entityType, entityId) {
  const [rating, setRating] = useState(EMPTY_RATING);
  const [loading, setLoading] = useState(Boolean(entityType && entityId));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    setRating(EMPTY_RATING);
    setError('');
    setSubmitting(false);

    if (!entityType || !entityId) {
      setLoading(false);
      setError('Рейтинг временно недоступен');
      return () => { cancelled = true; };
    }

    setLoading(true);
    publicApi.getRating(entityType, entityId)
      .then((response) => {
        if (!cancelled) setRating({ ...EMPTY_RATING, ...response.data });
      })
      .catch(() => {
        if (!cancelled) setError('Не удалось загрузить рейтинг');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [entityType, entityId]);

  const submitScore = useCallback(async (score) => {
    if (!Number.isInteger(score) || score < 1 || score > 10 || !entityType || !entityId) {
      return null;
    }

    setSubmitting(true);
    setError('');
    try {
      const response = await publicApi.putRating(entityType, entityId, score);
      setRating({ ...EMPTY_RATING, ...response.data });
      return response.data;
    } catch {
      setError('Не удалось сохранить оценку. Попробуйте ещё раз');
      return null;
    } finally {
      setSubmitting(false);
    }
  }, [entityType, entityId]);

  return {
    rating,
    loading,
    submitting,
    error,
    submitScore,
  };
}
