import { useState, useCallback, useMemo } from 'react';
import { 
  DndContext, closestCenter, KeyboardSensor, 
  PointerSensor, useSensor, useSensors
} from '@dnd-kit/core';
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates,
  verticalListSortingStrategy, useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { 
  Plus, X, Trash2, GripVertical, ChevronUp, ChevronDown, 
  Copy, ArrowRight, MoreHorizontal 
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatDecimalTrim, roundTo } from '@/utils/number';
import TeamSelector from './TeamSelector';
import GameTeamSelector from './GameTeamSelector';
import RichTextEditor from './RichTextEditor';

// Sortable Stage Component
function SortableStage({
  stage,
  stageIndex,
  isExpanded,
  onToggle,
  onUpdate,
  onDelete,
  onMoveGame,
  onCopyGame,
  data,
  onAddGame,
  onUpdateGame,
  onDeleteGame,
  onAddContest,
  onRemoveContest,
  onRenameContest,
  onMoveContest,
  onCopyContests,
  contestCopySources = [],
  onAddTeam,
  onRemoveTeam,
  onUpdateTeam,
  sensors,
  handleGameDragEnd,
  seasonAllTeams = []
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: `stage-${stageIndex}` });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1
  };

  return (
    <div ref={setNodeRef} style={style}>
      <Accordion 
        type="single" 
        collapsible
        value={isExpanded ? `stage-${stageIndex}` : undefined}
        onValueChange={onToggle}
      >
        <AccordionItem value={`stage-${stageIndex}`}>
          <AccordionTrigger className="hover:no-underline">
            <div className="flex items-center justify-between w-full pr-4">
              <div className="flex items-center gap-2 flex-1">
                <button
                  {...attributes}
                  {...listeners}
                  className="cursor-grab text-muted-foreground hover:text-foreground touch-none"
                  onClick={(e) => e.stopPropagation()}
                >
                  <GripVertical className="h-5 w-5" />
                </button>
                <div>
                  <span className="font-semibold">{stage.name || `Стадия ${stageIndex + 1}`}</span>
                  <Badge variant="outline" className="ml-2">
                    {stage.games?.length || 0} игр
                  </Badge>
                </div>
              </div>
            </div>
          </AccordionTrigger>
          <AccordionContent>
            <StageContent 
              stage={stage}
              stageIndex={stageIndex}
              onUpdate={onUpdate}
              onDelete={onDelete}
              onMoveGame={onMoveGame}
              onCopyGame={onCopyGame}
              allStages={data.stages || []}
              onAddGame={onAddGame}
              onUpdateGame={onUpdateGame}
              onDeleteGame={onDeleteGame}
              onAddContest={onAddContest}
              onRemoveContest={onRemoveContest}
              onRenameContest={onRenameContest}
              onMoveContest={onMoveContest}
              onCopyContests={onCopyContests}
              contestCopySources={contestCopySources}
              onAddTeam={onAddTeam}
              onRemoveTeam={onRemoveTeam}
              onUpdateTeam={onUpdateTeam}
              sensors={sensors}
              handleGameDragEnd={handleGameDragEnd}
              seasonAllTeams={seasonAllTeams}
            />
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}

