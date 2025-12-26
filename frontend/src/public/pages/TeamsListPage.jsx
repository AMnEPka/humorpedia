import { useState, useEffect } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Loader2, ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import publicApi from '../utils/api';

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
  
  const page = parseInt(searchParams.get('page') || '1');
  const limit = 24;

  useEffect(() => {
    const fetchTeams = async () => {
      setLoading(true);
      try {
        const res = await publicApi.getTeamsByCategory(category, { 
          page, 
          limit,
          search: search || undefined,
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
  }, [page, search, category]);

  const totalPages = Math.ceil(total / limit);
  const currentCategory = teamCategories.find(c => c.id === category) || teamCategories[0];

  const handleSearch = (e) => {
    e.preventDefault();
    setSearchParams({ q: search, page: 1 });
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

      <div className="flex flex-col gap-6 mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Команды {currentCategory.name}</h1>
        
        {/* Category Tabs */}
        <Tabs value={category} className="w-full">
          <TabsList>
            {teamCategories.map((cat) => (
              <TabsTrigger key={cat.id} value={cat.id} asChild>
                <Link to={cat.path}>{cat.name}</Link>
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
          <Input
            type="search"
            placeholder="Поиск команды..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1"
          />
          <Button type="submit" size="icon">
            <Search className="h-4 w-4" />
          </Button>
        </form>
      </div>

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
              <Link key={team.id} to={`/teams/${category}/${team.slug}`}>
                <Card className="overflow-hidden hover:shadow-lg transition-shadow group">
                  <div className="aspect-square bg-gray-100 overflow-hidden">
                    {team.logo ? (
                      <img 
                        src={team.logo} 
                        alt={team.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-gray-400 bg-gradient-to-br from-blue-50 to-blue-100">
                        <span className="text-3xl font-bold text-blue-300">
                          {team.title?.charAt(0)?.toUpperCase()}
                        </span>
                      </div>
                    )}
                  </div>
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
                onClick={() => setSearchParams({ ...Object.fromEntries(searchParams), page: page - 1 })}
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
                onClick={() => setSearchParams({ ...Object.fromEntries(searchParams), page: page + 1 })}
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
