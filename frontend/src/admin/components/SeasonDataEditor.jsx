import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { 
  Plus, X, Trash2, GripVertical, ChevronUp, ChevronDown, 
  Copy, ArrowRight, MoreHorizontal, ChevronRight, FileText, Table, List
} from 'lucide-react';
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { formatDecimalTrim, roundTo } from '@/utils/number';
import TeamSelector from './TeamSelector';
import GameTeamSelector from './GameTeamSelector';
import RichTextEditor from './RichTextEditor';

// Компонент для ввода баллов с локальным состоянием
// Синхронизируется с родителем только при потере фокуса
function ScoreInput({ value, onChange, onBlur, className }) {
  const [localValue, setLocalValue] = useState(() => {
    if (value === null || value === undefined) return '';
    if (typeof value === 'string') return value;
    return String(value);
  });
  const isFocusedRef = useRef(false);
  
  // Синхронизируем локальное значение с props только когда не в фокусе
  useEffect(() => {
    if (!isFocusedRef.current) {
      if (value === null || value === undefined) {
        setLocalValue('');
      } else if (typeof value === 'string') {
        setLocalValue(value);
      } else {
        setLocalValue(String(value));
      }
    }
  }, [value]);
  
  const handleChange = (e) => {
    let val = e.target.value;
    
    // Заменяем запятую на точку для поддержки русского формата
    val = val.replace(/,/g, '.');
    
    // Удаляем все кроме цифр, точки и минуса
    let cleaned = val.replace(/[^\d.-]/g, '');
    
    // Убираем лишние минусы (оставляем только в начале)
    if (cleaned.includes('-')) {
      const firstMinus = cleaned.indexOf('-');
      cleaned = (firstMinus === 0 ? '-' : '') + cleaned.replace(/-/g, '');
    }
    
    // Ограничиваем одной точкой
    const dotIndex = cleaned.indexOf('.');
    if (dotIndex !== -1) {
      cleaned = cleaned.substring(0, dotIndex + 1) + cleaned.substring(dotIndex + 1).replace(/\./g, '');
    }
    
    setLocalValue(cleaned);
  };
  
  const handleFocus = () => {
    isFocusedRef.current = true;
  };
  
  const handleBlur = (e) => {
    isFocusedRef.current = false;
    
    let val = localValue;
    
    // Очищаем частичный ввод
    if (val === '' || val === null || val === undefined || val === '-' || val === '.' || val === '-.') {
      setLocalValue('0');
      onBlur(0);
    } else {
      const numVal = parseFloat(val);
      if (!isNaN(numVal) && isFinite(numVal)) {
        const rounded = roundTo(numVal, 2);
        setLocalValue(String(rounded));
        onBlur(rounded);
      } else {
        setLocalValue('0');
        onBlur(0);
      }
    }
  };
  
  return (
    <Input 
      type="text"
      inputMode="decimal"
      className={className}
      value={localValue}
      onChange={handleChange}
      onFocus={handleFocus}
      onBlur={handleBlur}
    />
  );
}

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
  handleTeamDragEnd,
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
      <Card className="bg-white">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-1">
              <button
                {...attributes}
                {...listeners}
                className="cursor-grab text-muted-foreground hover:text-foreground touch-none"
                onClick={(e) => e.stopPropagation()}
              >
                <GripVertical className="h-5 w-5" />
              </button>
              <button
                type="button"
                onClick={onToggle}
                className="flex items-center gap-1 text-muted-foreground hover:text-foreground"
              >
                {isExpanded ? (
                  <ChevronDown className="h-5 w-5" />
                ) : (
                  <ChevronRight className="h-5 w-5" />
                )}
              </button>
              <div>
                <span className="font-semibold">{stage.name || `Стадия ${stageIndex + 1}`}</span>
                <Badge variant="outline" className="ml-2">
                  {stage.games?.length || 0} игр
                </Badge>
              </div>
            </div>
          </div>
        </CardHeader>
        {isExpanded && (
          <>
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
              handleTeamDragEnd={handleTeamDragEnd}
              seasonAllTeams={seasonAllTeams}
            />
            <div className="px-6 pb-4 pt-2 border-t">
              <button
                type="button"
                onClick={onToggle}
                className="flex items-center gap-1 text-muted-foreground hover:text-foreground text-sm"
              >
                <ChevronUp className="h-4 w-4" />
                Свернуть
              </button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

// Sortable Team Component
function SortableTeam({
  team,
  teamIndex,
  gameIndex,
  stageIndex,
  onUpdate,
  onRemove,
  game,
  seasonAllTeams,
  sensors
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: `team-${stageIndex}-${gameIndex}-${teamIndex}` });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1
  };

  return (
    <div ref={setNodeRef} style={style}>
      <Card className="bg-white">
        <CardContent className="pt-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <button
                {...attributes}
                {...listeners}
                className="cursor-grab text-muted-foreground hover:text-foreground touch-none"
                onClick={(e) => e.stopPropagation()}
              >
                <GripVertical className="h-4 w-4" />
              </button>
              <h5 className="font-semibold">Команда {teamIndex + 1}</h5>
            </div>
            <Button 
              onClick={() => onRemove(stageIndex, gameIndex, teamIndex)} 
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
                    onUpdate(stageIndex, gameIndex, teamIndex, selectedTeam);
                  } else {
                    onUpdate(stageIndex, gameIndex, teamIndex, { 
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
                onChange={(e) => onUpdate(stageIndex, gameIndex, teamIndex, { place: parseInt(e.target.value) || 0 })}
              />
            </div>
            <div className="space-y-2">
              <Label>Итого (автосумма)</Label>
              <Input 
                type="text"
                inputMode="decimal"
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
                  let val = e.target.value.replace(',', '.');
                  // Разрешаем только цифры, точку и минус в начале
                  if (val && !/^-?\d*\.?\d*$/.test(val)) {
                    return; // Игнорируем недопустимые символы
                  }
                  const manualTotal = parseFloat(val);
                  if (!isNaN(manualTotal)) {
                    onUpdate(stageIndex, gameIndex, teamIndex, { total: roundTo(manualTotal, 2) });
                  } else if (val === '') {
                    onUpdate(stageIndex, gameIndex, teamIndex, { total: 0 });
                  }
                }}
                onBlur={(e) => {
                  // При потере фокуса округляем значение
                  let val = e.target.value.replace(',', '.');
                  const manualTotal = parseFloat(val);
                  if (!isNaN(manualTotal)) {
                    onUpdate(stageIndex, gameIndex, teamIndex, { total: roundTo(manualTotal, 2) });
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
                    onCheckedChange={(checked) => onUpdate(stageIndex, gameIndex, teamIndex, { passed: checked })}
                  />
                  <Label className="text-sm">Прошёл</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox 
                    checked={team.is_winner || false}
                    onCheckedChange={(checked) => onUpdate(stageIndex, gameIndex, teamIndex, { is_winner: checked })}
                  />
                  <Label className="text-sm">Победитель</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox 
                    checked={team.is_additional || false}
                    onCheckedChange={(checked) => onUpdate(stageIndex, gameIndex, teamIndex, { is_additional: checked })}
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
                    <ScoreInput 
                      className="h-8 text-sm"
                      value={team.scores?.[contest]}
                      onBlur={(numValue) => {
                        const newScores = { ...(team.scores || {}) };
                        newScores[contest] = numValue;
                        
                        // Пересчитываем total
                        const total = game.contests.reduce((acc, c) => {
                          const score = newScores[c];
                          if (typeof score === 'number' && isFinite(score)) {
                            return acc + score;
                          }
                          return acc;
                        }, 0);
                        
                        onUpdate(stageIndex, gameIndex, teamIndex, { 
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
  seasonAllTeams = [],
  isExpanded = true,
  onToggleExpand,
  sensors,
  handleTeamDragEnd
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
              <button
                type="button"
                onClick={onToggleExpand}
                className="flex items-center gap-1 text-muted-foreground hover:text-foreground"
              >
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
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
        {isExpanded && (
          <>
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
              sensors={sensors}
              handleTeamDragEnd={handleTeamDragEnd}
            />
            <div className="px-6 pb-4 pt-2 border-t">
              <button
                type="button"
                onClick={onToggleExpand}
                className="flex items-center gap-1 text-muted-foreground hover:text-foreground text-sm"
              >
                <ChevronUp className="h-4 w-4" />
                Свернуть
              </button>
            </div>
          </>
        )}
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
  handleTeamDragEnd,
  seasonAllTeams = []
}) {
  const [expandedGames, setExpandedGames] = useState(new Set());

  const updateStage = (updates) => {
    onUpdate(stageIndex, updates);
  };

  const toggleGame = (gameIndex) => {
    const newExpanded = new Set(expandedGames);
    const gameKey = `${stageIndex}-${gameIndex}`;
    if (newExpanded.has(gameKey)) {
      newExpanded.delete(gameKey);
    } else {
      newExpanded.add(gameKey);
    }
    setExpandedGames(newExpanded);
  };

  const gameIds = (stage.games || []).map((_, idx) => `game-${stageIndex}-${idx}`);

  return (
    <div className="space-y-4 pt-4 px-6">
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
                {stage.games.map((game, gameIndex) => {
                  const gameKey = `${stageIndex}-${gameIndex}`;
                  const isExpanded = expandedGames.has(gameKey);
                  return (
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
                      isExpanded={isExpanded}
                      onToggleExpand={() => toggleGame(gameIndex)}
                      sensors={sensors}
                      handleTeamDragEnd={handleTeamDragEnd}
                    />
                  );
                })}
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
  seasonAllTeams = [],
  sensors,
  handleTeamDragEnd
}) {
  const [showTableDialog, setShowTableDialog] = useState(false);
  const [tableInput, setTableInput] = useState('');
  const [tableError, setTableError] = useState('');
  const [showListDialog, setShowListDialog] = useState(false);
  const [listInput, setListInput] = useState('');
  const [listError, setListError] = useState('');

  const updateGame = (updates) => {
    onUpdate(stageIndex, gameIndex, updates);
  };

  // Функция для нормализации названия (для сопоставления)
  const normalizeName = (name) => {
    return String(name || '').trim().toLowerCase();
  };

  // Функция для сопоставления заголовка конкурса с конкурсами из игры
  const matchContestName = (headerName, gameContests) => {
    const normalizedHeader = normalizeName(headerName);
    
    // Ищем точное совпадение
    let match = gameContests.find(contest => 
      normalizeName(contest) === normalizedHeader
    );
    
    if (match) return match;
    
    // Ищем частичное совпадение
    match = gameContests.find(contest => {
      const normalizedContest = normalizeName(contest);
      return normalizedContest.includes(normalizedHeader) || 
             normalizedHeader.includes(normalizedContest);
    });
    
    return match || null;
  };

  // Функция для сопоставления названия команды с командами-участниками
  const matchTeamName = (teamNameFromTable) => {
    if (!teamNameFromTable || !seasonAllTeams || seasonAllTeams.length === 0) {
      return null;
    }

    const normalizedTableName = normalizeName(teamNameFromTable);
    
    // Ищем точное совпадение (без учета регистра)
    let match = seasonAllTeams.find(team => {
      const teamName = normalizeName(team.name || team.team_name);
      return teamName === normalizedTableName;
    });

    if (match) {
      return {
        team_slug: match.slug || match.team_slug || '',
        team_name: match.name || match.team_name || '',
        city: match.city || ''
      };
    }

    // Ищем частичное совпадение (название содержит или содержится в)
    match = seasonAllTeams.find(team => {
      const teamName = normalizeName(team.name || team.team_name);
      return teamName.includes(normalizedTableName) || normalizedTableName.includes(teamName);
    });

    if (match) {
      return {
        team_slug: match.slug || match.team_slug || '',
        team_name: match.name || match.team_name || '',
        city: match.city || ''
      };
    }

    return null;
  };

  const parseTableData = (text) => {
    // Разбиваем на строки
    const lines = text.split('\n').map(line => line.trim()).filter(line => line);
    
    if (lines.length === 0) {
      return null;
    }

    // Парсим каждую строку - поддерживаем табуляцию, пробелы, запятые как разделители столбцов
    const rows = lines.map(line => {
      // Разделяем по табуляции, затем по запятым, затем по пробелам
      let cells = line.split(/\t/);
      if (cells.length === 1) {
        cells = line.split(/,/);
      }
      if (cells.length === 1) {
        // Пробуем разделить по нескольким пробелам
        cells = line.split(/\s{2,}/);
      }
      if (cells.length === 1) {
        // Последняя попытка - разделить по одному пробелу
        cells = line.split(/\s+/);
      }
      
      return cells.map(cell => cell.trim()).filter(cell => cell);
    });

    return rows;
  };

  // Парсинг списка команд (с нумерацией или без)
  const parseListData = (text) => {
    const lines = text.split('\n').map(line => line.trim()).filter(line => line);
    
    if (lines.length === 0) {
      return null;
    }

    const parsed = [];
    
    for (const line of lines) {
      // Поддерживаем два формата:
      // 1. С нумерацией: "1. Название (Город) – баллы" или "1. Название"
      // 2. Без нумерации: "Название (Город)" или "Название"
      
      // Убираем нумерацию в начале строки, если она есть
      const lineWithoutNumber = line.replace(/^\d+\.\s*/, '');
      
      // Пробуем полный формат с городом и баллами: "Название (Город) – баллы"
      let match = lineWithoutNumber.match(/^(.+?)\s*\(([^)]+)\)\s*[–-]\s*(.+)$/);
      
      if (match) {
        // Формат: "Название (Город) – баллы"
        const [, name, city, totalStr] = match;
        let total = null;
        
        if (totalStr) {
          // Извлекаем число из строки (может быть "10,7 балла" или "10.5" или "10")
          const numMatch = totalStr.match(/([\d,\.]+)/);
          if (numMatch) {
            const numStr = numMatch[1].replace(',', '.');
            total = parseFloat(numStr);
            if (isNaN(total)) total = null;
          }
        }
        
        parsed.push({
          name: name.trim(),
          city: city ? city.trim() : null,
          total: total
        });
      } else {
        // Пробуем формат с городом без баллов: "Название (Город)"
        match = lineWithoutNumber.match(/^(.+?)\s*\(([^)]+)\)\s*$/);
        if (match) {
          const [, name, city] = match;
          parsed.push({
            name: name.trim(),
            city: city ? city.trim() : null,
            total: null
          });
        } else {
          // Пробуем формат без города с баллами: "Название – баллы"
          match = lineWithoutNumber.match(/^(.+?)\s*[–-]\s*(.+)$/);
          if (match) {
            const [, name, totalStr] = match;
            let total = null;
            
            if (totalStr) {
              const numMatch = totalStr.match(/([\d,\.]+)/);
              if (numMatch) {
                const numStr = numMatch[1].replace(',', '.');
                total = parseFloat(numStr);
                if (isNaN(total)) total = null;
              }
            }
            
            parsed.push({
              name: name.trim(),
              city: null,
              total: total
            });
          } else {
            // Просто название: "Название"
            if (lineWithoutNumber.trim()) {
              parsed.push({
                name: lineWithoutNumber.trim(),
                city: null,
                total: null
              });
            }
          }
        }
      }
    }
    
    return parsed.length > 0 ? parsed : null;
  };

  const applyListData = () => {
    setListError('');
    
    const parsed = parseListData(listInput);
    
    if (!parsed || parsed.length === 0) {
      setListError('Не удалось распарсить список. Убедитесь, что каждая строка начинается с номера и точки (например: "1. Название команды").');
      return;
    }
    
    // Создаем команды из списка
    const newTeams = parsed.map((item, index) => {
      // Пытаемся найти команду в списке участников сезона
      const matchedTeam = matchTeamName(item.name);
      
      let teamName = item.name;
      let teamSlug = '';
      let city = item.city || '';
      
      if (matchedTeam) {
        teamName = matchedTeam.team_name;
        teamSlug = matchedTeam.team_slug || '';
        // Если город не указан в списке, но есть у найденной команды, используем его
        if (!city && matchedTeam.city) {
          city = matchedTeam.city;
        }
      }
      
      // Формируем полное название с городом, если нужно
      if (city && !teamName.includes(`(${city})`)) {
        teamName = `${teamName} (${city})`;
      }
      
      // Создаем объект команды
      const team = {
        team_slug: teamSlug,
        team_name: teamName,
        place: index + 1,
        total: item.total !== null ? item.total : 0,
        scores: {},
        passed: false,
        is_winner: false,
        is_additional: false,
        city: city
      };
      
      return team;
    });
    
    // Обновляем игру с новыми командами
    updateGame({ teams: newTeams });
    
    // Закрываем диалог
    setShowListDialog(false);
    setListInput('');
  };

  const applyTableData = () => {
    setTableError('');
    
    const allRows = parseTableData(tableInput);
    
    if (!allRows || allRows.length === 0) {
      setTableError('Не удалось распарсить таблицу. Убедитесь, что данные разделены табуляцией, запятыми или пробелами.');
      return;
    }

    if (allRows.length < 2) {
      setTableError('Таблица должна содержать минимум 2 строки: заголовки и хотя бы одну строку данных.');
      return;
    }

    // Первая строка - заголовки
    const headers = allRows[0];
    const dataRows = allRows.slice(1); // Остальные строки - данные
    
    if (headers.length < 2) {
      setTableError('В таблице должен быть хотя бы один столбец с конкурсом помимо названия команды.');
      return;
    }
    
    // Определяем индекс столбца с названием команды (обычно первый)
    const teamColumnIndex = 0;
    
    // Определяем индексы столбцов конкурсов и сами конкурсы.
    // Если конкурсы уже заданы в игре, стараемся сопоставить заголовки с ними.
    // Если конкурсов ещё нет, создаём их автоматически по заголовкам таблицы.
    const existingContests = game.contests || [];
    const contestColumnMap = new Map(); // contestName -> columnIndex
    let contestsToUse = [];
    
    if (existingContests.length > 0) {
      // Режим "обновления" — сопоставляем заголовки с уже существующими конкурсами
      existingContests.forEach((contest) => {
        const matchedHeaderIndex = headers.findIndex((header, index) => {
          if (index === teamColumnIndex) return false;
          const normalizedHeader = normalizeName(header);
          if (normalizedHeader === 'общий' || normalizedHeader === 'итого') return false;
          const matchedContest = matchContestName(header, [contest]);
          return Boolean(matchedContest);
        });
        if (matchedHeaderIndex !== -1) {
          contestColumnMap.set(contest, matchedHeaderIndex);
        }
      });
      
      const missingContests = existingContests.filter(c => !contestColumnMap.has(c));
      if (missingContests.length > 0) {
        setTableError(`Не найдены столбцы для конкурсов: ${missingContests.join(', ')}. Найденные заголовки: ${headers.slice(1).join(', ')}`);
        return;
      }
      
      contestsToUse = existingContests;
    } else {
      // Режим "создания" — конкурсы берём из заголовков таблицы
      const inferredContests = [];
      headers.forEach((header, index) => {
        if (index === teamColumnIndex) return;
        const normalizedHeader = normalizeName(header);
        if (normalizedHeader === 'общий' || normalizedHeader === 'итого') return;
        const contestName = String(header || '').trim();
        if (!contestName) return;
        inferredContests.push(contestName);
        contestColumnMap.set(contestName, index);
      });
      
      if (inferredContests.length === 0) {
        setTableError('Не удалось определить конкурсы по заголовкам таблицы. Убедитесь, что после столбца с названием команды есть столбцы с названиями конкурсов.');
        return;
      }
      
      contestsToUse = inferredContests;
    }
    
    // Формируем список команд на основе строк таблицы
    const newTeams = dataRows.map((row, idx) => {
      if (!row || row.length === 0) {
        return null;
      }
      
      const teamNameFromTable = row[teamColumnIndex] || '';
      const matchedTeam = matchTeamName(teamNameFromTable);
      
      let teamName = teamNameFromTable;
      let teamSlug = '';
      let city = '';
      
      if (matchedTeam) {
        teamName = matchedTeam.team_name;
        teamSlug = matchedTeam.team_slug || '';
        if (!city && matchedTeam.city) {
          city = matchedTeam.city;
        }
      }
      
      if (city && !teamName.includes(`(${city})`)) {
        teamName = `${teamName} (${city})`;
      }
      
      const scores = {};
      contestsToUse.forEach((contest) => {
        const columnIndex = contestColumnMap.get(contest);
        if (columnIndex !== undefined && row[columnIndex] !== undefined) {
          let value = String(row[columnIndex]).trim().replace(',', '.');
          const numValue = parseFloat(value);
          scores[contest] = !isNaN(numValue) && isFinite(numValue)
            ? roundTo(numValue, 2)
            : 0;
        } else {
          scores[contest] = 0;
        }
      });
      
      const total = contestsToUse.reduce((acc, c) => {
        const score = scores[c];
        return acc + (typeof score === 'number' && isFinite(score) ? score : 0);
      }, 0);
      
      return {
        team_slug: teamSlug,
        team_name: teamName,
        place: idx + 1,
        total: roundTo(total, 2),
        scores,
        passed: false,
        is_winner: false,
        is_additional: false,
        city
      };
    }).filter(Boolean);
    
    if (newTeams.length === 0) {
      setTableError('Не удалось распознать ни одной команды в таблице.');
      return;
    }
    
    // Обновляем игру: конкурсы (если нужно) и команды заполняются автоматически
    const updates = {
      teams: newTeams,
    };
    if (!existingContests.length) {
      updates.contests = contestsToUse;
    }
    updateGame(updates);

    setShowTableDialog(false);
    setTableInput('');
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
          <div className="flex items-center gap-2">
            {game.contests && game.contests.length > 0 && (
              <Button 
                onClick={() => {
                  setTableInput('');
                  setTableError('');
                  setShowTableDialog(true);
                }} 
                size="sm" 
                variant="outline"
              >
                <Table className="h-4 w-4 mr-2" />
                Вставить из таблицы
              </Button>
            )}
            <Button 
              onClick={() => {
                setListInput('');
                setListError('');
                setShowListDialog(true);
              }} 
              size="sm" 
              variant="outline"
            >
              <List className="h-4 w-4 mr-2" />
              Вставить из списка
            </Button>
            <Button 
              onClick={() => onAddTeam(stageIndex, gameIndex)} 
              size="sm" 
              variant="outline"
            >
              <Plus className="h-4 w-4 mr-2" />
              Добавить команду
            </Button>
          </div>
        </div>
        {game.teams && game.teams.length > 0 ? (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={(e) => handleTeamDragEnd(e, stageIndex, gameIndex)}
          >
            <SortableContext
              items={(game.teams || []).map((_, idx) => `team-${stageIndex}-${gameIndex}-${idx}`)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-2">
                {game.teams.map((team, teamIndex) => (
                  <SortableTeam
                    key={teamIndex}
                    team={team}
                    teamIndex={teamIndex}
                    gameIndex={gameIndex}
                    stageIndex={stageIndex}
                    onUpdate={onUpdateTeam}
                    onRemove={onRemoveTeam}
                    game={game}
                    seasonAllTeams={seasonAllTeams}
                    sensors={sensors}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        ) : (
          <p className="text-sm text-muted-foreground">Нет команд. Добавьте команду для начала.</p>
        )}
      </div>

      {/* Диалог вставки таблицы */}
      <Dialog open={showTableDialog} onOpenChange={setShowTableDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Вставить баллы из таблицы</DialogTitle>
            <DialogDescription>
              Вставьте таблицу с баллами. Первая строка — заголовки (название команды и конкурсы).
              Разделители: табуляция, запятая или пробелы. Десятичные числа можно вводить с запятой или точкой.
              <br />
              <br />
              Если в игре ещё нет конкурсов и команд, они будут автоматически созданы на основе заголовков и строк таблицы.
              Если конкурсы уже заданы, данные будут сопоставлены с ними по названиям.
              <br />
              <br />
              Столбцы "общий" и "Итого" будут автоматически пропущены.
              Названия команд будут попытаны сопоставиться с командами сезона; при совпадении привяжутся slug и город.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Таблица данных</Label>
              <Textarea
                value={tableInput}
                onChange={(e) => {
                  setTableInput(e.target.value);
                  setTableError('');
                }}
                placeholder={`Пример:\nКоманда\tПриветствие\tРазминка\tДЗ\nМужская сборная\t5\t5.4\t4.6\nВИАсиПЕД\t5\t4.6\t4`}
                rows={10}
                className="font-mono text-sm"
              />
              {tableError && (
                <p className="text-sm text-destructive">{tableError}</p>
              )}
            </div>
            {tableInput && (() => {
              const allRows = parseTableData(tableInput);
              if (!allRows || allRows.length === 0) return null;
              
              if (allRows.length < 2) return null;
              
              const headers = allRows[0];
              const dataRows = allRows.slice(1);
              const teamColumnIndex = 0;
              
              const existingContests = game.contests || [];
              const inferredContests =
                existingContests.length > 0
                  ? existingContests
                  : headers
                      .map((header, index) => ({ header, index }))
                      .filter(({ index }) => index !== teamColumnIndex)
                      .filter(({ header }) => {
                        const normalizedHeader = normalizeName(header);
                        return normalizedHeader !== 'общий' && normalizedHeader !== 'итого';
                      })
                      .map(({ header }) => String(header || '').trim())
                      .filter(Boolean);
              
              const contests = inferredContests;
              
              // Определяем индексы столбцов конкурсов
              const contestColumnMap = new Map();
              
              contests.forEach((contest) => {
                const headerIndex = headers.findIndex((header, index) => {
                  if (index === teamColumnIndex) return false;
                  const normalizedHeader = normalizeName(header);
                  if (normalizedHeader === 'общий' || normalizedHeader === 'итого') return false;
                  if (!existingContests.length) {
                    return normalizeName(header) === normalizeName(contest);
                  }
                  const matched = matchContestName(header, [contest]);
                  return Boolean(matched);
                });
                if (headerIndex !== -1) {
                  contestColumnMap.set(contest, headerIndex);
                }
              });
              
              const expectedRows = game.teams && game.teams.length > 0 ? game.teams.length : dataRows.length;
              const hasError =
                (game.teams && game.teams.length > 0 && dataRows.length !== expectedRows) ||
                contests.length === 0;
              
              return (
                <div className="space-y-2">
                  <Label className={`text-xs ${hasError ? 'text-destructive' : 'text-muted-foreground'}`}>
                    Предпросмотр {hasError && '(размеры не совпадают)'}:
                  </Label>
                  <div className="border rounded p-2 bg-muted max-h-60 overflow-auto">
                    <table className="text-xs">
                      <thead>
                        <tr>
                          <th className="text-left pr-4">Команда из таблицы</th>
                          <th className="text-left pr-4">Сопоставление</th>
                          {contests.map((contest, idx) => {
                            const colIndex = contestColumnMap.get(contest);
                            const headerName = colIndex !== undefined ? headers[colIndex] : '?';
                            const isMatched = colIndex !== undefined;
                            return (
                              <th key={idx} className={`text-left px-2 ${isMatched ? '' : 'text-destructive'}`}>
                                {contest}
                                {!isMatched && ' (не найден)'}
                                {isMatched && headerName !== contest && ` (${headerName})`}
                              </th>
                            );
                          })}
                        </tr>
                      </thead>
                      <tbody>
                        {dataRows.map((row, idx) => {
                          const teamNameFromTable = row[teamColumnIndex] || '';
                          const matchedTeam = matchTeamName(teamNameFromTable);
                          const matchStatus = matchedTeam 
                            ? `✓ ${matchedTeam.team_name}${matchedTeam.city ? ` (${matchedTeam.city})` : ''}`
                            : '✗ Не найдено';
                          return (
                            <tr key={idx}>
                              <td className="pr-4 font-medium">{teamNameFromTable}</td>
                              <td className={`pr-4 text-xs ${matchedTeam ? 'text-green-600' : 'text-orange-600'}`}>
                                {matchStatus}
                              </td>
                              {contests.map((contest, contestIdx) => {
                                const colIndex = contestColumnMap.get(contest);
                                const value = colIndex !== undefined && row[colIndex] !== undefined 
                                  ? row[colIndex] 
                                  : '-';
                                return (
                                  <td key={contestIdx} className="px-2">{value}</td>
                                );
                              })}
                            </tr>
                          );
                        })}
                        {dataRows.length < expectedRows && (
                          <tr>
                            <td colSpan={contests.length + 2} className="px-2 text-muted-foreground text-center">
                              (не хватает строк: {dataRows.length} из {expectedRows})
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })()}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowTableDialog(false)}>
              Отмена
            </Button>
            <Button onClick={applyTableData}>
              Применить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Диалог вставки из списка */}
      <Dialog open={showListDialog} onOpenChange={setShowListDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Вставить команды из списка</DialogTitle>
            <DialogDescription>
              Вставьте список команд. Формат:
              <br />
              <code className="text-xs">Название команды (Город)</code>
              <br />
              или с нумерацией:
              <br />
              <code className="text-xs">1. Название команды (Город) – баллы</code>
              <br />
              <br />
              Нумерация, город и баллы опциональны. Поддерживаются тире (–) и дефис (-).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Список команд</Label>
              <Textarea
                value={listInput}
                onChange={(e) => {
                  setListInput(e.target.value);
                  setListError('');
                }}
                placeholder={`Пример с нумерацией:\n1. НЗ (Нижний Новгород) – 10,7 балла\n2. Гураны (Чита) – 10,5\n3. Альтернатива (Астрахань) – 10,4\n\nИли без нумерации:\nТерритория игры (Красноярск)\nНайди (Ижевск)\nУГТУ (Ухта)\nПравильное решение (Оренбург)\nАндреичи (Новосибирск)`}
                rows={10}
                className="font-mono text-sm"
              />
              {listError && (
                <p className="text-sm text-destructive">{listError}</p>
              )}
            </div>
            {listInput && (() => {
              const parsed = parseListData(listInput);
              if (!parsed || parsed.length === 0) return null;
              
              return (
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">
                    Предпросмотр ({parsed.length} команд):
                  </Label>
                  <div className="border rounded p-2 bg-muted max-h-60 overflow-auto">
                    <div className="space-y-1 text-xs">
                      {parsed.map((item, idx) => {
                        const matchedTeam = matchTeamName(item.name);
                        const matchStatus = matchedTeam 
                          ? `✓ ${matchedTeam.team_name}${matchedTeam.city ? ` (${matchedTeam.city})` : ''}`
                          : '✗ Не найдено';
                        return (
                          <div key={idx} className="flex items-center gap-2 py-1 border-b last:border-0">
                            <span className="font-medium w-48">{item.name}</span>
                            {item.city && <span className="text-muted-foreground w-32">({item.city})</span>}
                            {item.total !== null && <span className="text-muted-foreground w-20">{item.total}</span>}
                            <span className={`text-xs flex-1 ${matchedTeam ? 'text-green-600' : 'text-orange-600'}`}>
                              {matchStatus}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              );
            })()}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowListDialog(false)}>
              Отмена
            </Button>
            <Button onClick={applyListData}>
              Применить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </CardContent>
  );
}

// Utility function to remove city name from team name (e.g., "Team Name (City)" -> "Team Name")
function removeCityFromName(name) {
  if (!name) return name;
  return name.replace(/\s*\([^)]+\)\s*$/, '').trim();
}

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

  // Drag and drop для команд внутри игры
  const handleTeamDragEnd = useCallback((event, stageIndex, gameIndex) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    
    const activeId = active.id.toString();
    const overId = over.id.toString();
    
    // Извлекаем индексы из ID вида "team-stageIndex-gameIndex-teamIndex"
    const activeMatch = activeId.match(/team-(\d+)-(\d+)-(\d+)/);
    const overMatch = overId.match(/team-(\d+)-(\d+)-(\d+)/);
    
    if (!activeMatch || !overMatch) return;
    const activeTeamIndex = parseInt(activeMatch[3]);
    const overTeamIndex = parseInt(overMatch[3]);
    
    if (activeTeamIndex !== overTeamIndex && data.stages && data.stages[stageIndex]?.games?.[gameIndex]?.teams) {
      const newData = { ...data };
      const newTeams = arrayMove(newData.stages[stageIndex].games[gameIndex].teams, activeTeamIndex, overTeamIndex);
      newData.stages[stageIndex].games[gameIndex].teams = newTeams;
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

    // Если в удаляемой игре есть команды с флагом "добор" — чистим их из additional_teams,
    // но только если такие команды больше не встречаются в оставшихся играх стадии.
    const stageBefore = newData.stages[stageIndex];
    const removedGame = stageBefore.games?.[gameIndex];
    const removedAdditionalNames = (removedGame?.teams || [])
      .filter(t => t?.is_additional)
      .map(t => String(t?.team_name || '').trim())
      .filter(Boolean);

    newData.stages[stageIndex].games = newData.stages[stageIndex].games.filter((_, i) => i !== gameIndex);

    if (removedAdditionalNames.length > 0) {
      // Клонируем stage, чтобы не мутировать ссылку на прежний объект
      newData.stages[stageIndex] = { ...newData.stages[stageIndex] };
      const stageAfter = newData.stages[stageIndex];
      const currentAdditional = Array.isArray(stageAfter.additional_teams) ? [...stageAfter.additional_teams] : [];

      const stillHasName = (name) => {
        const target = String(name || '').trim();
        if (!target) return false;
        const targetWithoutCity = removeCityFromName(target);
        return (stageAfter.games || []).some(g =>
          (g.teams || []).some(t => {
            const teamName = String(t?.team_name || '').trim();
            const teamNameWithoutCity = removeCityFromName(teamName);
            return t?.is_additional && (
              teamName === target || 
              teamNameWithoutCity === targetWithoutCity
            );
          })
        );
      };

      stageAfter.additional_teams = currentAdditional.filter(n => {
        const name = String(n || '').trim();
        if (!name) return false;
        const nameWithoutCity = removeCityFromName(name);
        // Проверяем как точное совпадение, так и совпадение без города
        const shouldRemove = removedAdditionalNames.some(removed => {
          const removedWithoutCity = removeCityFromName(removed);
          return name === removed || nameWithoutCity === removedWithoutCity;
        });
        // Удаляем только те имена, которые были "добором" в удаленной игре и больше нигде не отмечены
        if (shouldRemove && !stillHasName(name)) return false;
        return true;
      });
    }
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

    const prevTeam = newData.stages[stageIndex].games[gameIndex].teams[teamIndex] || {};
    const prevName = String(prevTeam.team_name || '').trim();
    const prevIsAdditional = !!prevTeam.is_additional;

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

    // Автоматически поддерживаем "Доборы после стадии" в sync с флагом "Добор"
    // Поведение: добавляем имя, когда ставят флаг, убираем — когда снимают.
    // При смене названия у команды-добора обновляем имя в списке.
    const nextTeam = newData.stages[stageIndex].games[gameIndex].teams[teamIndex] || {};
    let nextName = String(nextTeam.team_name || '').trim();
    const nextIsAdditional = !!nextTeam.is_additional;
    
    const shouldSyncAdditional =
      Object.prototype.hasOwnProperty.call(updates, 'is_additional') ||
      Object.prototype.hasOwnProperty.call(updates, 'team_name');

    if (shouldSyncAdditional) {
      const stage = newData.stages[stageIndex];
      const currentAdditional = Array.isArray(stage.additional_teams) ? [...stage.additional_teams] : [];

      const stageHasAdditionalName = (name, exclude = null) => {
        const target = String(name || '').trim();
        if (!target) return false;
        return (stage.games || []).some((g, gIdx) =>
          (g.teams || []).some((t, tIdx) => {
            if (exclude && exclude.gameIndex === gIdx && exclude.teamIndex === tIdx) return false;
            return t?.is_additional && String(t?.team_name || '').trim() === target;
          })
        );
      };

      let nextAdditional = currentAdditional
        .map(n => String(n || '').trim())
        .filter(Boolean);

      // Убираем город из скобок для additional_teams
      const prevNameWithoutCity = removeCityFromName(prevName);
      const nextNameWithoutCity = removeCityFromName(nextName);
      
      // 1) Если команда была добором и имя изменилось — удаляем старое имя (если оно больше нигде не используется)
      if (prevIsAdditional && prevNameWithoutCity && prevNameWithoutCity !== nextNameWithoutCity) {
        const stillUsed = stageHasAdditionalName(prevName, { gameIndex, teamIndex });
        if (!stillUsed) {
          // Удаляем как с городом, так и без (на случай, если было сохранено в разных форматах)
          nextAdditional = nextAdditional.filter(n => {
            const nWithoutCity = removeCityFromName(n);
            return nWithoutCity !== prevNameWithoutCity;
          });
        }
      }

      // 2) Если флаг сняли — удаляем имя (если оно больше нигде не используется)
      if (prevIsAdditional && !nextIsAdditional && prevNameWithoutCity) {
        const stillUsed = stageHasAdditionalName(prevName, { gameIndex, teamIndex });
        if (!stillUsed) {
          // Удаляем как с городом, так и без
          nextAdditional = nextAdditional.filter(n => {
            const nWithoutCity = removeCityFromName(n);
            return nWithoutCity !== prevNameWithoutCity;
          });
        }
      }

      // 3) Если флаг поставили — добавляем имя БЕЗ города (если оно задано)
      if (nextIsAdditional && nextNameWithoutCity) {
        // Проверяем, нет ли уже такого имени (без города) в списке
        const alreadyExists = nextAdditional.some(n => removeCityFromName(n) === nextNameWithoutCity);
        if (!alreadyExists) {
          nextAdditional.push(nextNameWithoutCity);
        }
      }

      // 4) Если команда остается добором, но имя появилось/обновилось — убеждаемся, что новое имя есть (БЕЗ города)
      if (prevIsAdditional && nextIsAdditional && nextNameWithoutCity) {
        // Проверяем, нет ли уже такого имени (без города) в списке
        const alreadyExists = nextAdditional.some(n => removeCityFromName(n) === nextNameWithoutCity);
        if (!alreadyExists) {
          nextAdditional.push(nextNameWithoutCity);
        }
      }

      newData.stages[stageIndex] = { ...stage, additional_teams: nextAdditional };
    }
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

    const removedTeam = newData.stages[stageIndex].games[gameIndex].teams[teamIndex] || {};
    const removedName = String(removedTeam.team_name || '').trim();
    const removedIsAdditional = !!removedTeam.is_additional;

    newData.stages[stageIndex].games[gameIndex].teams = 
      newData.stages[stageIndex].games[gameIndex].teams.filter((_, i) => i !== teamIndex);

    if (removedIsAdditional && removedName) {
      // Клонируем stage, чтобы можно было безопасно обновить additional_teams
      newData.stages[stageIndex] = { ...newData.stages[stageIndex] };
      const stage = newData.stages[stageIndex];
      const currentAdditional = Array.isArray(stage.additional_teams) ? [...stage.additional_teams] : [];

      const removedNameWithoutCity = removeCityFromName(removedName);

      const stillUsed = (stage.games || []).some(g =>
        (g.teams || []).some(t => {
          const teamName = String(t?.team_name || '').trim();
          const teamNameWithoutCity = removeCityFromName(teamName);
          return t?.is_additional && (
            teamName === removedName || 
            teamNameWithoutCity === removedNameWithoutCity
          );
        })
      );

      if (!stillUsed) {
        stage.additional_teams = currentAdditional
          .map(n => String(n || '').trim())
          .filter(Boolean)
          .filter(n => {
            const nWithoutCity = removeCityFromName(n);
            // Удаляем как точное совпадение, так и совпадение без города
            return n !== removedName && nWithoutCity !== removedNameWithoutCity;
          });
      }
    }
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
