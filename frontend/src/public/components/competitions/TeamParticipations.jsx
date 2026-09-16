import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, ChevronRight, Trophy } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import publicApi from '../../utils/api';
import {
  RESULT_TONE_CLASSES, formatDate, formatScore, pagePath, seasonResult, tournamentTitle,
} from './labels';

// Участие команды в сезонах всех турниров (КВН-лиги и другие шоу) — из participations.
export default function TeamParticipations({ teamSlug, teamName }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    publicApi.getTeamParticipations(teamSlug, true)
      .then((res) => { if (!cancelled) setData(res.data); })
      .catch(() => { if (!cancelled) setData({ seasons: [] }); });
    return () => { cancelled = true; };
  }, [teamSlug]);

  const groups = useMemo(() => {
    const byTournament = new Map();
    for (const season of data?.seasons || []) {
      const key = season.tournament_id;
      if (!byTournament.has(key)) {
        byTournament.set(key, { tournament: season.tournament, seasons: [] });
      }
      byTournament.get(key).seasons.push(season);
    }
    return [...byTournament.values()].sort(
      (a, b) => (a.tournament?.order ?? 999) - (b.tournament?.order ?? 999)
    );
  }, [data]);

  if (!data || groups.length === 0) return null;

  const championships = data.seasons.filter((s) => s.is_champion);

  return (
    <Card id="section-participations" className="scroll-mt-20">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Trophy className="h-5 w-5 text-amber-500" /> Участие в турнирах
        </CardTitle>
        {championships.length > 0 && (
          <p className="text-sm text-gray-600">
            Чемпион: {championships.map((s) => `${tournamentTitle(s.tournament)} ${s.season_year}`).join(', ')}
          </p>
        )}
      </CardHeader>
      <CardContent className="space-y-6">
        {groups.map(({ tournament, seasons }) => (
          <section key={tournament?._id || tournamentTitle(tournament)}>
            <h3 className="font-semibold text-gray-900 mb-2">
              {pagePath(tournament?.page_path) ? (
                <Link to={pagePath(tournament.page_path)} className="hover:text-blue-600">
                  {tournamentTitle(tournament)}
                </Link>
              ) : tournamentTitle(tournament)}
            </h3>
            <ul className="divide-y divide-gray-100 border border-gray-100 rounded-lg">
              {seasons.map((season) => (
                <SeasonRow key={season._id} season={season} teamName={teamName} />
              ))}
            </ul>
          </section>
        ))}
      </CardContent>
    </Card>
  );
}

function SeasonRow({ season, teamName }) {
  const [open, setOpen] = useState(false);
  const result = seasonResult(season);
  const games = season.games || [];
  const href = pagePath(season.season_path);

  return (
    <li>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
        <span className="w-12 font-semibold text-gray-900 tabular-nums">{season.season_year || '—'}</span>
        <span className="flex-1 min-w-[10rem] text-sm">
          {href ? <Link to={href} className="text-blue-700 hover:underline">{season.season_title}</Link> : season.season_title}
          {season.name && !sameName(season.name, teamName) && (
            <span className="text-gray-500"> · как «{season.name}»</span>
          )}
        </span>
        <span className={`text-xs px-2 py-0.5 rounded border ${RESULT_TONE_CLASSES[result.tone]}`}>{result.label}</span>
        {games.length > 0 && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900"
            aria-expanded={open}
          >
            {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            игр: {games.length}{season.wins ? `, побед: ${season.wins}` : ''}
          </button>
        )}
      </div>
      {open && games.length > 0 && (
        <div className="overflow-x-auto px-3 pb-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="py-1 pr-3 font-medium">Этап</th>
                <th className="py-1 pr-3 font-medium">Игра</th>
                <th className="py-1 pr-3 font-medium">Дата</th>
                <th className="py-1 pr-3 font-medium text-right">Место</th>
                <th className="py-1 font-medium text-right">Баллы</th>
              </tr>
            </thead>
            <tbody>
              {games.map((game) => (
                <tr key={game._id} className="border-b last:border-0">
                  <td className="py-1 pr-3 whitespace-nowrap">{game.stage_name}</td>
                  <td className="py-1 pr-3">
                    {game.game_name}
                    {game.passed && <span className="ml-2 text-xs text-green-700">прошла дальше</span>}
                    {game.is_additional && <span className="ml-2 text-xs text-gray-500">добор</span>}
                  </td>
                  <td className="py-1 pr-3 whitespace-nowrap tabular-nums">{formatDate(game.date)}</td>
                  <td className="py-1 pr-3 text-right tabular-nums">
                    {game.place ? `${game.place}${game.participants_count ? ` из ${game.participants_count}` : ''}` : ''}
                  </td>
                  <td className="py-1 text-right tabular-nums">{formatScore(game.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </li>
  );
}

// Название в сезоне показываем, только если команда тогда называлась иначе (город в скобках не в счёт)
function sameName(a, b) {
  const norm = (s) => (s || '').toLowerCase().replace(/ё/g, 'е').replace(/\([^)]*\)/g, '').replace(/[«»"]/g, '').trim();
  return !b || norm(a) === norm(b);
}
