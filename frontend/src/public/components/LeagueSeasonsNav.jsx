import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

/**
 * Нормализует список дочерних KVN-страниц (сезонов) в формат для навигации.
 * Возвращает массив { id, year, slug, full_path }, отсортированный по году.
 */
export function normalizeLeagueSeasons(children = []) {
  return (children || [])
    .filter((s) => s && s.season_data)
    .map((s) => {
      const sd = s.season_data || {};
      const year =
        sd.year ||
        (() => {
          const m = String(s.slug || '').match(/\d{4}/);
          return m ? parseInt(m[0], 10) : null;
        })();
      return {
        id: s.id || s._id || s.slug,
        slug: s.slug,
        full_path: s.full_path,
        year
      };
    })
    .filter((s) => s.year)
    .sort((a, b) => a.year - b.year);
}

/**
 * Навигация по сезонам лиги: группы по десятилетиям, кликабельные годы.
 * seasons: массив { id, year, slug, full_path }
 * leagueSlug: slug лиги (например '1l-kvn') для формирования ссылок
 * title: заголовок блока (по умолчанию "Все сезоны лиги")
 */
export function LeagueSeasonsNav({ seasons = [], leagueSlug, title = 'Все сезоны лиги' }) {
  if (!seasons || seasons.length === 0) return null;

  const seasonsByDecade = seasons.reduce((acc, s) => {
    const decade = Math.floor(s.year / 10) * 10;
    acc[decade] = acc[decade] || [];
    acc[decade].push(s);
    return acc;
  }, {});

  const sortedDecades = Object.keys(seasonsByDecade)
    .map((d) => parseInt(d, 10))
    .sort((a, b) => a - b);

  return (
    <section className="space-y-4 pt-6 border-t mt-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-xl font-bold text-gray-900">{title}</h3>
        <p className="text-sm text-gray-500">
          Нажмите на год, чтобы перейти к сезону.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {sortedDecades.map((decade) => (
          <Card key={decade} className="bg-slate-50/60">
            <CardHeader className="py-3 pb-1">
              <CardTitle className="text-sm font-semibold text-gray-700">
                {decade}–{decade + 9}
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-4 pt-1">
              <div className="flex flex-wrap gap-2">
                {seasonsByDecade[decade].map((season) => (
                  <Button
                    key={season.id}
                    asChild
                    variant="outline"
                    size="sm"
                    className="rounded-full px-3 py-1 h-8 text-sm bg-white hover:bg-blue-50 border-slate-200"
                  >
                    <Link
                      to={
                        season.full_path
                          ? `/${season.full_path}`
                          : `/kvn/${leagueSlug}/${season.slug}`
                      }
                    >
                      {season.year}
                    </Link>
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
