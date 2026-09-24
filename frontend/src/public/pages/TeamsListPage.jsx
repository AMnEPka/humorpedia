import { useState, useEffect } from 'react';
import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom';
import { Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import publicApi from '../utils/api';
import FittedImage from '@/components/FittedImage';
import { teamLogoUrl } from '@/utils/media';
import { teamSubtitle, teamUrl } from '@/utils/teams';
import ListPageHeader from '../components/ListPageHeader';
import AlphabetFilter from '../components/AlphabetFilter';

const categories = [
  { slug: 'kvn', title: 'Команды КВН', featured: true },
  { slug: 'zvezdy-ntv', title: 'Звёзды', featured: true },
  { slug: 'igra', title: 'ИГРА', retro: true },
  { slug: 'liga-gorodov', title: 'Лига Городов', retro: true },
  { slug: 'improv-teams', title: 'Импровизация. Команды', retro: true },
];

export default function TeamsListPage() {
  const { category: categoryParam } = useParams();
  const category = categoryParam ? categories.find(item => item.slug === categoryParam) : categories[0];
  const categorySlug = category?.slug;
  const [searchParams, setSearchParams] = useSearchParams();
  const [teams, setTeams] = useState([]);
  const [total, setTotal] = useState(0);
  const [availableLetters, setAvailableLetters] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState(searchParams.get('q') || '');
  const query = searchParams.get('q') || '';
  const letter = searchParams.get('letter') || '';
  const page = Math.max(1, Number.parseInt(searchParams.get('page'), 10) || 1);
  const limit = 24;

  useEffect(() => {
    if (!categorySlug) return undefined;
    let cancelled = false;
    setLoading(true);
    setError(false);
    publicApi.getTeamsByCategory(categorySlug, {
      skip: (page - 1) * limit, limit,
      search: query || undefined, letter: letter || undefined,
    }).then(res => {
      if (cancelled) return;
      setTeams(res.data.items || []);
      setTotal(res.data.total || 0);
      setAvailableLetters(res.data.available_letters || null);
    }).catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [categorySlug, page, query, letter]);

  useEffect(() => setSearch(query), [query]);

  const totalPages = Math.ceil(total / limit);
  const updateParam = (name, value) => {
    const params = new URLSearchParams(searchParams);
    if (value) params.set(name, value);
    else params.delete(name);
    params.delete('page');
    setSearchParams(params);
  };

  if (!category) return <Navigate to="/teams" replace />;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <nav className="mb-6" aria-label="Хлебные крошки">
        <ol className="flex items-center gap-2 text-sm text-gray-500">
          <li><Link to="/" className="hover:text-blue-600">Главная</Link></li>
          <li>/</li><li className="text-gray-900">Команды</li>
        </ol>
      </nav>

      <ListPageHeader title="Команды" search={search} onSearchChange={setSearch}
        onSearch={event => { event.preventDefault(); updateParam('q', search.trim()); }}
        placeholder="Поиск команды..." searchId="teams-search" />
      <nav aria-label="Тип команд" className="flex flex-wrap gap-2 mb-6">
        <div className="grid w-full grid-cols-2 gap-3">
          {categories.filter(item => item.featured).map(item => (
            <Link key={item.slug} to={item.slug === 'kvn' ? '/teams' : `/teams/${item.slug}`}
              aria-current={category.slug === item.slug ? 'page' : undefined}
              className={`flex min-h-20 items-center justify-center rounded-xl border-2 px-3 py-4 text-center text-base font-semibold shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 sm:text-lg ${category.slug === item.slug ? 'border-blue-600 bg-blue-50 text-blue-900' : 'border-blue-200 bg-white text-blue-800 hover:border-blue-500 hover:bg-blue-50'}`}>
              {item.title}
            </Link>
          ))}
        </div>
        <div className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 pt-1 text-sm">
          <span className="text-gray-500">Другие шоу:</span>
          {categories.filter(item => !item.featured).map(item => (
            <Link key={item.slug} to={`/teams/${item.slug}`}
              aria-current={category.slug === item.slug ? 'page' : undefined}
              className={`inline-flex min-h-11 items-center rounded px-1 underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 ${category.slug === item.slug ? 'font-semibold text-blue-800 underline' : 'text-gray-600 hover:text-blue-700 hover:underline'}`}>
              {item.title}<span className="ml-1 text-xs text-gray-500">ретро</span>
            </Link>
          ))}
        </div>
      </nav>

      <div className="mb-8">
        <AlphabetFilter selectedLetter={letter}
          onLetterClick={nextLetter => updateParam('letter', nextLetter)}
          availableLetters={availableLetters} />
      </div>

      {loading ? (
        <div className="flex items-center justify-center min-h-[40vh]" aria-label="Загрузка команд">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      ) : error ? (
        <p role="alert" className="py-12 text-center text-gray-600">Не удалось загрузить команды. Обновите страницу и попробуйте ещё раз.</p>
      ) : teams.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <p>{query || letter ? 'По этим условиям команды не найдены.' : 'В этом разделе пока нет команд.'}</p>
          {(query || letter) && <Button variant="link" onClick={() => setSearchParams({})}>Сбросить фильтры</Button>}
        </div>
      ) : (
        <>
          <p className="text-sm text-gray-600 mb-4">{category.title}: {total}</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {teams.map(team => (
              <Link key={team._id || team.id} to={teamUrl(team)} className="focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 rounded-lg">
                <Card className="h-full overflow-hidden hover:shadow-lg transition-shadow group">
                  <FittedImage src={teamLogoUrl(team)} fallbackKey={team} alt="" className="aspect-square bg-gray-100" />
                  <CardContent className="p-3">
                    <h3 className="font-medium text-sm text-gray-900 group-hover:text-blue-600 transition-colors line-clamp-2">{team.title}</h3>
                    <p className="text-xs text-gray-500 mt-1">{teamSubtitle(team)}</p>
                    {(team.city || team.facts?.['Город']) && <p className="text-xs text-gray-500 mt-1">{team.city || team.facts['Город']}</p>}
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-8">
              <Button variant="outline" size="icon" aria-label="Предыдущая страница" disabled={page <= 1} onClick={() => {
                const params = new URLSearchParams(searchParams); params.set('page', String(page - 1)); setSearchParams(params);
              }}><ChevronLeft className="h-4 w-4" /></Button>
              <span className="px-4 py-2 text-sm">Страница {page} из {totalPages}</span>
              <Button variant="outline" size="icon" aria-label="Следующая страница" disabled={page >= totalPages} onClick={() => {
                const params = new URLSearchParams(searchParams); params.set('page', String(page + 1)); setSearchParams(params);
              }}><ChevronRight className="h-4 w-4" /></Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
