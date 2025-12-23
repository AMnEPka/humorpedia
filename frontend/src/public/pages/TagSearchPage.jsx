import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, Tag as TagIcon } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import publicApi from '../utils/api';

const contentTypeLabels = {
  person: 'Люди',
  team: 'Команды',
  show: 'Шоу',
  article: 'Статьи',
  news: 'Новости',
  wiki: 'Вики',
  section: 'Разделы',
  quiz: 'Квизы'
};

const getItemPath = (item, type) => {
  if (type === 'section') return item.full_path;
  if (type === 'person') return `/people/${item.slug || item._id}`;
  if (type === 'team') return `/teams/kvn/${item.slug || item._id}`;
  if (type === 'show') return `/shows/${item.slug || item._id}`;
  if (type === 'article') return `/articles/${item.slug || item._id}`;
  if (type === 'news') return `/news/${item.slug || item._id}`;
  if (type === 'quiz') return `/quizzes/${item.slug || item._id}`;
  return '#';
};

const getItemTitle = (item, type) => {
  if (type === 'person') return item.full_name || item.title;
  if (type === 'team' || type === 'show') return item.name || item.title;
  return item.title;
};

export default function TagSearchPage() {
  const { tag } = useParams();
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (tag) {
      loadTagResults();
    }
  }, [tag]);

  const loadTagResults = async () => {
    setLoading(true);
    try {
      const res = await publicApi.searchByTag(tag);
      setResults(res.data);
    } catch (err) {
      console.error('Tag search error:', err);
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!results || results.total === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center">
          <TagIcon className="h-12 w-12 mx-auto mb-4 text-gray-400" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Тег: {tag}</h1>
          <p className="text-gray-500 mb-4">Контент с этим тегом не найден</p>
          <Button asChild>
            <Link to="/">Вернуться на главную</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <TagIcon className="h-8 w-8 text-blue-600" />
          <h1 className="text-3xl font-bold text-gray-900">{tag}</h1>
        </div>
        <p className="text-gray-600">
          Найдено материалов: <strong>{results.total}</strong>
        </p>
      </div>

      {/* Results by type */}
      <div className="space-y-6">
        {Object.entries(results.results).map(([type, data]) => (
          <Card key={type}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {contentTypeLabels[type] || type}
                <Badge variant="secondary">{data.count}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-4">
                {data.items.map((item) => (
                  <Link
                    key={item._id}
                    to={getItemPath(item, type)}
                    className="block p-4 rounded-lg border hover:bg-gray-50 transition-colors"
                  >
                    <h3 className="font-medium text-gray-900 mb-2">
                      {getItemTitle(item, type)}
                    </h3>
                    {item.excerpt && (
                      <p className="text-sm text-gray-600 line-clamp-2">
                        {item.excerpt}
                      </p>
                    )}
                    {item.description && (
                      <p className="text-sm text-gray-600 line-clamp-2">
                        {item.description}
                      </p>
                    )}
                    {item.tags && item.tags.length > 1 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {item.tags.filter(t => t !== tag).slice(0, 3).map((t) => (
                          <Badge key={t} variant="outline" className="text-xs">
                            {t}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
