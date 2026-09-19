import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarDays, Newspaper } from 'lucide-react';
import { publicApi } from '../utils/api';
import FittedImage from '@/components/FittedImage';
import { contentImageUrl } from '@/utils/media';

function formatPublishedAt(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

export default function RelatedNews({ entityType, entityId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    if (!entityType || !entityId) {
      setItems([]);
      setLoading(false);
      return undefined;
    }

    setItems([]);
    setLoading(true);
    publicApi.getRelatedNews(entityType, entityId)
      .then(({ data }) => {
        if (active) setItems(data?.enabled && Array.isArray(data.items) ? data.items.slice(0, 3) : []);
      })
      .catch(() => {
        if (active) setItems([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [entityType, entityId]);

  if (loading || items.length === 0) return null;

  return (
    <section className="overflow-hidden rounded-xl border bg-white" aria-labelledby={`related-news-${entityType}-${entityId}`}>
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <Newspaper className="h-5 w-5 text-blue-600" aria-hidden="true" />
        <h2 id={`related-news-${entityType}-${entityId}`} className="text-lg font-semibold text-gray-900">
          Свежие новости
        </h2>
      </div>
      <div className="divide-y">
        {items.map((item) => {
          const publishedAt = formatPublishedAt(item.published_at);
          return (
            <Link
              key={item.id || item.slug}
              to={`/news/${item.slug}`}
              className="group flex gap-3 p-3 transition-colors hover:bg-blue-50/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-600 sm:p-4"
            >
              <FittedImage
                src={contentImageUrl(item, item.cover_image)}
                fallbackKey={item.slug || item.id}
                alt=""
                className="h-16 w-20 flex-none rounded-md sm:h-20 sm:w-28"
                fit="cover"
              />
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold leading-snug text-gray-900 transition-colors group-hover:text-blue-700 line-clamp-2">
                  {item.title}
                </h3>
                {publishedAt && (
                  <div className="mt-1 flex items-center gap-1 text-xs text-gray-500">
                    <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />
                    <time dateTime={item.published_at}>{publishedAt}</time>
                  </div>
                )}
                {item.excerpt && <p className="mt-1 text-sm text-gray-600 line-clamp-2">{item.excerpt}</p>}
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
