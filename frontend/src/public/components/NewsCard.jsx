import { Link } from 'react-router-dom';
import { MessageCircle, Clock } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';

export default function NewsCard({ news, compact = false }) {
  const formattedDate = news.published_at 
    ? formatDistanceToNow(new Date(news.published_at), { addSuffix: true, locale: ru })
    : '';

  if (compact) {
    return (
      <Link 
        to={`/news/${news.slug}`}
        className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-100 transition-colors group"
      >
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-gray-900 group-hover:text-blue-600 transition-colors line-clamp-2">
            {news.title}
          </h3>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formattedDate}
            </span>
            {news.comments_count > 0 && (
              <span className="flex items-center gap-1">
                <MessageCircle className="h-3 w-3" />
                {news.comments_count}
              </span>
            )}
          </div>
        </div>
      </Link>
    );
  }

  return (
    <article className="bg-white rounded-xl shadow-sm border overflow-hidden hover:shadow-md transition-shadow">
      {news.image && (
        <Link to={`/news/${news.slug}`}>
          <img 
            src={news.image} 
            alt={news.title}
            className="w-full h-48 object-cover"
          />
        </Link>
      )}
      <div className="p-5">
        <Link to={`/news/${news.slug}`}>
          <h3 className="text-lg font-semibold text-gray-900 hover:text-blue-600 transition-colors line-clamp-2">
            {news.title}
          </h3>
        </Link>
        {news.excerpt && (
          <p className="mt-2 text-gray-600 text-sm line-clamp-2">{news.excerpt}</p>
        )}
        <div className="flex items-center gap-4 mt-4 text-sm text-gray-500">
          <span className="flex items-center gap-1">
            <Clock className="h-4 w-4" />
            {formattedDate}
          </span>
          <span className="flex items-center gap-1">
            <MessageCircle className="h-4 w-4" />
            {news.comments_count || 0}
          </span>
        </div>
      </div>
    </article>
  );
}
