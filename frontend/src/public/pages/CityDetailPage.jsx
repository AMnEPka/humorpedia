import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { MapPin, Loader2, ArrowLeft, Users, UsersRound } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import ModuleRenderer from '../components/ModuleRenderer';
import publicApi from '../utils/api';

export default function CityDetailPage() {
  const { slug } = useParams();
  const [city, setCity] = useState(null);
  const [relatedPeople, setRelatedPeople] = useState([]);
  const [relatedTeams, setRelatedTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchCity = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await publicApi.getCity(slug);
        setCity(response.data);

        // Fetch related people and teams if available
        if (response.data.related_person_ids?.length > 0) {
          try {
            const peopleRes = await publicApi.getCityRelatedPeople(response.data._id);
            setRelatedPeople(peopleRes.data.items || []);
          } catch (e) {
            console.error('Error fetching related people:', e);
          }
        }

        if (response.data.related_team_ids?.length > 0) {
          try {
            const teamsRes = await publicApi.getCityRelatedTeams(response.data._id);
            setRelatedTeams(teamsRes.data.items || []);
          } catch (e) {
            console.error('Error fetching related teams:', e);
          }
        }
      } catch (error) {
        console.error('Error fetching city:', error);
        setError('Город не найден');
      } finally {
        setLoading(false);
      }
    };
    fetchCity();
  }, [slug]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !city) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center">
        <MapPin className="h-16 w-16 mx-auto text-gray-300 mb-4" />
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{error || 'Город не найден'}</h1>
        <Link to="/city">
          <Button variant="outline" className="mt-4">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Вернуться к списку городов
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumbs */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm">
          <li>
            <Link to="/" className="text-gray-500 hover:text-gray-700">Главная</Link>
          </li>
          <li className="text-gray-300">/</li>
          <li>
            <Link to="/city" className="text-gray-500 hover:text-gray-700">География</Link>
          </li>
          <li className="text-gray-300">/</li>
          <li className="text-gray-900 font-medium">{city.name || city.title}</li>
        </ol>
      </nav>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-8">
          {/* Header */}
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <MapPin className="h-8 w-8 text-blue-600" />
              {city.name || city.title}
            </h1>
            {city.description && (
              <p className="mt-4 text-lg text-gray-600 leading-relaxed">
                {city.description}
              </p>
            )}
          </div>

          {/* Tags */}
          {city.tags?.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {city.tags.map((tag, idx) => (
                <Link key={idx} to={`/tags/${encodeURIComponent(tag)}`}>
                  <Badge variant="secondary" className="hover:bg-gray-200">
                    {tag}
                  </Badge>
                </Link>
              ))}
            </div>
          )}

          {/* Modules */}
          {city.modules?.length > 0 && (
            <div className="space-y-8">
              <ModuleRenderer modules={city.modules} />
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Poster */}
          {city.poster?.url && (
            <div className="rounded-lg overflow-hidden shadow-sm">
              <img
                src={city.poster.url}
                alt={city.name}
                className="w-full aspect-video object-cover"
              />
            </div>
          )}

          {/* Facts */}
          {city.facts && Object.keys(city.facts).length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h3 className="font-semibold text-gray-900 mb-4">Факты</h3>
              <dl className="space-y-3">
                {Object.entries(city.facts).map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-sm text-gray-500">{key}</dt>
                    <dd className="font-medium text-gray-900">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {/* Rating */}
          {city.rating > 0 && (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h3 className="font-semibold text-gray-900 mb-2">Рейтинг</h3>
              <div className="flex items-center gap-2">
                <span className="text-3xl font-bold text-yellow-500">★</span>
                <span className="text-2xl font-bold text-gray-900">{city.rating.toFixed(1)}</span>
                {city.votes_count > 0 && (
                  <span className="text-sm text-gray-500">({city.votes_count} голосов)</span>
                )}
              </div>
            </div>
          )}

          {/* Related People */}
          {relatedPeople.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Users className="h-5 w-5" />
                Известные люди
              </h3>
              <div className="space-y-3">
                {relatedPeople.slice(0, 10).map((person) => (
                  <Link
                    key={person._id}
                    to={`/people/${person.slug}`}
                    className="flex items-center gap-3 hover:bg-gray-50 -mx-2 px-2 py-1 rounded"
                  >
                    {person.photo?.thumbnail ? (
                      <img
                        src={person.photo.thumbnail}
                        alt={person.full_name}
                        className="w-10 h-10 rounded-full object-cover"
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center">
                        <Users className="h-5 w-5 text-gray-400" />
                      </div>
                    )}
                    <span className="text-sm font-medium text-gray-900 hover:text-blue-600">
                      {person.full_name || person.title}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Related Teams */}
          {relatedTeams.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <UsersRound className="h-5 w-5" />
                Команды
              </h3>
              <div className="space-y-3">
                {relatedTeams.slice(0, 10).map((team) => (
                  <Link
                    key={team._id}
                    to={`/kvn/teams/${team.slug}`}
                    className="flex items-center gap-3 hover:bg-gray-50 -mx-2 px-2 py-1 rounded"
                  >
                    {team.logo?.thumbnail ? (
                      <img
                        src={team.logo.thumbnail}
                        alt={team.name}
                        className="w-10 h-10 rounded-full object-cover"
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center">
                        <UsersRound className="h-5 w-5 text-gray-400" />
                      </div>
                    )}
                    <span className="text-sm font-medium text-gray-900 hover:text-blue-600">
                      {team.name || team.title}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
