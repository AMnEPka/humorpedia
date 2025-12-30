import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { MapPin, Loader2, ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import publicApi from '../utils/api';
import { cn } from '@/lib/utils';

const LETTERS = 'АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯ'.split('');

export default function CitiesListPage() {
  const [cities, setCities] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();

  const page = parseInt(searchParams.get('page') || '1');
  const search = searchParams.get('search') || '';
  const letter = searchParams.get('letter') || '';
  const limit = 24;

  useEffect(() => {
    const fetchCities = async () => {
      setLoading(true);
      try {
        const params = {
          skip: (page - 1) * limit,
          limit,
          status: 'published',
          ...(search && { search }),
          ...(letter && { letter })
        };
        const response = await publicApi.getCities(params);
        setCities(response.data.items || []);
        setTotal(response.data.total || 0);
      } catch (error) {
        console.error('Error fetching cities:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchCities();
  }, [page, search, letter]);

  const handleLetterClick = (l) => {
    const params = new URLSearchParams(searchParams);
    if (l === letter) {
      params.delete('letter');
    } else {
      params.set('letter', l);
    }
    params.set('page', '1');
    setSearchParams(params);
  };

  const handleSearch = (value) => {
    const params = new URLSearchParams(searchParams);
    if (value) {
      params.set('search', value);
    } else {
      params.delete('search');
    }
    params.set('page', '1');
    setSearchParams(params);
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
          <MapPin className="h-8 w-8 text-blue-600" />
          География
        </h1>
        <p className="mt-2 text-lg text-gray-600">
          Города, подарившие миру звёзд юмора
        </p>
      </div>

      {/* Filters */}
      <div className="mb-6 space-y-4">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            type="search"
            placeholder="Поиск города..."
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Alphabet filter */}
        <div className="flex flex-wrap gap-1">
          {LETTERS.map((l) => (
            <button
              key={l}
              onClick={() => handleLetterClick(l)}
              className={cn(
                'w-8 h-8 text-sm font-medium rounded transition-colors',
                letter === l
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
              )}
            >
              {l}
            </button>
          ))}
          {letter && (
            <button
              onClick={() => handleLetterClick(letter)}
              className="px-3 h-8 text-sm font-medium rounded bg-red-100 text-red-600 hover:bg-red-200"
            >
              Сбросить
            </button>
          )}
        </div>
      </div>

      {/* Results count */}
      <p className="text-sm text-gray-500 mb-4">
        Найдено: {total} {total === 1 ? 'город' : total < 5 ? 'города' : 'городов'}
      </p>

      {/* Cities grid */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      ) : cities.length === 0 ? (
        <div className="text-center py-16">
          <MapPin className="h-12 w-12 mx-auto text-gray-300 mb-4" />
          <p className="text-gray-500">Города не найдены</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {cities.map((city) => (
            <Link
              key={city._id}
              to={`/city/${city.slug}`}
              className="group block"
            >
              <div className="bg-white rounded-lg shadow-sm border overflow-hidden hover:shadow-md transition-shadow">
                {/* Poster */}
                <div className="aspect-video bg-gradient-to-br from-blue-500 to-blue-700 relative overflow-hidden">
                  {city.poster?.url ? (
                    <img
                      src={city.poster.url}
                      alt={city.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <MapPin className="h-12 w-12 text-white/50" />
                    </div>
                  )}
                </div>

                {/* Info */}
                <div className="p-4">
                  <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
                    {city.name || city.title}
                  </h3>
                  {city.description && (
                    <p className="mt-1 text-sm text-gray-500 line-clamp-2">
                      {city.description}
                    </p>
                  )}
                  {city.rating > 0 && (
                    <div className="mt-2 flex items-center gap-1 text-sm text-yellow-600">
                      <span>★</span>
                      <span>{city.rating.toFixed(1)}</span>
                    </div>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-8">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => {
              const params = new URLSearchParams(searchParams);
              params.set('page', String(page - 1));
              setSearchParams(params);
            }}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-gray-500">
            Страница {page} из {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
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
    </div>
  );
}
