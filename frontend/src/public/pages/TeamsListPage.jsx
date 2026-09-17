import { useState, useEffect } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import publicApi from '../utils/api';
import FittedImage from '@/components/FittedImage';
import { teamLogoUrl } from '@/utils/media';
import ListPageHeader from '../components/ListPageHeader';

const teamCategories = [
  { id: 'kvn', name: 'КВН', path: '/kvn/teams' },
  { id: 'lg', name: 'Лига смеха', path: '/kvn/teams' },
  { id: 'improv', name: 'Импровизация', path: '/kvn/teams' },
];

export default function TeamsListPage() {
  const { category = 'kvn' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [teams, setTeams] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(searchParams.get('q') || '');
  const query = searchParams.get('q') || '';
  
  const page = parseInt(searchParams.get('page') || '1');
  const limit = 24;

  useEffect(() => {
    const fetchTeams = async () => {
      setLoading(true);
      try {
        const res = await publicApi.getTeamsByCategory(category, { 
          skip: (page - 1) * limit,
          limit,
          search: query || undefined,
          sort: 'title' 
        });
        setTeams(res.data.items || []);
        setTotal(res.data.total || 0);
      } catch (err) {
        console.error('Error fetching teams:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchTeams();
  }, [page, query, category]);

  useEffect(() => setSearch(query), [query]);

  const totalPages = Math.ceil(total / limit);
  const currentCategory = teamCategories.find(c => c.id === category) || teamCategories[0];

  const handleSearch = (e) => {
    e.preventDefault();
    const params = new URLSearchParams(searchParams);
    if (search.trim()) params.set('q', search.trim());
    else params.delete('q');
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
          <li><Link to="/kvn/teams" className="hover:text-blue-600">КВН</Link></li>
          <li>/</li>
          <li className="text-gray-900">Команды</li>
        </ol>
      </nav>

      <ListPageHeader
        title={`Команды ${currentCategory.name}`}
        search={search}
        onSearchChange={setSearch}
        onSearch={handleSearch}
        placeholder="Поиск команды..."
        searchId="teams-search"
      >
        <Tabs value={category} className="w-full">
          <TabsList>
            {teamCategories.map((cat) => (
              <TabsTrigger key={cat.id} value={cat.id} asChild>
                <Link to={cat.path}>{cat.name}</Link>
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </ListPageHeader>

      {loading ? (
        <div className="flex items-center justify-center min-h-[40vh]">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      ) : teams.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p>Команды не найдены</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {teams.map((team) => (
              <Link key={team.id} to={`/kvn/teams/${team.slug}`}>
                <Card className="overflow-hidden hover:shadow-lg transition-shadow group">
                  <FittedImage
                    src={teamLogoUrl(team)}
                    fallbackKey={team}
                    alt={team.title}
                    className="aspect-square bg-gray-100"
                  />
                  <CardContent className="p-3">
                    <h3 className="font-medium text-sm text-gray-900 group-hover:text-blue-600 transition-colors line-clamp-2">
                      {team.title}
                    </h3>
                    {team.city && (
                      <p className="text-xs text-gray-500 mt-1">{team.city}</p>
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
