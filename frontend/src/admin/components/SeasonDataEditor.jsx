import { useState, useCallback, useMemo } from 'react';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Plus, FileText } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import TeamSelector from './TeamSelector';
import RichTextEditor from './RichTextEditor';
import { SortableStage } from './season-editor/StageEditor';
import * as seasonOps from './season-editor/operations';
export { cloneGameForNewStage, mergeTeamIdentityUpdate, retainUnambiguousTeamLinks, hasUnmatchedPersonReferences } from './season-editor/operations';
export default function SeasonDataEditor({ seasonData, onChange }) {
  const [expandedStages, setExpandedStages] = useState(new Set());
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  );

  // Инициализируем seasonData если его нет (useMemo для стабильной ссылки в useCallback)
  const data = useMemo(() => seasonData || {
    league_name: '',
    year: 0,
    season_number: 0,
    winners: [],
    all_teams: [],
    intro_html: '',
    description: '',
    stages: []
  }, [seasonData]);

  // ID для drag-and-drop
  const stageIds = useMemo(() => 
    (data.stages || []).map((_, idx) => `stage-${idx}`),
    [data.stages]
  );

  const contestCopySources = useMemo(() => {
    const sources = [];
    (data.stages || []).forEach((stage, sIdx) => {
      (stage.games || []).forEach((game, gIdx) => {
        const gameName = game?.name ? String(game.name) : `Игра ${gIdx + 1}`;
        const stageName = stage?.name ? String(stage.name) : `Стадия ${sIdx + 1}`;
        sources.push({
          key: `${sIdx}:${gIdx}`,
          value: `${sIdx}:${gIdx}`,
          label: `${stageName} — ${gameName}`
        });
      });
    });
    return sources;
  }, [data.stages]);

  const handleStageDragEnd = useCallback((event) => {
    const { active, over } = event;
    if (!over || active.id === over.id || !data.stages) return;
    const fromIndex = parseInt(active.id.toString().replace('stage-', ''), 10);
    const toIndex = parseInt(over.id.toString().replace('stage-', ''), 10);
    if (fromIndex !== toIndex) onChange(seasonOps.reorderStages(data, fromIndex, toIndex));
  }, [data, onChange]);

  const handleGameDragEnd = useCallback((event, stageIndex) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const activeMatch = active.id.toString().match(/game-(\d+)-(\d+)/);
    const overMatch = over.id.toString().match(/game-(\d+)-(\d+)/);
    if (!activeMatch || !overMatch) return;
    const fromIndex = parseInt(activeMatch[2], 10);
    const toIndex = parseInt(overMatch[2], 10);
    if (fromIndex !== toIndex) onChange(seasonOps.reorderGames(data, stageIndex, fromIndex, toIndex));
  }, [data, onChange]);

  const handleTeamDragEnd = useCallback((event, stageIndex, gameIndex) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const activeMatch = active.id.toString().match(/team-(\d+)-(\d+)-(\d+)/);
    const overMatch = over.id.toString().match(/team-(\d+)-(\d+)-(\d+)/);
    if (!activeMatch || !overMatch) return;
    const fromIndex = parseInt(activeMatch[3], 10);
    const toIndex = parseInt(overMatch[3], 10);
    if (fromIndex !== toIndex) onChange(seasonOps.reorderTeams(data, stageIndex, gameIndex, fromIndex, toIndex));
  }, [data, onChange]);

  const moveGameToStage = useCallback((fromStageIndex, gameIndex, toStageIndex) => {
    onChange(seasonOps.moveGameToStage(data, fromStageIndex, gameIndex, toStageIndex));
  }, [data, onChange]);

  const copyGameToStage = useCallback((fromStageIndex, gameIndex, toStageIndex) => {
    onChange(seasonOps.copyGameToStage(data, fromStageIndex, gameIndex, toStageIndex));
  }, [data, onChange]);

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

  const toggleStage = (stageIndex) => {
    const newExpanded = new Set(expandedStages);
    if (newExpanded.has(stageIndex)) {
      newExpanded.delete(stageIndex);
    } else {
      newExpanded.add(stageIndex);
    }
    setExpandedStages(newExpanded);
  };

  const updateStage = (stageIndex, updates) => onChange(seasonOps.updateStage(data, stageIndex, updates));

  const addStage = () => onChange(seasonOps.addStage(data));


  const createTemplate = () => {
    // Проверяем, есть ли уже созданные стадии и игры
    const existingStages = data.stages || [];
    const totalGames = existingStages.reduce((sum, stage) => {
      return sum + (stage.games?.length || 0);
    }, 0);
    
    // Если уже есть более одной стадии и более одной игры, показываем предупреждение
    if (existingStages.length > 1 && totalGames > 1) {
      setShowTemplateDialog(true);
      return;
    }
    
    // Иначе сразу создаем шаблон
    applyTemplate();
  };

  const applyTemplate = () => {
    const newData = { ...data };
    
    // Создаем 4 стадии
    const stages = [
      {
        name: '1/8 финала',
        order: 1,
        games: [
          {
            name: 'Первая 1/8 финала',
            order: 1,
            date: '',
            host: '',
            jury: [],
            contests: ['Приветствие', 'Биатлон', 'Муз'],
            teams: [],
            notes: ''
          },
          {
            name: 'Вторая 1/8 финала',
            order: 2,
            date: '',
            host: '',
            jury: [],
            contests: [],
            teams: [],
            notes: ''
          },
          {
            name: 'Третья 1/8 финала',
            order: 3,
            date: '',
            host: '',
            jury: [],
            contests: [],
            teams: [],
            notes: ''
          },
          {
            name: 'Четвертая 1/8 финала',
            order: 4,
            date: '',
            host: '',
            jury: [],
            contests: [],
            teams: [],
            notes: ''
          }
        ],
        notes: '',
        additional_teams: [],
        additional_notes: ''
      },
      {
        name: '1/4 финала',
        order: 2,
        games: [
          {
            name: 'Первая 1/4 финала',
            order: 1,
            date: '',
            host: '',
            jury: [],
            contests: [],
            teams: [],
            notes: ''
          },
          {
            name: 'Вторая 1/4 финала',
            order: 2,
            date: '',
            host: '',
            jury: [],
            contests: [],
            teams: [],
            notes: ''
          },
          {
            name: 'Третья 1/4 финала',
            order: 3,
            date: '',
            host: '',
            jury: [],
            contests: [],
            teams: [],
            notes: ''
          }
        ],
        notes: '',
        additional_teams: [],
        additional_notes: ''
      },
      {
        name: '1/2 финала',
        order: 3,
        games: [
          {
            name: 'Первая 1/2 финала',
            order: 1,
            date: '',
            host: '',
            jury: [],
            contests: [],
            teams: [],
            notes: ''
          },
          {
            name: 'Вторая 1/2 финала',
            order: 2,
            date: '',
            host: '',
            jury: [],
            contests: [],
            teams: [],
            notes: ''
          }
        ],
        notes: '',
        additional_teams: [],
        additional_notes: ''
      },
      {
        name: 'Финал',
        order: 4,
        games: [
          {
            name: 'Финал',
            order: 1,
            date: '',
            host: '',
            jury: [],
            contests: [],
            teams: [],
            notes: ''
          }
        ],
        notes: '',
        additional_teams: [],
        additional_notes: ''
      }
    ];
    
    newData.stages = stages;
    onChange(newData);
    setShowTemplateDialog(false);
  };

  const removeStage = (stageIndex) => onChange(seasonOps.removeStage(data, stageIndex));


  const updateGame = (stageIndex, gameIndex, updates) => onChange(seasonOps.updateGame(data, stageIndex, gameIndex, updates));


  const addGame = (stageIndex) => onChange(seasonOps.addGame(data, stageIndex));


  const removeGame = (stageIndex, gameIndex) => onChange(seasonOps.removeGame(data, stageIndex, gameIndex));


  const updateTeam = (stageIndex, gameIndex, teamIndex, updates) => onChange(seasonOps.updateTeam(data, stageIndex, gameIndex, teamIndex, updates));


  const addTeamToGame = (stageIndex, gameIndex) => onChange(seasonOps.addTeamToGame(data, stageIndex, gameIndex));


  const removeTeamFromGame = (stageIndex, gameIndex, teamIndex) => onChange(seasonOps.removeTeamFromGame(data, stageIndex, gameIndex, teamIndex));


  const addContest = (stageIndex, gameIndex) => {
    const contestName = prompt('Введите название конкурса:');
    if (contestName && contestName.trim()) onChange(seasonOps.addContest(data, stageIndex, gameIndex, contestName));
  };


  const moveContest = (stageIndex, gameIndex, fromIndex, toIndex) => onChange(seasonOps.moveContest(data, stageIndex, gameIndex, fromIndex, toIndex));


  const renameContest = (stageIndex, gameIndex, contestIndex, newNameRaw) => {
    const newName = String(newNameRaw || '').trim();
    const contests = data?.stages?.[stageIndex]?.games?.[gameIndex]?.contests || [];
    if (newName && contests[contestIndex] !== newName && contests.includes(newName)) {
      alert('Такой конкурс уже есть в списке.');
      return;
    }
    onChange(seasonOps.renameContest(data, stageIndex, gameIndex, contestIndex, newName));
  };


  const copyContests = (dstStageIndex, dstGameIndex, srcStageIndex, srcGameIndex) => onChange(seasonOps.copyContests(data, dstStageIndex, dstGameIndex, srcStageIndex, srcGameIndex));


  const removeContest = (stageIndex, gameIndex, contestName) => onChange(seasonOps.removeContest(data, stageIndex, gameIndex, contestName));


  // Победители хранятся в формате редактора; unknown JSON fields остаются в объекте.
  const winnersValue = Array.isArray(data.winners)
    ? data.winners.map(winner => typeof winner === 'object' && winner !== null ? winner : { slug: winner, name: winner, city: '' })
    : [];

  const handleWinnersChange = (winners) => {
    onChange({ ...data, winners: seasonOps.formatWinners(winners) });
  };

  const allTeamsValue = Array.isArray(data.all_teams) ? data.all_teams : [];
  const handleAllTeamsChange = (teams) => onChange({ ...data, all_teams: teams });


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
          <div className="space-y-2">
            <Label htmlFor="season-editorial-notes">Редакционные заметки</Label>
            <Textarea
              id="season-editorial-notes"
              value={data.editorial_notes || ''}
              onChange={(e) => onChange({ ...data, editorial_notes: e.target.value })}
              rows={6}
              placeholder="Источники, расхождения и вопросы для редактора"
            />
            <p className="text-xs text-muted-foreground">Не отображаются на публичной странице сезона.</p>
          </div>
        </CardContent>
      </Card>

      {/* Стадии */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Стадии сезона ({data.stages?.length || 0})</CardTitle>
            <div className="flex items-center gap-2">
              <Button onClick={createTemplate} size="sm" variant="outline">
                <FileText className="h-4 w-4 mr-2" />
                Создать шаблон
              </Button>
              <Button onClick={addStage} size="sm" variant="outline">
                <Plus className="h-4 w-4 mr-2" />
                Добавить стадию
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {data.stages && data.stages.length > 0 ? (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleStageDragEnd}
            >
              <SortableContext
                items={stageIds}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-4">
                  {data.stages.map((stage, stageIndex) => {
                    const gameIds = (stage.games || []).map((_, idx) => `game-${stageIndex}-${idx}`);
                    return (
                      <div key={stageIndex}>
                        <SortableStage
                          stage={stage}
                          stageIndex={stageIndex}
                          isExpanded={expandedStages.has(stageIndex)}
                          onToggle={() => toggleStage(stageIndex)}
                          onUpdate={updateStage}
                          onDelete={removeStage}
                          onMoveGame={moveGameToStage}
                          onCopyGame={copyGameToStage}
                          data={data}
                          onAddGame={addGame}
                          onUpdateGame={updateGame}
                          onDeleteGame={removeGame}
                          onAddContest={addContest}
                          onRemoveContest={removeContest}
                          onRenameContest={renameContest}
                          onMoveContest={moveContest}
                          onCopyContests={copyContests}
                          contestCopySources={contestCopySources}
                          onAddTeam={addTeamToGame}
                          onRemoveTeam={removeTeamFromGame}
                          onUpdateTeam={updateTeam}
                          sensors={sensors}
                          handleGameDragEnd={handleGameDragEnd}
                          handleTeamDragEnd={handleTeamDragEnd}
                          seasonAllTeams={data.all_teams || []}
                        />
                      </div>
                    );
                  })}
                </div>
              </SortableContext>
            </DndContext>
          ) : (
            <p className="text-sm text-muted-foreground">Нет стадий. Добавьте стадию для начала.</p>
          )}
        </CardContent>
      </Card>

      {/* Диалог подтверждения создания шаблона */}
      <AlertDialog open={showTemplateDialog} onOpenChange={setShowTemplateDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Создать шаблон?</AlertDialogTitle>
            <AlertDialogDescription>
              Все уже созданные стадии будут удалены и заменены шаблоном с 4 стадиями (1/8 финала, 1/4 финала, 1/2 финала, Финал) и соответствующими играми.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction onClick={applyTemplate} className="bg-destructive text-destructive-foreground">
              Создать шаблон
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
