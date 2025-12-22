import { Link } from 'react-router-dom';
import { Star, MessageCircle, Clock } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';

export default function ArticleCard({ article, featured = false }) {
  const formattedDate = article.published_at 
    ? formatDistanceToNow(new Date(article.published_at), { addSuffix: true, locale: ru })
    : '';

  if (featured) {
    return (
      <article className="bg-white rounded-xl shadow-sm border overflow-hidden hover:shadow-lg transition-all group">
        <div className="md:flex">
          {article.image && (
            <Link to={`/articles/${article.slug}`} className="md:w-2/5 flex-shrink-0">
              <img 
                src={article.image} 
                alt={article.title}
                className="w-full h-56 md:h-full object-cover group-hover:scale-105 transition-transform duration-300"
              />
            </Link>
          )}
          <div className="p-6 flex flex-col justify-center">
            <Link to={`/articles/${article.slug}`}>
              <h3 className="text-xl font-bold text-gray-900 group-hover:text-blue-600 transition-colors">
                {article.title}
              </h3>
            </Link>
            {article.excerpt && (
              <p className="mt-3 text-gray-600 line-clamp-3">{article.excerpt}</p>
            )}
            <div className="flex items-center gap-4 mt-4 text-sm text-gray-500">
              <span className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                {formattedDate}
              </span>
              {article.rating && (
                <span className="flex items-center gap-1 text-amber-500">
                  <Star className="h-4 w-4 fill-current" />
                  {article.rating.toFixed(1)}
                </span>
              )}
              <span className="flex items-center gap-1">
                <MessageCircle className="h-4 w-4" />
                {article.comments_count || 0}
              </span>
            </div>
          </div>
        </div>
      </article>
    );
  }

  return (
    <article className="bg-white rounded-xl shadow-sm border overflow-hidden hover:shadow-md transition-shadow group">
      {article.image && (
        <Link to={`/articles/${article.slug}`} className="block overflow-hidden">
          <img 
            src={article.image} 
            alt={article.title}
            className="w-full h-48 object-cover group-hover:scale-105 transition-transform duration-300"
          />
        </Link>
      )}
      <div className="p-5">
        <Link to={`/articles/${article.slug}`}>
          <h3 className="text-lg font-semibold text-gray-900 group-hover:text-blue-600 transition-colors line-clamp-2">
            {article.title}
          </h3>
        </Link>
        {article.excerpt && (
          <p className="mt-2 text-gray-600 text-sm line-clamp-2">{article.excerpt}</p>
        )}
        <div className="flex items-center gap-4 mt-4 text-sm text-gray-500">
          <span className="flex items-center gap-1">
            <Clock className="h-4 w-4" />
            {formattedDate}
          </span>
          {article.rating && (
            <span className="flex items-center gap-1 text-amber-500">
              <Star className="h-4 w-4 fill-current" />
              {article.rating.toFixed(1)}
            </span>
          )}
        </div>
      </div>
    </article>
  );
}
