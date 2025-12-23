import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, Clock, MessageCircle, Share2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';
import publicApi from '../utils/api';
import { ModuleList } from '../components/ModuleRenderer';

export default function NewsDetailPage() {
  const { slug } = useParams();
  const [news, setNews] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchNews = async () => {
      setLoading(true);
      try {
        const res = await publicApi.getNewsItem(slug);
        setNews(res.data);
      } catch (err) {
        setError('Новость не найдена');
      } finally {
        setLoading(false);
      }
    };
    fetchNews();
  }, [slug]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !news) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
        <p className="text-gray-500 mb-4">{error || 'Новость не найдена'}</p>
        <Button asChild>
          <Link to="/news">Вернуться к списку</Link>
        </Button>
      </div>
    );
  }

  const formattedDate = news.published_at 
    ? formatDistanceToNow(new Date(news.published_at), { addSuffix: true, locale: ru })
    : news.created_at
    ? formatDistanceToNow(new Date(news.created_at), { addSuffix: true, locale: ru })
    : '';

  return (
    <article className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm text-gray-500">
          <li><Link to="/" className="hover:text-blue-600">Главная</Link></li>
          <li>/</li>
          <li><Link to="/news" className="hover:text-blue-600">Новости</Link></li>
          <li>/</li>
          <li className="text-gray-900 truncate max-w-[200px]">{news.title}</li>
        </ol>
      </nav>

      {/* Header */}
      <header className="mb-8">
        <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
          {news.title}
        </h1>
        
        <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500">
          {formattedDate && (
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              <span>{formattedDate}</span>
            </div>
          )}
          <div className="flex items-center gap-2">
            <MessageCircle className="h-4 w-4" />
            <span>{news.comments_count || 0} комментариев</span>
          </div>
        </div>

        {news.tags?.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {news.tags.map((tag, i) => (
              <Badge key={i} variant="secondary">{tag}</Badge>
            ))}
          </div>
        )}
      </header>

      {/* Cover image */}
      {news.cover_image?.url && (
        <div className="mb-8 rounded-xl overflow-hidden">
          <img 
            src={news.cover_image.url} 
            alt={news.title}
            className="w-full h-auto"
          />
        </div>
      )}

      {/* Excerpt */}
      {news.excerpt && (
        <p className="text-lg text-gray-600 mb-8 font-medium">
          {news.excerpt}
        </p>
      )}

      {/* Modules content */}
      {news.modules && news.modules.length > 0 ? (
        <ModuleList modules={news.modules} />
      ) : news.content ? (
        /* Fallback to HTML content */
        <div 
          className="prose prose-lg prose-blue max-w-none"
          dangerouslySetInnerHTML={{ __html: news.content }}
        />
      ) : (
        <p className="text-gray-500">Содержимое отсутствует</p>
      )}

      {/* Share */}
      <div className="mt-12 pt-8 border-t">
        <Button 
          variant="outline" 
          onClick={() => {
            if (navigator.share) {
              navigator.share({ url: window.location.href, title: news.title });
            } else {
              navigator.clipboard.writeText(window.location.href);
              alert('Ссылка скопирована!');
            }
          }}
        >
          <Share2 className="mr-2 h-4 w-4" /> Поделиться
        </Button>
      </div>
    </article>
  );
}
