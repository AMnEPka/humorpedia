import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Calendar, Users, Award, Video } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import publicApi from '../utils/api';
import { formatDecimalTrim } from '@/utils/number';
import { cleanTeamName } from '@/utils/team';

export function GameTable({ game, stageName = '' }) {
  const { name, date, date_raw, teams = [], contests = [], jury = [], host = '', notes = '', is_cancelled = false, video_links = [] } = game;
  const [teamNames, setTeamNames] = useState({}); // Кэш названий команд по slug
  
  // Определяем, является ли это финалом
  const isFinal = stageName.toLowerCase().includes('финал') && !stageName.toLowerCase().includes('1/8') && 
                  !stageName.toLowerCase().includes('1/4') && !stageName.toLowerCase().includes('1/2') &&
                  !stageName.toLowerCase().includes('четверть') && !stageName.toLowerCase().includes('полу');

  // Загружаем названия команд из базы данных по их slug
  useEffect(() => {
    let cancelled = false;
    const loadTeamNames = async () => {
      const slugsToLoad = teams
        .filter(team => team.team_slug && !teamNames[team.team_slug])
        .map(team => team.team_slug);
      
      if (slugsToLoad.length === 0) return;
      
      const namesMap = { ...teamNames };
      
      // Загружаем команды параллельно
      await Promise.all(
        slugsToLoad.map(async (slug) => {
          if (cancelled) return;
          try {
            const res = await publicApi.getTeam(slug);
            if (cancelled) {
              return;
            }
            const teamData = res.data;
            // Используем name или title из базы данных
            const teamName = teamData.name || teamData.title || '';
            namesMap[slug] = teamName;
          } catch (err) {
            if (cancelled) return;
            // Если команда не найдена, используем название из данных игры
            const team = teams.find(t => t.team_slug === slug);
            if (team) {
              namesMap[slug] = team.team_name || '';
            }
          }
        })
      );
      
      if (!cancelled) {
        setTeamNames(namesMap);
      }
    };
    
    loadTeamNames();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teams]);

  if (is_cancelled) {
    return (
      <div className="p-4 bg-gray-100 border border-gray-300 rounded-lg">
        <h3 className="font-semibold text-gray-700 mb-2">{name}</h3>
        <p className="text-sm text-gray-600 italic">Игра отменена</p>
      </div>
    );
  }

  return (
    <div className="border rounded-lg p-4">
      {/* Game header */}
      <div className="mb-4">
        <h3 className="text-xl font-bold text-gray-900 mb-2">{name}</h3>
        <div className="flex flex-wrap gap-4 text-sm text-gray-600">
          {date && (
            <div className="flex items-center gap-1">
              <Calendar className="h-4 w-4" />
              <span>{date}</span>
            </div>
          )}
          {host && (
            <div className="flex items-center gap-1">
              <Users className="h-4 w-4" />
              <span>Ведущий: {host}</span>
            </div>
          )}
          {jury.length > 0 && (
            <div className="flex items-center gap-1">
              <Award className="h-4 w-4" />
              <span>Жюри: {jury
                .map(name => {
                  // Обрезаем каждый элемент массива, убирая всё после "Конкурсы:" или "Результат игры:"
                  let cleanName = name;
                  const contestsIndex = cleanName.toLowerCase().indexOf('конкурсы:');
                  if (contestsIndex !== -1) {
                    cleanName = cleanName.substring(0, contestsIndex).trim();
                  }
                  const resultIndex = cleanName.toLowerCase().indexOf('результат игры:');
                  if (resultIndex !== -1) {
                    cleanName = cleanName.substring(0, resultIndex).trim();
                  }
                  // Убираем "Жюри:" из начала, если есть
                  cleanName = cleanName.replace(/^[Жж]юри\s*:\s*/i, '').trim();
                  return cleanName;
                })
                .filter(name => {
                  // Убираем пустые строки и элементы, которые начинаются с "Конкурсы:" или "Результат игры:"
                  if (!name || name.length === 0) return false;
                  const trimmed = name.trim();
                  const lower = trimmed.toLowerCase();
                  if (lower.startsWith('конкурсы') || lower.startsWith('результат')) return false;
                  // Убираем названия конкурсов в кавычках (начинаются и заканчиваются кавычками)
                  if ((trimmed.startsWith('«') && trimmed.endsWith('»')) ||
                      (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
                      (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
                    return false;
                  }
                  // Убираем служебные слова
                  if (lower === 'и' || lower === 'а' || lower === 'но' || lower === 'или') {
                    return false;
                  }
                  return true;
                })
                .join(', ')}</span>
            </div>
          )}
        </div>
      </div>

      {/* Results table */}
      {teams.length > 0 ? (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[60px]">М</TableHead>
                <TableHead>Команда</TableHead>
                {contests.map((contest, idx) => (
                  <TableHead key={idx} className="text-center">{contest}</TableHead>
                ))}
                <TableHead className="text-center">Итого</TableHead>
                <TableHead className="w-[100px]">Результат</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {teams.map((team, idx) => {
                const isPassed = team.passed || team.is_winner;
                const isWinner = team.is_winner;
                const isAdditional = team.is_additional;  // Добор
                
                // Определяем цвет и классы
                const bgColor = isAdditional ? 'bg-yellow-50' : (isPassed ? 'bg-green-50' : '');
                const textColor = isAdditional ? 'text-yellow-700' : (isPassed ? 'text-green-700' : '');
                
                return (
                  <TableRow 
                    key={idx} 
                    className={bgColor}
                  >
                    <TableCell className="font-medium">{team.place || idx + 1}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {team.team_slug ? (
                          <Link 
                            to={`/kvn/teams/${team.team_slug}`}
                            className={`font-medium hover:underline ${textColor}`}
                          >
                            {/* Используем название из базы данных, если оно загружено, иначе из данных игры */}
                            {teamNames[team.team_slug] || cleanTeamName(team.team_name) || team.team_slug}
                          </Link>
                        ) : (
                          <span className={`font-medium ${textColor}`}>
                            {cleanTeamName(team.team_name)}
                          </span>
                        )}
                        {isWinner && (
                          <Badge variant="default" className="bg-yellow-600">
                            🏆
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    {contests.map((contest, contestIdx) => (
                      <TableCell key={contestIdx} className="text-center">
                        {team.scores && team.scores[contest] !== undefined 
                          ? formatDecimalTrim(team.scores[contest], 2)
                          : '-'
                        }
                      </TableCell>
                    ))}
                    <TableCell className="text-center font-semibold">
                      {team.total !== null && team.total !== undefined
                        ? formatDecimalTrim(team.total, 2)
                        : '-'
                      }
                    </TableCell>
                    <TableCell>
                      {isPassed && (
                        <Badge 
                          variant="outline" 
                          className={isAdditional 
                            ? 'bg-yellow-100 text-yellow-800 border-yellow-300' 
                            : (isFinal ? 'bg-yellow-600 text-white border-yellow-700' : 'bg-green-100 text-green-800 border-green-300')
                          }
                        >
                          {isFinal ? 'Чемпион' : (isWinner ? 'Победитель' : (isAdditional ? 'Добор' : 'Прошёл'))}
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      ) : (
        <p className="text-gray-500 italic">Результаты игры отсутствуют</p>
      )}

      {/* Video links */}
      {video_links.length > 0 && (
        <div className="mt-4 pt-4 border-t">
          <div className="flex items-center gap-2 mb-2">
            <Video className="h-4 w-4 text-gray-600" />
            <span className="text-sm font-semibold text-gray-700">Видео:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {video_links.map((link, idx) => (
              <a
                key={idx}
                href={link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
              >
                {link}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

