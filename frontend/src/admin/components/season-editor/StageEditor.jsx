import { useState } from 'react';
import { DndContext, closestCenter } from '@dnd-kit/core';
import { useSortable } from '@dnd-kit/sortable';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Card, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Trash2, GripVertical, ChevronDown, ChevronUp, ChevronRight, Plus } from 'lucide-react';
import RichTextEditor from '../RichTextEditor';
import { SortableGame } from './GameEditor';
export function SortableStage({
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
                aria-label={"Переместить стадию " + (stage.name || "Стадия " + (stageIndex + 1))}
                className="cursor-grab text-muted-foreground hover:text-foreground touch-none"
                onClick={(e) => e.stopPropagation()}
              >
                <GripVertical className="h-5 w-5" />
              </button>
              <button
                type="button"
                onClick={onToggle}
                aria-label={(isExpanded ? "Свернуть стадию " : "Развернуть стадию ") + (stage.name || "Стадия " + (stageIndex + 1))}
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
                aria-label={"Свернуть стадию " + (stage.name || "Стадия " + (stageIndex + 1))}
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
        <Label>Комментарий к стадии</Label>
        <Textarea
          value={stage.comment || ''}
          onChange={(e) => updateStage({ comment: e.target.value })}
          rows={3}
          placeholder="Краткий текст перед сеткой игр этой стадии"
        />
        <p className="text-xs text-muted-foreground">
          Обычный текст без HTML. Показывается под названием стадии перед играми.
        </p>
      </div>
      <div className="space-y-2">
        <Label>Старые заметки к стадии (HTML)</Label>
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