// Sortable Game Component
function SortableGame({ 
  game, 
  gameIndex, 
  stageIndex, 
  onUpdate, 
  onDelete, 
  onMove, 
  onCopy, 
  allStages, 
  onAddContest, 
  onRemoveContest,
  onRenameContest,
  onMoveContest,
  onCopyContests,
  contestCopySources = [],
  onAddTeam, 
  onRemoveTeam, 
  onUpdateTeam, 
  seasonAllTeams = [] 
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: `game-${stageIndex}-${gameIndex}` });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1
  };

  return (
    <div ref={setNodeRef} style={style}>
      <Card className="bg-gray-50">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-1">
              <button
                {...attributes}
                {...listeners}
                className="cursor-grab text-muted-foreground hover:text-foreground touch-none"
              >
                <GripVertical className="h-4 w-4" />
              </button>
              <CardTitle className="text-base">{game.name || `Игра ${gameIndex + 1}`}</CardTitle>
            </div>
            <div className="flex items-center gap-1">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <div className="px-2 py-1.5 text-sm font-semibold">Копировать в стадию:</div>
                  {allStages.map((stage, idx) => {
                    if (idx === stageIndex) return null;
                    return (
                      <DropdownMenuItem 
                        key={`copy-${idx}`}
                        onClick={() => onCopy(stageIndex, gameIndex, idx)}
                      >
                        <Copy className="mr-2 h-4 w-4" />
                        {stage.name || `Стадия ${idx + 1}`}
                      </DropdownMenuItem>
                    );
                  })}
                  {allStages.length <= 1 && (
                    <DropdownMenuItem disabled>
                      Нет других стадий
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <div className="px-2 py-1.5 text-sm font-semibold">Перенести в стадию:</div>
                  {allStages.map((stage, idx) => {
                    if (idx === stageIndex) return null;
                    return (
                      <DropdownMenuItem 
                        key={`move-${idx}`}
                        onClick={() => onMove(stageIndex, gameIndex, idx)}
                      >
                        <ArrowRight className="mr-2 h-4 w-4" />
                        {stage.name || `Стадия ${idx + 1}`}
                      </DropdownMenuItem>
                    );
                  })}
                  {allStages.length <= 1 && (
                    <DropdownMenuItem disabled>
                      Нет других стадий
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem 
                    onClick={() => onDelete(stageIndex, gameIndex)}
                    className="text-destructive"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Удалить
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </CardHeader>
        <GameContent 
          game={game}
          gameIndex={gameIndex}
          stageIndex={stageIndex}
          onUpdate={onUpdate}
          onAddContest={onAddContest}
          onRemoveContest={onRemoveContest}
          onRenameContest={onRenameContest}
          onMoveContest={onMoveContest}
          onCopyContests={onCopyContests}
          contestCopySources={contestCopySources}
          onAddTeam={onAddTeam}
          onRemoveTeam={onRemoveTeam}
          onUpdateTeam={onUpdateTeam}
          seasonAllTeams={seasonAllTeams}
        />
      </Card>
    </div>
  );
}

// Stage Content Component
function StageContent({ 
  stage, 
  stageIndex, 
  onUpdate, 
  onDelete, 
  onMoveGame, 
  onCopyGame, 
  allStages,
  onAddGame,
  onUpdateGame,
  onDeleteGame,
  onAddContest,
  onRemoveContest,
  onRenameContest,
  onMoveContest,
  onCopyContests,
  contestCopySources = [],
  onAddTeam,
  onRemoveTeam,
  onUpdateTeam,
  sensors,
  handleGameDragEnd,
  seasonAllTeams = []
}) {
  const updateStage = (updates) => {
    onUpdate(stageIndex, updates);
  };

  const gameIds = (stage.games || []).map((_, idx) => `game-${stageIndex}-${idx}`);

  return (
    <div className="space-y-4 pt-4">
      <div className="flex items-center justify-between">
        <h4 className="font-semibold">Настройки стадии</h4>
        <Button 
          onClick={() => onDelete(stageIndex)} 
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
            onChange={(e) => updateStage({ name: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label>Порядок</Label>
          <Input 
            type="number"
            value={stage.order || 0} 
            onChange={(e) => updateStage({ order: parseInt(e.target.value) || 0 })}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>Заметки к стадии (HTML)</Label>
        <RichTextEditor
          content={stage.notes || ''}
          onChange={(html) => updateStage({ notes: html })}
          placeholder="Дополнительная информация по стадии"
          minHeight={200}
        />
      </div>
      <div className="space-y-2">
        <Label>Доборы после стадии (команды через запятую)</Label>
        <Input 
          value={Array.isArray(stage.additional_teams) ? stage.additional_teams.join(', ') : ''} 
          onChange={(e) => {
            const additional_teams = e.target.value.split(',').map(t => t.trim()).filter(t => t);
            updateStage({ additional_teams });
          }}
          placeholder="Названия команд, прошедших добором"
        />
      </div>
      <div className="space-y-2">
        <Label>Комментарий к доборам</Label>
        <Textarea 
          value={stage.additional_notes || ''} 
          onChange={(e) => updateStage({ additional_notes: e.target.value })}
          rows={2}
          placeholder="Текст о доборах (например: 'После всех игр жюри добрали...')"
        />
      </div>

      {/* Игры */}
      <div className="space-y-4 mt-4 border-t pt-4">
        <div className="flex items-center justify-between">
          <Label className="text-lg">Игры ({stage.games?.length || 0})</Label>
          <Button onClick={() => onAddGame(stageIndex)} size="sm" variant="outline">
            <Plus className="h-4 w-4 mr-2" />
            Добавить игру
          </Button>
        </div>
        {stage.games && stage.games.length > 0 ? (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={(e) => handleGameDragEnd(e, stageIndex)}
          >
            <SortableContext
              items={gameIds}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-4">
                {stage.games.map((game, gameIndex) => (
                  <SortableGame
                    key={gameIndex}
                    game={game}
                    gameIndex={gameIndex}
                    stageIndex={stageIndex}
                    onUpdate={onUpdateGame}
                    onDelete={onDeleteGame}
                    onMove={onMoveGame}
                    onCopy={onCopyGame}
                    allStages={allStages}
                    onAddContest={onAddContest}
                    onRemoveContest={onRemoveContest}
                    onRenameContest={onRenameContest}
                    onMoveContest={onMoveContest}
                    onCopyContests={onCopyContests}
                    contestCopySources={contestCopySources.filter(s => s.value !== `${stageIndex}:${gameIndex}`)}
                    onAddTeam={onAddTeam}
                    onRemoveTeam={onRemoveTeam}
                    onUpdateTeam={onUpdateTeam}
                    seasonAllTeams={seasonAllTeams}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        ) : (
          <p className="text-sm text-muted-foreground">Нет игр. Добавьте игру для начала.</p>
        )}
      </div>
    </div>
  );
}

// Game Content Component
function GameContent({ 
  game, 
  gameIndex, 
  stageIndex, 
  onUpdate, 
  onAddContest, 
  onRemoveContest,
  onRenameContest,
  onMoveContest,
  onCopyContests,
  contestCopySources = [],
  onAddTeam, 
  onRemoveTeam, 
  onUpdateTeam, 
  seasonAllTeams = [] 
}) {
  const updateGame = (updates) => {
    onUpdate(stageIndex, gameIndex, updates);
  };

  return (
    <CardContent className="space-y-4">
      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Название игры</Label>
          <Input 
            value={game.name || ''} 
            onChange={(e) => updateGame({ name: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label>Дата</Label>
          <Input 
            value={game.date || ''} 
            onChange={(e) => updateGame({ date: e.target.value })}
            placeholder="YYYY-MM-DD"
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>Ведущий</Label>
        <Input 
          value={game.host || ''} 
          onChange={(e) => updateGame({ host: e.target.value })}
        />
      </div>
      <div className="space-y-2">
        <Label>Жюри (через запятую)</Label>
        <Input 
          value={Array.isArray(game.jury) ? game.jury.join(', ') : ''} 
          onChange={(e) => {
            const jury = e.target.value.split(',').map(j => j.trim()).filter(j => j);
            updateGame({ jury });
          }}
        />
      </div>

      {/* Конкурсы */}
      <div className="space-y-2 mt-4 border-t pt-4">
        <div className="flex items-center justify-between">
          <Label>Конкурсы ({game.contests?.length || 0})</Label>
          <Button 
            onClick={() => onAddContest(stageIndex, gameIndex)} 
            size="sm" 
            variant="outline"
          >
            <Plus className="h-4 w-4 mr-2" />
            Добавить конкурс
          </Button>
        </div>
        {contestCopySources.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <Label className="text-xs text-muted-foreground">Скопировать из игры:</Label>
            <select
              className="h-8 rounded-md border bg-background px-2 text-sm"
              defaultValue=""
              onChange={(e) => {
                const val = e.target.value;
                if (!val) return;
                const [srcStage, srcGame] = val.split(':').map(v => parseInt(v, 10));
                if (Number.isFinite(srcStage) && Number.isFinite(srcGame)) {
                  onCopyContests(stageIndex, gameIndex, srcStage, srcGame);
                  e.target.value = '';
                }
              }}
            >
              <option value="">— выбрать —</option>
              {contestCopySources.map(src => (
                <option key={src.key} value={src.value}>{src.label}</option>
              ))}
            </select>
          </div>
        )}
        {game.contests && game.contests.length > 0 && (
          <div className="space-y-2">
            {game.contests.map((contest, contestIndex) => (
              <div key={`contest-${contestIndex}`} className="flex items-center gap-2">
                <Input
                  className="h-8"
                  value={contest}
                  onChange={(e) => onRenameContest(stageIndex, gameIndex, contestIndex, e.target.value)}
                  placeholder="Название конкурса"
                />
                <Button
                  type="button"
                  size="icon"
                  variant="outline"
                  disabled={contestIndex === 0}
                  onClick={() => onMoveContest(stageIndex, gameIndex, contestIndex, contestIndex - 1)}
                  title="Вверх"
                >
                  <ChevronUp className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  size="icon"
                  variant="outline"
                  disabled={contestIndex === (game.contests.length - 1)}
                  onClick={() => onMoveContest(stageIndex, gameIndex, contestIndex, contestIndex + 1)}
                  title="Вниз"
                >
                  <ChevronDown className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="text-destructive hover:text-destructive"
                  onClick={() => onRemoveContest(stageIndex, gameIndex, contest)}
                  title="Удалить"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Команды */}
      <div className="space-y-2 mt-4 border-t pt-4">
        <div className="flex items-center justify-between">
          <Label>Команды ({game.teams?.length || 0})</Label>
          <Button 
            onClick={() => onAddTeam(stageIndex, gameIndex)} 
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
                      onClick={() => onRemoveTeam(stageIndex, gameIndex, teamIndex)} 
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
                      <GameTeamSelector
                        value={team}
                        onChange={(selectedTeam) => {
                          if (selectedTeam) {
                            onUpdateTeam(stageIndex, gameIndex, teamIndex, selectedTeam);
                          } else {
                            onUpdateTeam(stageIndex, gameIndex, teamIndex, { 
                              team_slug: '', 
                              team_name: '', 
                              city: '' 
                            });
                          }
                        }}
                        existingTeams={game.teams?.filter((t, idx) => idx !== teamIndex) || []}
                        seasonAllTeams={seasonAllTeams}
                        placeholder="Выберите команду..."
                        allowCustom={false}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Место</Label>
                      <Input 
                        type="number"
                        value={team.place || ''} 
                        onChange={(e) => onUpdateTeam(stageIndex, gameIndex, teamIndex, { place: parseInt(e.target.value) || 0 })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Итого (автосумма)</Label>
                      <Input 
                        type="number"
                        step="0.01"
                        value={(() => {
                          // Автоматически вычисляем сумму баллов за все конкурсы
                          if (game.contests && game.contests.length > 0 && team.scores) {
                            const sum = game.contests.reduce((acc, contest) => {
                              const score = team.scores[contest];
                              return acc + (typeof score === 'number' ? score : 0);
                            }, 0);
                            return formatDecimalTrim(roundTo(sum, 2), 2);
                          }
                          if (team.total === null || team.total === undefined) return '';
                          return formatDecimalTrim(roundTo(team.total, 2), 2);
                        })()}
                        onChange={(e) => {
                          // Позволяем вручную изменить, если нужно
                          const manualTotal = parseFloat(e.target.value);
                          if (!isNaN(manualTotal)) {
                            onUpdateTeam(stageIndex, gameIndex, teamIndex, { total: roundTo(manualTotal, 2) });
                          }
                        }}
                        readOnly={game.contests && game.contests.length > 0}
                        className={game.contests && game.contests.length > 0 ? "bg-muted" : ""}
                      />
                    </div>
                    <div className="space-y-2 flex flex-col">
                      <Label>Флаги</Label>
                      <div className="flex flex-col gap-2 mt-2">
                        <div className="flex items-center gap-2">
                          <Checkbox 
                            checked={team.passed || false}
                            onCheckedChange={(checked) => onUpdateTeam(stageIndex, gameIndex, teamIndex, { passed: checked })}
                          />
                          <Label className="text-sm">Прошёл</Label>
                        </div>
                        <div className="flex items-center gap-2">
                          <Checkbox 
                            checked={team.is_winner || false}
                            onCheckedChange={(checked) => onUpdateTeam(stageIndex, gameIndex, teamIndex, { is_winner: checked })}
                          />
                          <Label className="text-sm">Победитель</Label>
                        </div>
                        <div className="flex items-center gap-2">
                          <Checkbox 
                            checked={team.is_additional || false}
                            onCheckedChange={(checked) => onUpdateTeam(stageIndex, gameIndex, teamIndex, { is_additional: checked })}
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
                              step="0.01"
                              className="h-8 text-sm"
                              value={(() => {
                                const score = team.scores?.[contest];
                                if (score === null || score === undefined) return '';
                                return formatDecimalTrim(roundTo(score, 2), 2);
                              })()} 
                              onChange={(e) => {
                                const newScores = { ...(team.scores || {}) };
                                const val = e.target.value;
                                // Разрешаем 0 и пустую строку
                                if (val === '' || val === null || val === undefined) {
                                  newScores[contest] = 0;
                                } else {
                                  const numVal = parseFloat(val);
                                  newScores[contest] = isNaN(numVal) ? 0 : roundTo(numVal, 2);
                                }
                                
                                // Автоматически вычисляем сумму
                                const total = game.contests.reduce((acc, c) => {
                                  const score = newScores[c] ?? 0;
                                  return acc + (typeof score === 'number' ? score : 0);
                                }, 0);
                                
                                onUpdateTeam(stageIndex, gameIndex, teamIndex, { 
                                  scores: newScores,
                                  total: roundTo(total, 2)
                                });
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
  );
}

export default function SeasonDataEditor({ seasonData, onChange }) {
  const [expandedStages, setExpandedStages] = useState(new Set());

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  );

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

  // Drag and drop для стадий
  const handleStageDragEnd = useCallback((event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    
    const activeIndex = parseInt(active.id.toString().replace('stage-', ''));
    const overIndex = parseInt(over.id.toString().replace('stage-', ''));
    
    if (activeIndex !== overIndex && data.stages) {
      const newData = { ...data };
      const newStages = arrayMove(newData.stages, activeIndex, overIndex);
      // Обновляем порядок
      newStages.forEach((stage, idx) => {
        stage.order = idx + 1;
      });
      onChange({ ...newData, stages: newStages });
    }
  }, [data, onChange]);

  // Drag and drop для игр внутри стадии
  const handleGameDragEnd = useCallback((event, stageIndex) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    
    const activeId = active.id.toString();
    const overId = over.id.toString();
    
    // Извлекаем индексы из ID вида "game-stageIndex-gameIndex"
    const activeMatch = activeId.match(/game-(\d+)-(\d+)/);
    const overMatch = overId.match(/game-(\d+)-(\d+)/);
    
    if (!activeMatch || !overMatch) return;
    const activeGameIndex = parseInt(activeMatch[2]);
    const overGameIndex = parseInt(overMatch[2]);
    
    if (activeGameIndex !== overGameIndex && data.stages && data.stages[stageIndex]?.games) {
      const newData = { ...data };
      const newGames = arrayMove(newData.stages[stageIndex].games, activeGameIndex, overGameIndex);
      // Обновляем порядок
      newGames.forEach((game, idx) => {
        game.order = idx + 1;
      });
      newData.stages[stageIndex].games = newGames;
      onChange(newData);
    }
  }, [data, onChange]);

  // Перенос игры в другую стадию
  const moveGameToStage = useCallback((fromStageIndex, gameIndex, toStageIndex) => {
    if (!data.stages) return;
    const newData = { ...data };
    
    const game = newData.stages[fromStageIndex]?.games?.[gameIndex];
    if (!game) return;
    
    // Удаляем игру из исходной стадии
    newData.stages[fromStageIndex].games = newData.stages[fromStageIndex].games.filter((_, i) => i !== gameIndex);
    
    // Добавляем в новую стадию
    if (!newData.stages[toStageIndex].games) {
      newData.stages[toStageIndex].games = [];
    }
    const maxOrder = newData.stages[toStageIndex].games.length > 0
      ? Math.max(...newData.stages[toStageIndex].games.map(g => g.order || 0))
      : 0;
    game.order = maxOrder + 1;
    newData.stages[toStageIndex].games = [...newData.stages[toStageIndex].games, game];
    
    onChange(newData);
  }, [data, onChange]);

  // Копирование игры в другую стадию
  const copyGameToStage = useCallback((fromStageIndex, gameIndex, toStageIndex) => {
    if (!data.stages) return;
    const newData = { ...data };
    
    const game = newData.stages[fromStageIndex]?.games?.[gameIndex];
    if (!game) return;
    
    // Создаем глубокую копию игры
    const gameCopy = JSON.parse(JSON.stringify(game));
    gameCopy.name = `${gameCopy.name || `Игра ${gameIndex + 1}`} (копия)`;
    
    // Добавляем в целевую стадию
    if (!newData.stages[toStageIndex].games) {
      newData.stages[toStageIndex].games = [];
    }
    const maxOrder = newData.stages[toStageIndex].games.length > 0
      ? Math.max(...newData.stages[toStageIndex].games.map(g => g.order || 0))
      : 0;
    gameCopy.order = maxOrder + 1;
    newData.stages[toStageIndex].games = [...newData.stages[toStageIndex].games, gameCopy];
    
    onChange(newData);
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
      const trimmedContestName = contestName.trim();
      newData.stages[stageIndex].games[gameIndex].contests = [
        ...newData.stages[stageIndex].games[gameIndex].contests,
        trimmedContestName
      ];
      // Добавляем поле scores для всех команд и пересчитываем total
      if (newData.stages[stageIndex].games[gameIndex].teams) {
        const allContests = newData.stages[stageIndex].games[gameIndex].contests;
        newData.stages[stageIndex].games[gameIndex].teams = 
          newData.stages[stageIndex].games[gameIndex].teams.map(team => {
            const newScores = {
              ...(team.scores || {}),
              [trimmedContestName]: 0
            };
            // Пересчитываем total
            const total = allContests.reduce((acc, c) => {
              const score = newScores[c] ?? 0;
              return acc + (typeof score === 'number' ? score : 0);
            }, 0);
            return {
              ...team,
              scores: newScores,
              total: roundTo(total, 2)
            };
          });
      }
      onChange(newData);
    }
  };

  const moveContest = (stageIndex, gameIndex, fromIndex, toIndex) => {
    const newData = { ...data };
    if (!newData.stages) return;
    newData.stages = [...newData.stages];
    if (!newData.stages[stageIndex]?.games) return;
    newData.stages[stageIndex] = { ...newData.stages[stageIndex] };
    newData.stages[stageIndex].games = [...newData.stages[stageIndex].games];
    const gameRef = { ...newData.stages[stageIndex].games[gameIndex] };
    const contests = [...(gameRef.contests || [])];
    if (fromIndex < 0 || fromIndex >= contests.length) return;
    if (toIndex < 0 || toIndex >= contests.length) return;
    const [moved] = contests.splice(fromIndex, 1);
    contests.splice(toIndex, 0, moved);
    gameRef.contests = contests;
    newData.stages[stageIndex].games[gameIndex] = gameRef;
    onChange(newData);
  };

  const renameContest = (stageIndex, gameIndex, contestIndex, newNameRaw) => {
    const newName = (newNameRaw || '').trim();
    const newData = { ...data };
    if (!newData.stages) return;
    newData.stages = [...newData.stages];
    if (!newData.stages[stageIndex]?.games) return;
    newData.stages[stageIndex] = { ...newData.stages[stageIndex] };
    newData.stages[stageIndex].games = [...newData.stages[stageIndex].games];
    const gameRef = { ...newData.stages[stageIndex].games[gameIndex] };
    const contests = [...(gameRef.contests || [])];
    if (contestIndex < 0 || contestIndex >= contests.length) return;
    const oldName = contests[contestIndex];
    if (!newName || newName === oldName) return;
    if (contests.includes(newName)) {
      alert('Такой конкурс уже есть в списке.');
      return;
    }
    contests[contestIndex] = newName;
    gameRef.contests = contests;

    if (Array.isArray(gameRef.teams)) {
      gameRef.teams = gameRef.teams.map(team => {
        const scores = { ...(team.scores || {}) };
        if (Object.prototype.hasOwnProperty.call(scores, oldName)) {
          scores[newName] = scores[oldName];
          delete scores[oldName];
        } else if (!Object.prototype.hasOwnProperty.call(scores, newName)) {
          scores[newName] = 0;
        }
        const total = contests.reduce((acc, c) => {
          const score = scores[c] ?? 0;
          return acc + (typeof score === 'number' ? score : 0);
        }, 0);
        return { ...team, scores, total: roundTo(total, 2) };
      });
    }

    newData.stages[stageIndex].games[gameIndex] = gameRef;
    onChange(newData);
  };

  const copyContests = (dstStageIndex, dstGameIndex, srcStageIndex, srcGameIndex) => {
    const sourceGame = data?.stages?.[srcStageIndex]?.games?.[srcGameIndex];
    if (!sourceGame) return;
    const sourceContests = Array.isArray(sourceGame.contests) ? sourceGame.contests : [];

    const newData = { ...data };
    if (!newData.stages) return;
    newData.stages = [...newData.stages];
    if (!newData.stages[dstStageIndex]?.games) return;
    newData.stages[dstStageIndex] = { ...newData.stages[dstStageIndex] };
    newData.stages[dstStageIndex].games = [...newData.stages[dstStageIndex].games];
    const dstGame = { ...newData.stages[dstStageIndex].games[dstGameIndex] };
    dstGame.contests = [...sourceContests];

    if (Array.isArray(dstGame.teams)) {
      dstGame.teams = dstGame.teams.map(team => {
        const oldScores = team.scores || {};
        const scores = {};
        for (const c of dstGame.contests) {
          const v = oldScores[c];
          scores[c] = typeof v === 'number' ? roundTo(v, 2) : 0;
        }
        const total = dstGame.contests.reduce((acc, c) => acc + (scores[c] ?? 0), 0);
        return { ...team, scores, total: roundTo(total, 2) };
      });
    }

    newData.stages[dstStageIndex].games[dstGameIndex] = dstGame;
    onChange(newData);
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
    // Удаляем scores для этого конкурса у всех команд и пересчитываем total
    if (newData.stages[stageIndex].games[gameIndex].teams) {
      const remainingContests = newData.stages[stageIndex].games[gameIndex].contests;
      newData.stages[stageIndex].games[gameIndex].teams = 
        newData.stages[stageIndex].games[gameIndex].teams.map(team => {
          const newScores = { ...(team.scores || {}) };
          delete newScores[contestName];
          // Пересчитываем total
          const total = remainingContests.reduce((acc, c) => {
            const score = newScores[c] ?? 0;
            return acc + (typeof score === 'number' ? score : 0);
          }, 0);
          return { ...team, scores: newScores, total: roundTo(total, 2) };
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
    </div>
  );
}
