import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { MapPin, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import publicApi from '../utils/api';
import FittedImage from '@/components/FittedImage';
import { contentImageUrl } from '@/utils/media';
import ListPageHeader from '../components/ListPageHeader';
import AlphabetFilter from '../components/AlphabetFilter';

export default function CitiesListPage() {
  const [cities, setCities] = useState([]);
  const [total, setTotal] = useState(0);
  const [availableLetters, setAvailableLetters] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();

  const page = parseInt(searchParams.get('page') || '1');
  const query = searchParams.get('q') || searchParams.get('search') || '';
  const letter = searchParams.get('letter') || '';
  const [search, setSearch] = useState(query);
  const limit = 24;

  useEffect(() => {
    const fetchCities = async () => {
      setLoading(true);
      try {
        const params = {
          skip: (page - 1) * limit,
          limit,
          status: 'published',
          ...(query && { search: query }),
          ...(letter && { letter }),
        };
        const response = await publicApi.getCities(params);
        setCities(response.data.items || []);
        setTotal(response.data.total || 0);
        if (Array.isArray(response.data.available_letters)) {
          setAvailableLetters(response.data.available_letters);
        }
      } catch (error) {
        console.error('Error fetching cities:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchCities();
  }, [page, query, letter]);

  useEffect(() => setSearch(query), [query]);

  const handleSearch = (event) => {
    event.preventDefault();
    const params = new URLSearchParams(searchParams);
    params.delete('search');
    if (search.trim()) params.set('q', search.trim());
    else params.delete('q');
    params.set('page', '1');
    setSearchParams(params);
  };

  const handleLetterClick = (nextLetter) => {
    const params = new URLSearchParams(searchParams);
    if (nextLetter) params.set('letter', nextLetter);
    else params.delete('letter');
    params.set('page', '1');
    setSearchParams(params);
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm text-gray-500">
          <li><Link to="/" className="hover:text-blue-600">Главная</Link></li>
          <li>/</li>
          <li className="text-gray-900">География</li>
        </ol>
      </nav>

      <ListPageHeader
        title="География"
        description="Города, подарившие миру звёзд юмора"
        search={search}
        onSearchChange={setSearch}
        onSearch={handleSearch}
        placeholder="Поиск города..."
        searchId="cities-search"
      >
        <AlphabetFilter
          selectedLetter={letter}
          onLetterClick={handleLetterClick}
          availableLetters={availableLetters}
        />
      </ListPageHeader>

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
                  <FittedImage
                    src={contentImageUrl(city, city.poster)}
                    fallbackKey={city}
                    alt={city.name}
                    className="h-full w-full"
                    imageClassName="group-hover:scale-105 transition-transform duration-300"
                  />
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
                  {(() => {
                    // Handle both rating formats: object with 'average' property or direct number
                    const ratingValue = typeof city.rating === 'object' && city.rating !== null 
                      ? city.rating.average 
                      : city.rating;
                    const hasRating = typeof ratingValue === 'number' && ratingValue > 0;
                    
                    return hasRating && (
                      <div className="mt-2 flex items-center gap-1 text-sm text-yellow-600">
                        <span>★</span>
                        <span>{ratingValue.toFixed(1)}</span>
                      </div>
                    );
                  })()}
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
