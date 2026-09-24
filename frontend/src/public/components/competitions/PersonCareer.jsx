import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Award, Users } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import publicApi from '../../utils/api';
import { pagePath, roleTitle, teamHref, tournamentTitle } from './labels';

export function kvnCareerTeams(teams = []) {
  return teams.filter(({ team }) => !team?.show_id);
}

// Карьера человека: команды КВН из составов и роли в турнирах (жюри, ведущий, редактор).
export default function PersonCareer({ personSlug, career }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (career !== undefined) return undefined;
    let cancelled = false;
    setData(null);
    publicApi.getPersonCareer(personSlug)
      .then((res) => { if (!cancelled) setData(res.data); })
      .catch(() => { if (!cancelled) setData({ teams: [], roles: [] }); });
    return () => { cancelled = true; };
  }, [personSlug, career]);

  const visibleData = career !== undefined ? career : data;

  const roleGroups = useMemo(() => {
    const groups = new Map();
    for (const row of visibleData?.roles || []) {
      const key = `${row.role}:${row.tournament_id}`;
      if (!groups.has(key)) groups.set(key, { role: row.role, tournament: row.tournament, rows: [] });
      groups.get(key).rows.push(row);
    }
    return [...groups.values()];
  }, [visibleData]);

  if (!visibleData) return null;

  return <PersonCareerContent teams={kvnCareerTeams(visibleData.teams || [])} roleGroups={roleGroups} />;
}

export function PersonCareerContent({ teams, roleGroups }) {
  if (teams.length === 0 && roleGroups.length === 0) return null;

  return (
    <>
      {teams.length > 0 && (
        <Card id="section-career-teams" className="scroll-mt-20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5 text-blue-600" /> Команды КВН
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-4">
              {teams.map(({ membership, team }) => (
                <li key={membership._id}>
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <Link to={teamHref(team)} className="font-semibold text-blue-700 hover:underline">{team.name}</Link>
                    {membership.roles?.length > 0 && (
                      <span className="text-sm text-gray-500">
                        {membership.roles.join(', ')}
                      </span>
                    )}
                  </div>
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
