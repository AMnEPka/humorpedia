import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import publicApi from '../utils/api';
import NewsCard from '../components/NewsCard';

export default function NewsListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [news, setNews] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  
  const page = parseInt(searchParams.get('page') || '1');
  const limit = 12;

  useEffect(() => {
    const fetchNews = async () => {
      setLoading(true);
      try {
        const res = await publicApi.getNews({ 
          page, 
          limit,
          sort: '-published_at' 
        });
        setNews(res.data.items || []);
        setTotal(res.data.total || 0);
      } catch (err) {
        console.error('Error fetching news:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchNews();
  }, [page]);

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm text-gray-500">
          <li><Link to="/" className="hover:text-blue-600">Главная</Link></li>
          <li>/</li>
          <li className="text-gray-900">Новости</li>
        </ol>
      </nav>

      <h1 className="text-3xl font-bold text-gray-900 mb-8">Новости</h1>

      {loading ? (
        <div className="flex items-center justify-center min-h-[40vh]">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      ) : news.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p>Нет новостей</p>
        </div>
      ) : (
        <>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {news.map((item) => (
              <NewsCard key={item.id} news={item} />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-8">
              <Button
                variant="outline"
                size="icon"
                disabled={page <= 1}
                onClick={() => setSearchParams({ page: page - 1 })}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="px-4 py-2 text-sm">
                Страница {page} из {totalPages}
              </span>
              <Button
                variant="outline"
                size="icon"
                disabled={page >= totalPages}
                onClick={() => setSearchParams({ page: page + 1 })}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
