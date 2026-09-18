import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { publicApi } from '../utils/api';
import FittedImage from '@/components/FittedImage';

export default function RelatedArticles({ contentType, contentId, className = '' }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    if (!contentType || !contentId) {
      setLoading(false);
      return undefined;
    }
    setLoading(true);
    publicApi.getRecommendations(contentType, contentId)
      .then((response) => active && setItems(response.data.items || []))
      .catch(() => active && setItems([]))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [contentType, contentId]);

  if (loading) {
    return (
      <div className={`flex justify-center py-6 ${className}`} aria-label="Загрузка рекомендаций">
        <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
      </div>
    );
  }
  if (!items.length) return null;

  return (
    <section className={`mt-10 ${className}`} aria-labelledby={`related-${contentType}-${contentId}`}>
      <h2 id={`related-${contentType}-${contentId}`} className="text-2xl font-bold text-gray-900 mb-5">
        Читайте также
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <Link
            key={item.id}
            to={item.url}
            className="group overflow-hidden rounded-xl border bg-white transition hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
          >
            <FittedImage
              src={item.cover_image?.url}
              fallbackKey={item.slug || item.id}
              alt=""
              className="aspect-[16/9] w-full"
            />
            <div className="p-4">
              <h3 className="font-semibold leading-snug text-gray-900 group-hover:text-blue-700">
                {item.title}
              </h3>
              {item.excerpt && <p className="mt-2 text-sm text-gray-600 line-clamp-2">{item.excerpt}</p>}
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
