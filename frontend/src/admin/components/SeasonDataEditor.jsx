import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { 
  Accordion, 
  AccordionContent, 
  AccordionItem, 
  AccordionTrigger 
} from '@/components/ui/accordion';
import { Plus, X, ChevronDown, ChevronUp, Trash2 } from 'lucide-react';
import TeamSelector from './TeamSelector';
import RichTextEditor from './RichTextEditor';

export default function SeasonDataEditor({ seasonData, onChange }) {
  const [expandedStages, setExpandedStages] = useState(new Set());

  // Если seasonData отсутствует, показываем сообщение
  if (!seasonData) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-gray-500 text-center">
            Сезон ещё не создан. Нажмите кнопку "Создать шаблон сезона" выше, чтобы начать.
          </p>
        </CardContent>
      </Card>
    );
  }

  // Инициализируем seasonData если его нет
  const data = seasonData || {
    league_name: '',
    year: 0,
    season_number: 0,
    winners: [],
    all_teams: [],
    intro_html: '',
    description: '',
    stages: []
  };

  const toggleStage = (stageIndex) => {
    const newExpanded = new Set(expandedStages);
    if (newExpanded.has(stageIndex)) {
      newExpanded.delete(stageIndex);
    } else {
      newExpanded.add(stageIndex);
    }
    setExpandedStages(newExpanded);
  };

  const updateStage = (stageIndex, updates) => {
    const newData = { ...data };
    if (!newData.stages) newData.stages = [];
    newData.stages = [...newData.stages];
    newData.stages[stageIndex] = { ...newData.stages[stageIndex], ...updates };
    onChange(newData);
  };

  const addStage = () => {
    const newData = { ...data };
    if (!newData.stages) newData.stages = [];
    const maxOrder = newData.stages.length > 0 
      ? Math.max(...newData.stages.map(s => s.order || 0))
      : 0;
    newData.stages = [...newData.stages, {
      name: `Стадия ${newData.stages.length + 1}`,
      order: maxOrder + 1,
      games: [],
      notes: '',
      additional_teams: [],
      additional_notes: ''
    }];
    onChange(newData);
  };

  const removeStage = (stageIndex) => {
    const newData = { ...data };
    if (!newData.stages) return;
    newData.stages = newData.stages.filter((_, i) => i !== stageIndex);
    onChange(newData);
  };

  const updateGame = (stageIndex, gameIndex, updates) => {
    const newData = { ...data };
    if (!newData.stages) newData.stages = [];
    newData.stages = [...newData.stages];
    if (!newData.stages[stageIndex].games) newData.stages[stageIndex].games = [];
    newData.stages[stageIndex] = { ...newData.stages[stageIndex] };
    newData.stages[stageIndex].games = [...newData.stages[stageIndex].games];
    newData.stages[stageIndex].games[gameIndex] = {
      ...newData.stages[stageIndex].games[gameIndex],
      ...updates
    };
    onChange(newData);
  };

  const addGame = (stageIndex) => {
    const newData = { ...data };
    if (!newData.stages) newData.stages = [];
    newData.stages = [...newData.stages];
    if (!newData.stages[stageIndex].games) newData.stages[stageIndex].games = [];
    const games = newData.stages[stageIndex].games;
    const maxOrder = games.length > 0 
      ? Math.max(...games.map(g => g.order || 0))
      : 0;
    newData.stages[stageIndex].games = [...games, {
      name: `Игра ${games.length + 1}`,
      order: maxOrder + 1,
      date: '',
      host: '',
      jury: [],
      contests: [],
      teams: [],
      notes: ''
    }];
    onChange(newData);
  };

  const removeGame = (stageIndex, gameIndex) => {
    const newData = { ...data };
    if (!newData.stages) return;
    newData.stages = [...newData.stages];
    if (!newData.stages[stageIndex].games) return;
    newData.stages[stageIndex].games = newData.stages[stageIndex].games.filter((_, i) => i !== gameIndex);
    onChange(newData);
  };

  const updateTeam = (stageIndex, gameIndex, teamIndex, updates) => {
    const newData = { ...data };
    if (!newData.stages) newData.stages = [];
    newData.stages = [...newData.stages];
    if (!newData.stages[stageIndex].games) newData.stages[stageIndex].games = [];
    newData.stages[stageIndex] = { ...newData.stages[stageIndex] };
    newData.stages[stageIndex].games = [...newData.stages[stageIndex].games];
    if (!newData.stages[stageIndex].games[gameIndex].teams) {
      newData.stages[stageIndex].games[gameIndex].teams = [];
    }
    newData.stages[stageIndex].games[gameIndex] = {
      ...newData.stages[stageIndex].games[gameIndex]
    };
    newData.stages[stageIndex].games[gameIndex].teams = [
      ...newData.stages[stageIndex].games[gameIndex].teams
    ];
    newData.stages[stageIndex].games[gameIndex].teams[teamIndex] = {
      ...newData.stages[stageIndex].games[gameIndex].teams[teamIndex],
      ...updates
    };
    onChange(newData);
  };

  const addTeamToGame = (stageIndex, gameIndex) => {
    const newData = { ...data };
    if (!newData.stages) newData.stages = [];
    newData.stages = [...newData.stages];
    if (!newData.stages[stageIndex].games) newData.stages[stageIndex].games = [];
    newData.stages[stageIndex] = { ...newData.stages[stageIndex] };
    newData.stages[stageIndex].games = [...newData.stages[stageIndex].games];
    if (!newData.stages[stageIndex].games[gameIndex].teams) {
      newData.stages[stageIndex].games[gameIndex].teams = [];
    }
    newData.stages[stageIndex].games[gameIndex].teams = [
      ...newData.stages[stageIndex].games[gameIndex].teams,
      {
        team_slug: '',
        team_name: '',
        place: 0,
        total: 0,
        scores: {},
        passed: false,
        is_winner: false,
        is_additional: false,
        city: ''
      }
    ];
    onChange(newData);
  };

  const removeTeamFromGame = (stageIndex, gameIndex, teamIndex) => {
    const newData = { ...data };
    if (!newData.stages) return;
    newData.stages = [...newData.stages];
    if (!newData.stages[stageIndex].games) return;
    newData.stages[stageIndex].games = [...newData.stages[stageIndex].games];
    if (!newData.stages[stageIndex].games[gameIndex].teams) return;
    newData.stages[stageIndex].games[gameIndex].teams = 
      newData.stages[stageIndex].games[gameIndex].teams.filter((_, i) => i !== teamIndex);
    onChange(newData);
  };

  const addContest = (stageIndex, gameIndex) => {
    const newData = { ...data };
    if (!newData.stages) newData.stages = [];
    newData.stages = [...newData.stages];
    if (!newData.stages[stageIndex].games) newData.stages[stageIndex].games = [];
    newData.stages[stageIndex] = { ...newData.stages[stageIndex] };
    newData.stages[stageIndex].games = [...newData.stages[stageIndex].games];
    if (!newData.stages[stageIndex].games[gameIndex].contests) {
      newData.stages[stageIndex].games[gameIndex].contests = [];
    }
    const contestName = prompt('Введите название конкурса:');
    if (contestName && contestName.trim()) {
      newData.stages[stageIndex].games[gameIndex].contests = [
        ...newData.stages[stageIndex].games[gameIndex].contests,
        contestName.trim()
      ];
      // Добавляем поле scores для всех команд, если его еще нет
      if (newData.stages[stageIndex].games[gameIndex].teams) {
        newData.stages[stageIndex].games[gameIndex].teams = 
          newData.stages[stageIndex].games[gameIndex].teams.map(team => ({
            ...team,
            scores: {
              ...(team.scores || {}),
              [contestName.trim()]: 0
            }
          }));
      }
      onChange(newData);
    }
  };

  const removeContest = (stageIndex, gameIndex, contestName) => {
    const newData = { ...data };
    if (!newData.stages) return;
    newData.stages = [...newData.stages];
    if (!newData.stages[stageIndex].games) return;
    newData.stages[stageIndex].games = [...newData.stages[stageIndex].games];
    if (!newData.stages[stageIndex].games[gameIndex].contests) return;
    newData.stages[stageIndex].games[gameIndex].contests = 
      newData.stages[stageIndex].games[gameIndex].contests.filter(c => c !== contestName);
    // Удаляем scores для этого конкурса у всех команд
    if (newData.stages[stageIndex].games[gameIndex].teams) {
      newData.stages[stageIndex].games[gameIndex].teams = 
        newData.stages[stageIndex].games[gameIndex].teams.map(team => {
          const newScores = { ...(team.scores || {}) };
          delete newScores[contestName];
          return { ...team, scores: newScores };
        });
    }
    onChange(newData);
  };

  // Обработка победителей - конвертируем в формат для TeamSelector
  const winnersValue = Array.isArray(data.winners) 
    ? data.winners.map(w => {
        if (typeof w === 'object' && w !== null) {
          return w;
        }
        return { slug: w, name: w, city: '' };
      })
    : [];

  const handleWinnersChange = (winners) => {
    // Конвертируем обратно в формат сезона, сохраняя город
    const winnersFormatted = winners.map(w => {
      if (typeof w === 'object' && w !== null) {
        if (w.slug) {
          return { slug: w.slug, name: w.name || w.slug, city: w.city || '' };
        }
        return w.name;
      }
      return w;
    });
    onChange({ ...data, winners: winnersFormatted });
  };

  // Обработка команд-участников
  const allTeamsValue = Array.isArray(data.all_teams) ? data.all_teams : [];

  const handleAllTeamsChange = (teams) => {
    onChange({ ...data, all_teams: teams });
  };

  return (
    <div className="space-y-6">
      {/* Основная информация */}
      <Card>
        <CardHeader>
          <CardTitle>Основная информация</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>Лига</Label>
              <Input 
                value={data.league_name || ''} 
                onChange={(e) => onChange({ ...data, league_name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Год</Label>
              <Input 
                type="number"
                value={data.year || ''} 
                onChange={(e) => onChange({ ...data, year: parseInt(e.target.value) || 0 })}
              />
            </div>
            <div className="space-y-2">
              <Label>Номер сезона</Label>
              <Input 
                type="number"
                value={data.season_number || ''} 
                onChange={(e) => onChange({ ...data, season_number: parseInt(e.target.value) || 0 })}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Победители</Label>
            <TeamSelector
              value={winnersValue}
              onChange={handleWinnersChange}
              placeholder="Выберите команды-победители..."
              allowCustom={true}
            />
          </div>
          <div className="space-y-2">
            <Label>Команды-участники</Label>
            <TeamSelector
              value={allTeamsValue}
              onChange={handleAllTeamsChange}
              placeholder="Выберите команды-участники..."
              allowCustom={true}
            />
          </div>
        </CardContent>
      </Card>

      {/* О сезоне */}
      <Card>
        <CardHeader>
          <CardTitle>О сезоне</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Описание сезона (HTML)</Label>
            <RichTextEditor
              content={data.intro_html || ''}
              onChange={(html) => onChange({ ...data, intro_html: html })}
              placeholder="Введите описание сезона..."
              minHeight={300}
            />
          </div>
          <div className="space-y-2">
            <Label>Краткое описание (текст)</Label>
            <Textarea 
              value={data.description || ''} 
              onChange={(e) => onChange({ ...data, description: e.target.value })}
              rows={3}
              placeholder="Краткое текстовое описание для превью"
            />
          </div>
        </CardContent>
      </Card>

      {/* Стадии */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Стадии сезона ({data.stages?.length || 0})</CardTitle>
            <Button onClick={addStage} size="sm" variant="outline">
              <Plus className="h-4 w-4 mr-2" />
              Добавить стадию
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {data.stages && data.stages.length > 0 ? (
              data.stages.map((stage, stageIndex) => (
                <Accordion 
                  key={stageIndex} 
                  type="single" 
                  collapsible
                  value={expandedStages.has(stageIndex) ? `stage-${stageIndex}` : undefined}
                  onValueChange={() => toggleStage(stageIndex)}
                >
                  <AccordionItem value={`stage-${stageIndex}`}>
                    <AccordionTrigger className="hover:no-underline">
                      <div className="flex items-center justify-between w-full pr-4">
                        <div>
                          <span className="font-semibold">{stage.name || `Стадия ${stageIndex + 1}`}</span>
                          <Badge variant="outline" className="ml-2">
                            {stage.games?.length || 0} игр
                          </Badge>
                        </div>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="space-y-4 pt-4">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold">Настройки стадии</h4>
                          <Button 
                            onClick={() => removeStage(stageIndex)} 
                            size="sm" 
                            variant="destructive"
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Удалить стадию
                          </Button>
                        </div>
                        <div className="grid md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>Название стадии</Label>
                            <Input 
                              value={stage.name || ''} 
                              onChange={(e) => updateStage(stageIndex, { name: e.target.value })}
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>Порядок</Label>
                            <Input 
                              type="number"
                              value={stage.order || 0} 
                              onChange={(e) => updateStage(stageIndex, { order: parseInt(e.target.value) || 0 })}
                            />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label>Заметки к стадии (HTML)</Label>
                          <Textarea 
                            value={stage.notes || ''} 
                            onChange={(e) => updateStage(stageIndex, { notes: e.target.value })}
                            rows={3}
                            className="font-mono text-sm"
                            placeholder="Дополнительная информация по стадии"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Доборы после стадии (команды через запятую)</Label>
                          <Input 
                            value={Array.isArray(stage.additional_teams) ? stage.additional_teams.join(', ') : ''} 
                            onChange={(e) => {
                              const additional_teams = e.target.value.split(',').map(t => t.trim()).filter(t => t);
                              updateStage(stageIndex, { additional_teams });
                            }}
                            placeholder="Названия команд, прошедших добором"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Комментарий к доборам</Label>
                          <Textarea 
                            value={stage.additional_notes || ''} 
                            onChange={(e) => updateStage(stageIndex, { additional_notes: e.target.value })}
                            rows={2}
                            placeholder="Текст о доборах (например: 'После всех игр жюри добрали...')"
                          />
                        </div>

                        {/* Игры */}
                        <div className="space-y-4 mt-4 border-t pt-4">
                          <div className="flex items-center justify-between">
                            <Label className="text-lg">Игры ({stage.games?.length || 0})</Label>
                            <Button onClick={() => addGame(stageIndex)} size="sm" variant="outline">
                              <Plus className="h-4 w-4 mr-2" />
                              Добавить игру
                            </Button>
                          </div>
                          {stage.games && stage.games.length > 0 ? (
                            stage.games.map((game, gameIndex) => (
                              <Card key={gameIndex} className="bg-gray-50">
                                <CardHeader className="pb-3">
                                  <div className="flex items-center justify-between">
                                    <CardTitle className="text-base">{game.name || `Игра ${gameIndex + 1}`}</CardTitle>
                                    <Button 
                                      onClick={() => removeGame(stageIndex, gameIndex)} 
                                      size="sm" 
                                      variant="ghost"
                                      className="text-destructive hover:text-destructive"
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                  <div className="grid md:grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                      <Label>Название игры</Label>
                                      <Input 
                                        value={game.name || ''} 
                                        onChange={(e) => updateGame(stageIndex, gameIndex, { name: e.target.value })}
                                      />
                                    </div>
                                    <div className="space-y-2">
                                      <Label>Дата</Label>
                                      <Input 
                                        value={game.date || ''} 
                                        onChange={(e) => updateGame(stageIndex, gameIndex, { date: e.target.value })}
                                        placeholder="YYYY-MM-DD"
                                      />
                                    </div>
                                  </div>
                                  <div className="space-y-2">
                                    <Label>Ведущий</Label>
                                    <Input 
                                      value={game.host || ''} 
                                      onChange={(e) => updateGame(stageIndex, gameIndex, { host: e.target.value })}
                                    />
                                  </div>
                                  <div className="space-y-2">
                                    <Label>Жюри (через запятую)</Label>
                                    <Input 
                                      value={Array.isArray(game.jury) ? game.jury.join(', ') : ''} 
                                      onChange={(e) => {
                                        const jury = e.target.value.split(',').map(j => j.trim()).filter(j => j);
                                        updateGame(stageIndex, gameIndex, { jury });
                                      }}
                                    />
                                  </div>

                                  {/* Конкурсы */}
                                  <div className="space-y-2 mt-4 border-t pt-4">
                                    <div className="flex items-center justify-between">
                                      <Label>Конкурсы ({game.contests?.length || 0})</Label>
                                      <Button 
                                        onClick={() => addContest(stageIndex, gameIndex)} 
                                        size="sm" 
                                        variant="outline"
                                      >
                                        <Plus className="h-4 w-4 mr-2" />
                                        Добавить конкурс
                                      </Button>
                                    </div>
                                    {game.contests && game.contests.length > 0 && (
                                      <div className="flex flex-wrap gap-2">
                                        {game.contests.map((contest, contestIndex) => (
                                          <Badge key={contestIndex} variant="secondary" className="pr-1">
                                            {contest}
                                            <button
                                              type="button"
                                              onClick={() => removeContest(stageIndex, gameIndex, contest)}
                                              className="ml-1 hover:text-destructive"
                                            >
                                              <X className="h-3 w-3" />
                                            </button>
                                          </Badge>
                                        ))}
                                      </div>
                                    )}
                                  </div>

                                  {/* Команды */}
                                  <div className="space-y-2 mt-4 border-t pt-4">
                                    <div className="flex items-center justify-between">
                                      <Label>Команды ({game.teams?.length || 0})</Label>
                                      <Button 
                                        onClick={() => addTeamToGame(stageIndex, gameIndex)} 
                                        size="sm" 
                                        variant="outline"
                                      >
                                        <Plus className="h-4 w-4 mr-2" />
                                        Добавить команду
                                      </Button>
                                    </div>
                                    {game.teams && game.teams.length > 0 ? (
                                      <div className="space-y-2">
                                        {game.teams.map((team, teamIndex) => (
                                          <Card key={teamIndex} className="bg-white">
                                            <CardContent className="pt-4">
                                              <div className="flex items-center justify-between mb-4">
                                                <h5 className="font-semibold">Команда {teamIndex + 1}</h5>
                                                <Button 
                                                  onClick={() => removeTeamFromGame(stageIndex, gameIndex, teamIndex)} 
                                                  size="sm" 
                                                  variant="ghost"
                                                  className="text-destructive hover:text-destructive"
                                                >
                                                  <Trash2 className="h-4 w-4" />
                                                </Button>
                                              </div>
                                              <div className="grid md:grid-cols-4 gap-4">
                                                <div className="space-y-2">
                                                  <Label>Название команды</Label>
                                                  <Input 
                                                    value={team.team_name || ''} 
                                                    onChange={(e) => updateTeam(stageIndex, gameIndex, teamIndex, { team_name: e.target.value })}
                                                  />
                                                </div>
                                                <div className="space-y-2">
                                                  <Label>Место</Label>
                                                  <Input 
                                                    type="number"
                                                    value={team.place || ''} 
                                                    onChange={(e) => updateTeam(stageIndex, gameIndex, teamIndex, { place: parseInt(e.target.value) || 0 })}
                                                  />
                                                </div>
                                                <div className="space-y-2">
                                                  <Label>Итого</Label>
                                                  <Input 
                                                    type="number"
                                                    step="0.1"
                                                    value={team.total || ''} 
                                                    onChange={(e) => updateTeam(stageIndex, gameIndex, teamIndex, { total: parseFloat(e.target.value) || 0 })}
                                                  />
                                                </div>
                                                <div className="space-y-2 flex flex-col">
                                                  <Label>Флаги</Label>
                                                  <div className="flex flex-col gap-2 mt-2">
                                                    <div className="flex items-center gap-2">
                                                      <Checkbox 
                                                        checked={team.passed || false}
                                                        onCheckedChange={(checked) => updateTeam(stageIndex, gameIndex, teamIndex, { passed: checked })}
                                                      />
                                                      <Label className="text-sm">Прошёл</Label>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                      <Checkbox 
                                                        checked={team.is_winner || false}
                                                        onCheckedChange={(checked) => updateTeam(stageIndex, gameIndex, teamIndex, { is_winner: checked })}
                                                      />
                                                      <Label className="text-sm">Победитель</Label>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                      <Checkbox 
                                                        checked={team.is_additional || false}
                                                        onCheckedChange={(checked) => updateTeam(stageIndex, gameIndex, teamIndex, { is_additional: checked })}
                                                      />
                                                      <Label className="text-sm">Добор</Label>
                                                    </div>
                                                  </div>
                                                </div>
                                              </div>
                                              
                                              {/* Баллы по конкурсам */}
                                              {game.contests && game.contests.length > 0 && (
                                                <div className="mt-4 space-y-2 border-t pt-4">
                                                  <Label className="text-sm font-semibold">Баллы по конкурсам</Label>
                                                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                                    {game.contests.map((contest) => (
                                                      <div key={contest} className="flex items-center gap-2">
                                                        <Label className="text-xs w-24 truncate">{contest}:</Label>
                                                        <Input 
                                                          type="number"
                                                          step="0.1"
                                                          className="h-8 text-sm"
                                                          value={team.scores?.[contest] || ''} 
                                                          onChange={(e) => {
                                                            const newScores = { ...(team.scores || {}) };
                                                            newScores[contest] = parseFloat(e.target.value) || 0;
                                                            updateTeam(stageIndex, gameIndex, teamIndex, { scores: newScores });
                                                          }}
                                                        />
                                                      </div>
                                                    ))}
                                                  </div>
                                                </div>
                                              )}
                                            </CardContent>
                                          </Card>
                                        ))}
                                      </div>
                                    ) : (
                                      <p className="text-sm text-muted-foreground">Нет команд. Добавьте команду для начала.</p>
                                    )}
                                  </div>
                                </CardContent>
                              </Card>
                            ))
                          ) : (
                            <p className="text-sm text-muted-foreground">Нет игр. Добавьте игру для начала.</p>
                          )}
                        </div>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">Нет стадий. Добавьте стадию для начала.</p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
