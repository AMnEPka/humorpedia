import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { Loader2, Search as SearchIcon } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
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
  if (type === 'team') return `/kvn/teams/${item.slug || item._id}`;
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

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState(false);
  const [searchInput, setSearchInput] = useState(query);
  const [totalResults, setTotalResults] = useState(0);

  useEffect(() => {
    if (query && query.length >= 2) {
      setSearchInput(query); // Синхронизировать input с query из URL
      performSearch(query);
    } else {
      setSearchInput(query || ''); // Обновить input даже если query пустой
    }
  }, [query]);

  const performSearch = async (q) => {
    setLoading(true);
    try {
      const res = await publicApi.search(q);
      setResults(res.data);
      
      // Calculate total
      let total = 0;
      Object.values(res.data).forEach(items => {
        total += Array.isArray(items) ? items.length : 0;
      });
      setTotalResults(total);
    } catch (err) {
      console.error('Search error:', err);
      setResults({});
      setTotalResults(0);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchInput.trim().length >= 2) {
      setSearchParams({ q: searchInput.trim() });
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Search Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">Поиск</h1>
        
        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            type="search"
            placeholder="Введите поисковый запрос..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="flex-1"
          />
          <Button type="submit">
            <SearchIcon className="h-4 w-4 mr-2" />
            Найти
          </Button>
        </form>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      )}

      {/* No query */}
      {!loading && !query && (
        <div className="text-center py-12 text-gray-500">
          <SearchIcon className="h-12 w-12 mx-auto mb-4 text-gray-400" />
          <p>Введите запрос для поиска</p>
        </div>
      )}

      {/* Results */}
      {!loading && query && (
        <div>
          {totalResults === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p>Ничего не найдено по запросу "{query}"</p>
            </div>
          ) : (
            <div className="space-y-6">
              <p className="text-sm text-gray-600">
                Найдено результатов: <strong>{totalResults}</strong>
              </p>

              {Object.entries(results).map(([type, items]) => (
                <Card key={type}>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      {contentTypeLabels[type] || type}
                      <Badge variant="secondary">{items.length}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {items.map((item) => (
                        <Link
                          key={item._id}
                          to={getItemPath(item, type)}
                          className="block p-3 rounded-lg border hover:bg-gray-50 transition-colors"
                        >
                          <h3 className="font-medium text-gray-900 mb-1">
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
                          {item.tags && item.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {item.tags.slice(0, 3).map((tag) => (
                                <Badge key={tag} variant="outline" className="text-xs">
                                  {tag}
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
          )}
        </div>
      )}
    </div>
  );
}
