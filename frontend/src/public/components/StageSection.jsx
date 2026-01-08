import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { GameTable } from './GameTable';

export function StageSection({ stage }) {
  const { name, games = [], additional_teams = [], additional_notes = '', notes = '' } = stage;

  // Проверяем, является ли notes HTML контентом (для Кубка мэра и т.п.)
  const isHtmlNotes = notes && notes.includes('<');
  
  return (
    <div className="mb-12">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">{name}</CardTitle>
          {/* Показываем notes как текст только если это не HTML */}
          {notes && !isHtmlNotes && (
            <p className="text-sm text-gray-600 mt-2">{notes}</p>
          )}
        </CardHeader>
        <CardContent>
          {games.length === 0 && !notes && (
            <p className="text-gray-500 italic">Информация об играх отсутствует</p>
          )}
          
          {/* Для стадий без игр (Кубок мэра) - показываем HTML контент */}
          {/* Также показываем HTML notes если есть игры, но notes содержит важный текст */}
          {isHtmlNotes && (
            <div className="prose max-w-none mb-6" dangerouslySetInnerHTML={{ __html: notes }} />
          )}
          
          {games.map((game, gameIdx) => (
            <div key={gameIdx} className="mb-8 last:mb-0">
              <GameTable game={game} stageName={name} />
            </div>
          ))}

          {/* Additional teams (добор) */}
          {additional_teams.length > 0 && (
            <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <h4 className="font-semibold text-yellow-900 mb-2">Добор</h4>
              <div className="flex flex-wrap gap-2 mb-2">
                {additional_teams.map((team, idx) => (
                  <Badge key={idx} variant="outline" className="bg-yellow-100 text-yellow-800 border-yellow-300">
                    {team}
                  </Badge>
                ))}
              </div>
              {additional_notes && (
                <p className="text-sm text-yellow-800">{additional_notes}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

