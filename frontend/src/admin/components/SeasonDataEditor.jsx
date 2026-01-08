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
import { Plus, X, ChevronDown, ChevronUp } from 'lucide-react';

export default function SeasonDataEditor({ seasonData, onChange }) {
  const [expandedStages, setExpandedStages] = useState(new Set());

  if (!seasonData) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-gray-500">Сезон ещё не обработан. Используйте скрипт process_seasons.py для парсинга.</p>
        </CardContent>
      </Card>
    );
  }

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
    const newData = { ...seasonData };
    newData.stages = [...newData.stages];
    newData.stages[stageIndex] = { ...newData.stages[stageIndex], ...updates };
    onChange(newData);
  };

  const updateGame = (stageIndex, gameIndex, updates) => {
    const newData = { ...seasonData };
    newData.stages = [...newData.stages];
    newData.stages[stageIndex] = { ...newData.stages[stageIndex] };
    newData.stages[stageIndex].games = [...newData.stages[stageIndex].games];
    newData.stages[stageIndex].games[gameIndex] = {
      ...newData.stages[stageIndex].games[gameIndex],
      ...updates
    };
    onChange(newData);
  };

  const updateTeam = (stageIndex, gameIndex, teamIndex, updates) => {
    const newData = { ...seasonData };
    newData.stages = [...newData.stages];
    newData.stages[stageIndex] = { ...newData.stages[stageIndex] };
    newData.stages[stageIndex].games = [...newData.stages[stageIndex].games];
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
                value={seasonData.league_name || ''} 
                onChange={(e) => onChange({ ...seasonData, league_name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Год</Label>
              <Input 
                type="number"
                value={seasonData.year || ''} 
                onChange={(e) => onChange({ ...seasonData, year: parseInt(e.target.value) || 0 })}
              />
            </div>
            <div className="space-y-2">
              <Label>Номер сезона</Label>
              <Input 
                type="number"
                value={seasonData.season_number || ''} 
                onChange={(e) => onChange({ ...seasonData, season_number: parseInt(e.target.value) || 0 })}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Победители (через запятую)</Label>
            <Input 
              value={Array.isArray(seasonData.winners) ? seasonData.winners.join(', ') : ''} 
              onChange={(e) => {
                const winners = e.target.value.split(',').map(w => w.trim()).filter(w => w);
                onChange({ ...seasonData, winners });
              }}
            />
          </div>
          <div className="space-y-2">
            <Label>Команды-участники (через запятую)</Label>
            <Textarea 
              value={seasonData.all_teams?.map(t => typeof t === 'string' ? t : t.name).join(', ') || ''} 
              onChange={(e) => {
                const names = e.target.value.split(',').map(n => n.trim()).filter(n => n);
                const all_teams = names.map(name => ({ slug: '', name }));
                onChange({ ...seasonData, all_teams });
              }}
              rows={3}
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
            <Textarea 
              value={seasonData.intro_html || ''} 
              onChange={(e) => onChange({ ...seasonData, intro_html: e.target.value })}
              rows={10}
              className="font-mono text-sm"
              placeholder="HTML-контент с описанием сезона (текст до результатов)"
            />
          </div>
          <div className="space-y-2">
            <Label>Краткое описание (текст)</Label>
            <Textarea 
              value={seasonData.description || ''} 
              onChange={(e) => onChange({ ...seasonData, description: e.target.value })}
              rows={3}
              placeholder="Краткое текстовое описание для превью"
            />
          </div>
        </CardContent>
      </Card>

      {/* Стадии */}
      <Card>
        <CardHeader>
          <CardTitle>Стадии сезона ({seasonData.stages?.length || 0})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {seasonData.stages?.map((stage, stageIndex) => (
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
                        <span className="font-semibold">{stage.name}</span>
                        <Badge variant="outline" className="ml-2">
                          {stage.games?.length || 0} игр
                        </Badge>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-4 pt-4">
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
                      <div className="space-y-4 mt-4">
                        <div className="flex items-center justify-between">
                          <Label className="text-lg">Игры ({stage.games?.length || 0})</Label>
                        </div>
                        {stage.games?.map((game, gameIndex) => (
                          <Card key={gameIndex} className="bg-gray-50">
                            <CardHeader className="pb-3">
                              <div className="flex items-center justify-between">
                                <CardTitle className="text-base">{game.name || `Игра ${gameIndex + 1}`}</CardTitle>
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

                              {/* Команды */}
                              <div className="space-y-2 mt-4">
                                <Label>Команды ({game.teams?.length || 0})</Label>
                                <div className="space-y-2">
                                  {game.teams?.map((team, teamIndex) => (
                                    <Card key={teamIndex} className="bg-white">
                                      <CardContent className="pt-4">
                                        <div className="grid md:grid-cols-4 gap-4">
                                          <div className="space-y-2">
                                            <Label>Команда</Label>
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
                                            <div className="flex gap-4 mt-2">
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
                                        
                                        {/* Конкурсы и баллы */}
                                        {team.scores && Object.keys(team.scores).length > 0 && (
                                          <div className="mt-4 space-y-2">
                                            <Label className="text-sm font-semibold">Баллы по конкурсам</Label>
                                            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                              {Object.entries(team.scores).map(([contest, score]) => (
                                                <div key={contest} className="flex items-center gap-2">
                                                  <Label className="text-xs w-20 truncate">{contest}:</Label>
                                                  <Input 
                                                    type="number"
                                                    step="0.1"
                                                    className="h-8 text-sm"
                                                    value={score || ''} 
                                                    onChange={(e) => {
                                                      const newScores = { ...team.scores };
                                                      newScores[contest] = parseFloat(e.target.value) || 0;
                                                      updateTeam(stageIndex, gameIndex, teamIndex, { scores: newScores });
                                                    }}
                                                  />
                                                </div>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                        
                                        {/* Список конкурсов игры (если есть) */}
                                        {game.contests && game.contests.length > 0 && (
                                          <div className="mt-4 space-y-2">
                                            <Label className="text-sm font-semibold">Конкурсы игры</Label>
                                            <div className="text-xs text-gray-600">
                                              {game.contests.join(', ')}
                                            </div>
                                          </div>
                                        )}
                                      </CardContent>
                                    </Card>
                                  ))}
                                </div>
                              </div>
                              
                              {/* Конкурсы игры */}
                              {game.contests && game.contests.length > 0 && (
                                <div className="space-y-2 mt-4">
                                  <Label>Конкурсы (через запятую)</Label>
                                  <Input 
                                    value={Array.isArray(game.contests) ? game.contests.join(', ') : ''} 
                                    onChange={(e) => {
                                      const contests = e.target.value.split(',').map(c => c.trim()).filter(c => c);
                                      updateGame(stageIndex, gameIndex, { contests });
                                    }}
                                  />
                                </div>
                              )}
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

