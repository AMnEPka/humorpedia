import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { MapPin, Loader2, ArrowLeft, Users, UsersRound } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ModuleList } from '../components/ModuleRenderer';
import publicApi from '../utils/api';
import { usePageTitle } from '@/utils/pageTitle';
import { teamSubtitle, teamUrl } from '@/utils/teams';
import { contentImageUrl, orderedFacts, personPhotoUrl, teamLogoUrl } from '@/utils/media';
import FittedImage from '@/components/FittedImage';
import ForeignAgentNotice from '../components/ForeignAgentNotice';

function cityTeamSubtitle(team) {
  if (!team?.is_reference) return teamSubtitle(team);
  const context = (team.context || '').trim();
  if (!context) return 'Команда';
  if (/квн/i.test(context) || /^команд/i.test(context)) return 'Команда КВН';
  const show = context.replace(/^шоу\s+/i, '').replace(/^[«»"']+|[«»"']+$/g, '');
  return `Команда шоу «${show}»`;
}

export default function CityDetailPage() {
  const { slug } = useParams();
  const [city, setCity] = useState(null);
  const [relatedPeople, setRelatedPeople] = useState([]);
  const [relatedTeams, setRelatedTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  usePageTitle((city?.name || city?.title) || (loading ? 'Город' : (error ? 'Город не найден' : 'Город')));

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
              <ModuleList modules={city.modules} />
            </div>
          )}

          {/* Editorial people shortlist */}
          {relatedPeople.length > 0 && (
            <section className="bg-white rounded-lg shadow-sm border p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-5 flex items-center gap-2">
                <Users className="h-5 w-5" />
                Известные люди
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[...relatedPeople]
                  .sort((a, b) => (a.full_name || a.title || '').localeCompare(b.full_name || b.title || '', 'ru'))
                  .map((person) => (
                    <Link
                      key={person._id}
                      to={`/people/${person.slug}`}
                      className="flex items-center gap-3 rounded-lg border border-gray-100 p-3 hover:border-blue-200 hover:bg-blue-50/40 transition-colors"
                    >
                      <FittedImage
                        src={personPhotoUrl(person)}
                        fallbackKey={person}
                        alt={person.full_name || person.title}
                        className="w-12 h-12 rounded-full shrink-0"
                        fit="cover"
                      />
                      <span className="font-medium text-gray-900">
                        {person.full_name || person.title}
                      </span>
                    </Link>
                  ))}
              </div>
            </section>
          )}

          {/* All teams whose city field matches this city */}
          {relatedTeams.length > 0 && (
            <section className="bg-white rounded-lg shadow-sm border p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-5 flex items-center gap-2">
                <UsersRound className="h-5 w-5" />
                Команды
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[...relatedTeams]
                  .sort((a, b) => (a.name || a.title || '').localeCompare(b.name || b.title || '', 'ru'))
                  .map((team) => {
                    const subtitle = cityTeamSubtitle(team);
                    const card = (
                      <>
                      <FittedImage
                        src={teamLogoUrl(team)}
                        fallbackKey={team}
                        alt={team.name || team.title}
                        className="w-12 h-12 rounded-full shrink-0"
                        fit="cover"
                      />
                        <span>
                          <span className="block font-medium text-gray-900">
                            {team.name || team.title}
                          </span>
                          {subtitle && (
                            <span className="block text-xs text-gray-500 mt-0.5">{subtitle}</span>
                          )}
                        </span>
                      </>
                    );
                    const url = teamUrl(team);
                    return url ? (
                      <Link
                        key={team._id}
                        to={url}
                        className="flex items-center gap-3 rounded-lg border border-gray-100 p-3 hover:border-blue-200 hover:bg-blue-50/40 transition-colors"
                      >
                        {card}
                      </Link>
                    ) : (
                      <div
                        key={team._id}
                        className="flex items-center gap-3 rounded-lg border border-gray-100 p-3"
                      >
                        {card}
                      </div>
                    );
                  })}
              </div>
            </section>
          )}

          <ForeignAgentNotice visible={city.foreign_agent_notice} />
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Poster */}
          <div className="rounded-lg overflow-hidden shadow-sm">
            <FittedImage
              src={contentImageUrl(city, city.poster)}
              fallbackKey={city}
              alt={city.name}
              className="aspect-video"
            />
          </div>

          {/* Facts */}
          {city.facts && Object.keys(city.facts).length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h3 className="font-semibold text-gray-900 mb-4">Факты</h3>
              <dl className="space-y-3">
                {orderedFacts(city.facts, city.facts_order).map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-sm text-gray-500">{key}</dt>
                    <dd className="font-medium text-gray-900">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {/* Rating */}
          {(() => {
            // Handle both rating formats: object with 'average' property or direct number
            const ratingValue = typeof city.rating === 'object' && city.rating !== null 
              ? city.rating.average 
              : city.rating;
            const hasRating = typeof ratingValue === 'number' && ratingValue > 0;
            
            return hasRating && (
              <div className="bg-white rounded-lg shadow-sm border p-6">
                <h3 className="font-semibold text-gray-900 mb-2">Рейтинг</h3>
                <div className="flex items-center gap-2">
                  <span className="text-3xl font-bold text-yellow-500">★</span>
                  <span className="text-2xl font-bold text-gray-900">{ratingValue.toFixed(1)}</span>
                  {city.votes_count > 0 && (
                    <span className="text-sm text-gray-500">({city.votes_count} голосов)</span>
                  )}
                </div>
              </div>
            );
          })()}

        </div>
      </div>
    </div>
  );
}
