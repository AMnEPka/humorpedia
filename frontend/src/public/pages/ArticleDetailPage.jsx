import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, Clock, MessageCircle, Share2, Star, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';
import publicApi from '../utils/api';
import { ModuleList } from '../components/ModuleRenderer';

export default function ArticleDetailPage() {
  const { slug } = useParams();
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchArticle = async () => {
      setLoading(true);
      try {
        const res = await publicApi.getArticle(slug);
        setArticle(res.data);
      } catch (err) {
        setError('Статья не найдена');
      } finally {
        setLoading(false);
      }
    };
    fetchArticle();
  }, [slug]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !article) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
        <p className="text-gray-500 mb-4">{error || 'Статья не найдена'}</p>
        <Button asChild>
          <Link to="/articles">Вернуться к списку</Link>
        </Button>
      </div>
    );
  }

  const formattedDate = article.published_at 
    ? formatDistanceToNow(new Date(article.published_at), { addSuffix: true, locale: ru })
    : '';

  return (
    <article className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm text-gray-500">
          <li><Link to="/" className="hover:text-blue-600">Главная</Link></li>
          <li>/</li>
          <li><Link to="/articles" className="hover:text-blue-600">Статьи</Link></li>
          <li>/</li>
          <li className="text-gray-900 truncate max-w-[200px]">{article.title}</li>
        </ol>
      </nav>

      {/* Header */}
      <header className="mb-8">
        <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
          {article.title}
        </h1>
        
        <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500">
          {article.author && (
            <div className="flex items-center gap-2">
              <User className="h-4 w-4" />
              <span>{article.author}</span>
            </div>
          )}
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            <span>{formattedDate}</span>
          </div>
          {article.rating && (
            <div className="flex items-center gap-1 text-amber-500">
              <Star className="h-4 w-4 fill-current" />
              <span>{article.rating.toFixed(1)}</span>
            </div>
          )}
          <div className="flex items-center gap-2">
            <MessageCircle className="h-4 w-4" />
            <span>{article.comments_count || 0} комментариев</span>
          </div>
        </div>

        {article.tags?.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {article.tags.map((tag, i) => (
              <Link key={i} to={`/tags/${encodeURIComponent(tag)}`}>
                <Badge variant="secondary" className="cursor-pointer hover:bg-blue-100">
                  {tag}
                </Badge>
              </Link>
            ))}
          </div>
        )}
      </header>

      {/* Featured Image */}
      {article.image && (
        <div className="mb-8 rounded-xl overflow-hidden">
          <img 
            src={article.image} 
            alt={article.title}
            className="w-full h-auto"
          />
        </div>
      )}

      {/* Excerpt */}
      {article.excerpt && (
        <div className="text-xl text-gray-600 mb-8 font-medium leading-relaxed">
          {article.excerpt}
        </div>
      )}

      {/* Modules */}
      {article.modules && article.modules.length > 0 ? (
        <ModuleList modules={article.modules} />
      ) : article.content ? (
        <div 
          className="prose prose-lg prose-blue max-w-none"
          dangerouslySetInnerHTML={{ __html: article.content }}
        />
      ) : null}

      {/* Share */}
      <div className="mt-12 pt-8 border-t">
        <Button 
          variant="outline" 
          onClick={() => {
            if (navigator.share) {
              navigator.share({ url: window.location.href, title: article.title });
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
