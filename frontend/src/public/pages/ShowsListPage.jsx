import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Loader2, ChevronLeft, ChevronRight, Tv } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import publicApi from '../utils/api';

export default function ShowsListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [shows, setShows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  
  const page = parseInt(searchParams.get('page') || '1');
  const limit = 12;

  useEffect(() => {
    const fetchShows = async () => {
      setLoading(true);
      try {
        const res = await publicApi.getShows({ 
          page, 
          limit,
          sort: 'title' 
        });
        setShows(res.data.items || []);
        setTotal(res.data.total || 0);
      } catch (err) {
        console.error('Error fetching shows:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchShows();
  }, [page]);

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm text-gray-500">
          <li><Link to="/" className="hover:text-blue-600">Главная</Link></li>
          <li>/</li>
          <li className="text-gray-900">Шоу</li>
        </ol>
      </nav>

      <h1 className="text-3xl font-bold text-gray-900 mb-8">Шоу и проекты</h1>

      {loading ? (
        <div className="flex items-center justify-center min-h-[40vh]">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      ) : shows.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <Tv className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>Нет шоу</p>
        </div>
      ) : (
        <>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {shows.map((show) => (
              <Link key={show.id} to={`/shows/${show.slug}`}>
                <Card className="overflow-hidden hover:shadow-lg transition-shadow group h-full">
                  <div className="aspect-video bg-gray-100 overflow-hidden">
                    {show.poster ? (
                      <img 
                        src={show.poster} 
                        alt={show.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-blue-50 to-blue-100">
                        <Tv className="h-16 w-16 text-blue-300" />
                      </div>
                    )}
                  </div>
                  <CardContent className="p-5">
                    <h3 className="font-semibold text-lg text-gray-900 group-hover:text-blue-600 transition-colors">
                      {show.title}
                    </h3>
                    {show.channel && (
                      <p className="text-sm text-gray-500 mt-1">{show.channel}</p>
                    )}
                    {show.excerpt && (
                      <p className="text-sm text-gray-600 mt-2 line-clamp-2">{show.excerpt}</p>
                    )}
                  </CardContent>
                </Card>
              </Link>
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
