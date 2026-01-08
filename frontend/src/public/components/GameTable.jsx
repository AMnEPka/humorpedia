import { Link } from 'react-router-dom';
import { Calendar, Users, Award } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

export function GameTable({ game, stageName = '' }) {
  const { name, date, date_raw, teams = [], contests = [], jury = [], host = '', notes = '', is_cancelled = false } = game;
  
  // Определяем, является ли это финалом
  const isFinal = stageName.toLowerCase().includes('финал') && !stageName.toLowerCase().includes('1/8') && 
                  !stageName.toLowerCase().includes('1/4') && !stageName.toLowerCase().includes('1/2') &&
                  !stageName.toLowerCase().includes('четверть') && !stageName.toLowerCase().includes('полу');

  if (is_cancelled) {
    return (
      <div className="p-4 bg-gray-100 border border-gray-300 rounded-lg">
        <h3 className="font-semibold text-gray-700 mb-2">{name}</h3>
        <p className="text-sm text-gray-600 italic">Игра отменена</p>
        {notes && (
          <p className="text-sm text-gray-600 mt-2">{notes}</p>
        )}
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
              <span>Жюри: {jury.join(', ')}</span>
            </div>
          )}
        </div>
        {notes && (
          <p className="text-sm text-gray-600 mt-2">{notes}</p>
        )}
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
                            {team.team_name || team.team_slug}
                          </Link>
                        ) : (
                          <span className={`font-medium ${textColor}`}>
                            {team.team_name}
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
                          ? team.scores[contest].toFixed(1)
                          : '-'
                        }
                      </TableCell>
                    ))}
                    <TableCell className="text-center font-semibold">
                      {team.total ? team.total.toFixed(1) : '-'}
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
    </div>
  );
}

