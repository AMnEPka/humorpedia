import { useState, useEffect, useRef } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Trash2, GripVertical } from 'lucide-react';
import { formatDecimalTrim, roundTo } from '@/utils/number';
import GameTeamSelector from '../GameTeamSelector';
export function ScoreInput({ value, onChange, onBlur, className, "aria-label": ariaLabel }) {
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
    <Input aria-label={ariaLabel} type="text"
      inputMode="decimal"
      className={className}
      value={localValue}
      onChange={handleChange}
      onFocus={handleFocus}
      onBlur={handleBlur}
    />
  );
}

export function SortableTeam({
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
                aria-label={"Переместить команду " + (team.team_name || "Команда " + (teamIndex + 1))}
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
              aria-label={"Удалить команду " + (team.team_name || "Команда " + (teamIndex + 1))}
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
              <Input aria-label={"Итого: " + (team.team_name || "Команда " + (teamIndex + 1))} type="text"
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
                      aria-label={"Баллы: " + (team.team_name || "Команда " + (teamIndex + 1)) + " — " + contest}
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
