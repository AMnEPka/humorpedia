import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, Clock, MessageCircle, Share2, Star, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';
import publicApi from '../utils/api';

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
              <Badge key={i} variant="secondary">{tag}</Badge>
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

      {/* Content */}
      <div 
        className="prose prose-lg prose-blue max-w-none"
        dangerouslySetInnerHTML={{ __html: article.content || '' }}
      />

      {/* Modules */}
      {article.modules?.map((module, i) => (
        <div key={i} className="mt-8">
          <ModuleRenderer module={module} />
        </div>
      ))}

      {/* Share */}
      <div className="mt-12 pt-8 border-t">
        <Button variant="outline" onClick={() => navigator.share?.({ url: window.location.href, title: article.title })}>
          <Share2 className="mr-2 h-4 w-4" /> Поделиться
        </Button>
      </div>
    </article>
  );
}

function ModuleRenderer({ module }) {
  switch (module.type) {
    case 'gallery':
      return (
        <div className="not-prose">
          <h3 className="text-xl font-bold mb-4">{module.data?.title || 'Галерея'}</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {module.data?.images?.map((img, i) => (
              <img key={i} src={img.url} alt={img.caption || ''} className="rounded-lg" />
            ))}
          </div>
        </div>
      );
    case 'quote':
      return (
        <blockquote className="border-l-4 border-blue-500 pl-6 my-8 italic text-gray-700">
          {module.data?.text}
          {module.data?.author && (
            <cite className="block mt-2 text-sm text-gray-500 not-italic">— {module.data.author}</cite>
          )}
        </blockquote>
      );
    default:
      return null;
  }
}
