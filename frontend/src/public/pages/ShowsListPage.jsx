import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Loader2, ChevronLeft, ChevronRight, Tv } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import publicApi from '../utils/api';
import { contentImageUrl } from '@/utils/media';
import FittedImage from '@/components/FittedImage';
import ListPageHeader from '../components/ListPageHeader';
import AlphabetFilter from '../components/AlphabetFilter';

export default function ShowsListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [shows, setShows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const letter = searchParams.get('letter') || '';
  
  const page = parseInt(searchParams.get('page') || '1');
  const limit = 12;

  useEffect(() => {
    const fetchShows = async () => {
      setLoading(true);
      try {
        const res = await publicApi.getShows({ 
          skip: (page - 1) * limit,
          limit,
          letter: letter || undefined,
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
  }, [page, letter]);

  const totalPages = Math.ceil(total / limit);

  const handleLetterClick = (nextLetter) => {
    const params = new URLSearchParams(searchParams);
    params.delete('q');
    if (nextLetter) params.set('letter', nextLetter);
    else params.delete('letter');
    params.set('page', '1');
    setSearchParams(params);
  };

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

      <ListPageHeader
        title="Шоу и проекты"
      >
        <AlphabetFilter selectedLetter={letter} onLetterClick={handleLetterClick} />
      </ListPageHeader>

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
              <Link key={show.id} to={`/shows/${show.full_path || show.slug}`}>
                <Card className="overflow-hidden hover:shadow-lg transition-shadow group h-full">
                  <FittedImage
                    src={contentImageUrl(show, show.poster)}
                    fallbackKey={show}
                    alt={show.title}
                    className="aspect-video"
                  />
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
                onClick={() => {
                  const params = new URLSearchParams(searchParams);
                  params.set('page', String(page - 1));
                  setSearchParams(params);
                }}
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
                onClick={() => {
                  const params = new URLSearchParams(searchParams);
                  params.set('page', String(page + 1));
                  setSearchParams(params);
                }}
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
