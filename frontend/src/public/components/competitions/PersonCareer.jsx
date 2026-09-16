import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Award, Users } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import publicApi from '../../utils/api';
import {
  RESULT_TONE_CLASSES, pagePath, roleTitle, seasonResult, teamHref, tournamentTitle, yearsLabel,
} from './labels';

// Карьера человека: команды (из составов) с сезонами и роли в турнирах (жюри, ведущий, редактор).
export default function PersonCareer({ personSlug }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    publicApi.getPersonCareer(personSlug)
      .then((res) => { if (!cancelled) setData(res.data); })
      .catch(() => { if (!cancelled) setData({ teams: [], roles: [] }); });
    return () => { cancelled = true; };
  }, [personSlug]);

  const roleGroups = useMemo(() => {
    const groups = new Map();
    for (const row of data?.roles || []) {
      const key = `${row.role}:${row.tournament_id}`;
      if (!groups.has(key)) groups.set(key, { role: row.role, tournament: row.tournament, rows: [] });
      groups.get(key).rows.push(row);
    }
    return [...groups.values()];
  }, [data]);

  if (!data || (data.teams.length === 0 && roleGroups.length === 0)) return null;

  return (
    <>
      {data.teams.length > 0 && (
        <Card id="section-career-teams" className="scroll-mt-20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5 text-blue-600" /> Команды
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-4">
              {data.teams.map(({ membership, team, seasons }) => (
                <li key={membership._id}>
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <Link to={teamHref(team)} className="font-semibold text-blue-700 hover:underline">{team.name}</Link>
                    {[membership.roles?.join(', '), yearsLabel(membership)].filter(Boolean).length > 0 && (
                      <span className="text-sm text-gray-500">
                        {[membership.roles?.join(', '), yearsLabel(membership)].filter(Boolean).join(' · ')}
                      </span>
                    )}
                    {membership.status === 'former' && <span className="text-xs text-gray-400">бывший участник</span>}
                  </div>
                  {seasons.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {seasons.map((season) => <SeasonChip key={season._id} season={season} />)}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {roleGroups.length > 0 && (
        <Card id="section-career-roles" className="scroll-mt-20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Award className="h-5 w-5 text-amber-500" /> В турнирах
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {roleGroups.map(({ role, tournament, rows }) => (
                <li key={`${role}:${tournament?._id}`}>
                  <div className="text-sm">
                    <span className="font-medium text-gray-900">{roleTitle(role)}</span>
                    <span className="text-gray-500"> · {tournamentTitle(tournament)}</span>
                    <span className="text-gray-400"> · сезонов: {rows.length}</span>
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {rows.map((row) => (
                      <Link
                        key={row._id}
                        to={pagePath(row.season_path) || '#'}
                        className="text-xs px-2 py-0.5 rounded border bg-gray-50 text-gray-700 border-gray-200 hover:border-blue-300"
                        title={row.games_count ? `игр: ${row.games_count}` : undefined}
                      >
                        {row.season_year}
                      </Link>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </>
  );
}

function SeasonChip({ season }) {
  const result = seasonResult(season);
  const href = pagePath(season.season_path);
  const label = `${season.tournament?.short_title || tournamentTitle(season.tournament)} ${season.season_year}`;
  const className = `text-xs px-2 py-0.5 rounded border ${RESULT_TONE_CLASSES[result.tone]}`;
  const content = (
    <>
      {label}
      {result.tone === 'gold' && ' 🏆'}
    </>
  );
  return href
    ? <Link to={href} className={`${className} hover:opacity-80`} title={result.label}>{content}</Link>
    : <span className={className} title={result.label}>{content}</span>;
}
