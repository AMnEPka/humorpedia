import { useState } from 'react';
import { DndContext, closestCenter } from '@dnd-kit/core';
import { useSortable } from '@dnd-kit/sortable';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from '@/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { GripVertical, ChevronDown, ChevronRight, ChevronUp, MoreHorizontal, Copy, ArrowRight, Trash2, Plus, X, Table, List } from 'lucide-react';
import { roundTo } from '@/utils/number';
import { SortableTeam } from './TeamResultEditor';
import { hasUnmatchedPersonReferences, retainUnambiguousTeamLinks } from './operations';
export function SortableGame({
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
                aria-label={"Переместить игру " + (game.name || "Игра " + (gameIndex + 1))}
                className="cursor-grab text-muted-foreground hover:text-foreground touch-none"
              >
                <GripVertical className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={onToggleExpand}
                aria-label={(isExpanded ? "Свернуть игру " : "Развернуть игру ") + (game.name || "Игра " + (gameIndex + 1))}
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
                aria-label={"Свернуть игру " + (game.name || "Игра " + (gameIndex + 1))}
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

    if (hasUnmatchedPersonReferences(newTeams, game.teams || [])) {
      setListError('Нельзя заменить список: привязка к человеку для одной из команд не сопоставлена однозначно. Уточните названия команд и повторите вставку.');
      return;
    }

    // Обновляем игру с новыми командами
    updateGame({ teams: retainUnambiguousTeamLinks(newTeams, game.teams || []) });

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
    const newTeams = dataRows.map((row) => {
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
        total: roundTo(total, 2),
        scores,
        passed: false,
        is_winner: false,
        is_additional: false,
        city
      };
    }).filter(Boolean);

    // После фильтрации пересчитываем места, чтобы они были последовательными
    const teamsWithPlaces = retainUnambiguousTeamLinks(newTeams, game.teams || []).map((team, index) => ({
      ...team,
      place: index + 1,
    }));

    if (newTeams.length === 0) {
      setTableError('Не удалось распознать ни одной команды в таблице.');
      return;
    }

    if (hasUnmatchedPersonReferences(newTeams, game.teams || [])) {
      setTableError('Нельзя заменить таблицу: привязка к человеку для одной из команд не сопоставлена однозначно. Уточните названия команд и повторите вставку.');
      return;
    }

    // Обновляем игру: конкурсы (если нужно) и команды заполняются автоматически
    const updates = {
      teams: teamsWithPlaces,
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

              // Логика ошибок в превью должна соответствовать applyTableData:
              // - ошибка, если не удалось определить конкурсы (contests.length === 0),
              // - или если в режиме обновления не найден хотя бы один из существующих конкурсов.
              const hasError =
                contests.length === 0 ||
                (existingContests.length > 0 && contestColumnMap.size !== contests.length);

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
