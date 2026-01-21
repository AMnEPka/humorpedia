import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { contentApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import {
  Table, TableBody, TableCell, TableHead, 
  TableHeader, TableRow
} from '@/components/ui/table';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle
} from '@/components/ui/dialog';
import {
  Select, SelectContent, SelectItem, 
  SelectTrigger, SelectValue
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle
} from '@/components/ui/alert-dialog';
import { 
  Plus, Search, MoreHorizontal, Edit, Trash2, Eye, 
  ChevronLeft, ChevronRight, Loader2, Copy
} from 'lucide-react';

const statusLabels = {
  draft: { label: 'Черновик', variant: 'secondary' },
  published: { label: 'Опубликовано', variant: 'default' },
  archived: { label: 'В архиве', variant: 'outline' }
};

const teamTypeLabels = {
  kvn: 'КВН',
  liga_smeha: 'Лига Смеха',
  improv: 'Импровизация',
  comedy_club: 'Comedy Club',
  other: 'Другое'
};

const stripOuterQuotes = (s) => {
  const str = (s || '').trim();
  if (!str) return '';
  const pairs = [
    ['«', '»'],
    ['"', '"'],
    ["'", "'"],
    ['„', '“'],
    ['“', '”'],
  ];
  for (const [l, r] of pairs) {
    if (str.startsWith(l) && str.endsWith(r) && str.length >= 2) {
      return str.slice(1, -1).trim();
    }
  }
  return str;
};

const parseTeamLine = (rawLine) => {
  const raw = (rawLine || '').trim();
  if (!raw) return null;

  // City is optional; if present, expected in the last (...) group
  const m = raw.match(/^(.*?)(?:\s*\(([^()]*)\)\s*)$/);
  let namePart = raw;
  let city = null;
  if (m) {
    namePart = (m[1] || '').trim();
    city = (m[2] || '').trim() || null;
  }

  const name = stripOuterQuotes(namePart);
  return { raw_line: raw, name: name || '', city };
};

export default function TeamsListPage() {
  const [teams, setTeams] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState(null);
  const [duplicatingId, setDuplicatingId] = useState(null); // Защита от повторных кликов
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const page = parseInt(searchParams.get('page') || '1');
  const search = searchParams.get('search') || '';
  const status = searchParams.get('status') || '';
  const teamType = searchParams.get('team_type') || '';
  const limit = 20;

  // Bulk import state
  const [bulkText, setBulkText] = useState('');
  const [bulkRows, setBulkRows] = useState([]); // [{ raw_line, name, city, status, create, confirmed_skip, team_id, team_slug, team_display_name, manual_link }]
  const [bulkChecking, setBulkChecking] = useState(false);
  const [bulkApplying, setBulkApplying] = useState(false);
  const [bulkError, setBulkError] = useState('');
  const [bulkSuccess, setBulkSuccess] = useState('');

  // Manual matching dialog
  const [matchDialogOpen, setMatchDialogOpen] = useState(false);
  const [matchRowIndex, setMatchRowIndex] = useState(null);
  const [matchSearch, setMatchSearch] = useState('');
  const [matchLoading, setMatchLoading] = useState(false);
  const [matchResults, setMatchResults] = useState([]);

  const fetchTeams = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        skip: (page - 1) * limit,
        limit,
        ...(search && { search }),
        ...(status && { status }),
        ...(teamType && { team_type: teamType })
      };
      const response = await contentApi.listTeams(params);
      setTeams(response.data.items);
      setTotal(response.data.total);
    } catch (error) {
      console.error('Error fetching teams:', error);
    } finally {
      setLoading(false);
    }
  }, [page, search, status, teamType]);

  useEffect(() => {
    fetchTeams();
  }, [fetchTeams]);

  const canApplyBulk = bulkRows.every((r) => {
    if (r.status === 'found') return !!r.confirmed_skip;
    return true;
  });

  const handleBulkCheck = async () => {
    setBulkError('');
    setBulkSuccess('');
    setBulkChecking(true);
    try {
      const parsed = bulkText
        .split(/\r?\n/)
        .map(parseTeamLine)
        .filter(Boolean);

      const items = parsed.map((p) => ({ raw_line: p.raw_line, name: p.name, city: p.city }));
      const res = await contentApi.teamsBulkCheck({ items });
      const checked = (res.data.items || []).map((r) => {
        const base = parsed[r.index] || { raw_line: '', name: '', city: null };
        const statusVal = r.status;
        const isNotFound = statusVal === 'not_found';
        return {
          raw_line: base.raw_line,
          name: r.name || base.name || '',
          city: r.city ?? base.city ?? null,
          status: statusVal,
          team_id: r.team_id || null,
          team_slug: r.team_slug || null,
          team_display_name: r.team_display_name || null,
          // user controls
          create: isNotFound, // only default-create not_found rows
          confirmed_skip: false,
          manual_link: false,
        };
      });

      setBulkRows(checked);
      if (checked.length === 0) {
        setBulkError('Список пустой или не удалось распарсить строки');
      }
    } catch (e) {
      console.error(e);
      setBulkError('Ошибка проверки списка');
    } finally {
      setBulkChecking(false);
    }
  };

  const buildBulkCreatePayload = () => {
    return {
      rows: bulkRows.map((r) => {
        if (r.status === 'found') {
          return {
            action: 'link_existing',
            existing_team_id: r.team_id,
            confirmed_skip: !!r.confirmed_skip,
          };
        }
        if (r.status === 'not_found') {
          if (!r.create) {
            return { action: 'skip' };
          }
          return { action: 'create', name: r.name, city: r.city };
        }
        // invalid or unknown -> skip
        return { action: 'skip' };
      }),
    };
  };

  const handleBulkApply = async () => {
    setBulkError('');
    setBulkSuccess('');
    setBulkApplying(true);
    try {
      const payload = buildBulkCreatePayload();
      const res = await contentApi.teamsBulkCreate(payload);
      const createdCount = res.data.created?.length || 0;
      const skippedCount = res.data.skipped?.length || 0;
      setBulkSuccess(`Готово: создано ${createdCount}, пропущено ${skippedCount}`);
      // refresh list tab data
      fetchTeams();
    } catch (e) {
      console.error(e);
      const detail = e.response?.data?.detail;
      setBulkError(typeof detail === 'string' ? detail : 'Ошибка при создании команд');
    } finally {
      setBulkApplying(false);
    }
  };

  const openMatchDialog = (rowIdx) => {
    setMatchRowIndex(rowIdx);
    setMatchSearch('');
    setMatchResults([]);
    setMatchDialogOpen(true);
  };

  const searchMatchTeams = async (q) => {
    const query = (q || '').trim();
    setMatchSearch(q);
    if (query.length < 2) {
      setMatchResults([]);
      return;
    }
    setMatchLoading(true);
    try {
      const res = await contentApi.listTeams({ search: query, limit: 10, skip: 0, team_type: 'kvn' });
      setMatchResults(res.data.items || []);
    } catch (e) {
      console.error(e);
      setMatchResults([]);
    } finally {
      setMatchLoading(false);
    }
  };

  const chooseExistingTeam = (team) => {
    if (matchRowIndex === null || matchRowIndex === undefined) return;
    setBulkRows((prev) => {
      const next = [...prev];
      const row = { ...next[matchRowIndex] };
      row.status = 'found';
      row.team_id = team._id;
      row.team_slug = team.slug;
      row.team_display_name = team.name || team.title || team.slug;
      row.manual_link = true;
      row.create = false;
      row.confirmed_skip = false; // must be confirmed explicitly
      next[matchRowIndex] = row;
      return next;
    });
    setMatchDialogOpen(false);
  };

  const handleSearch = (value) => {
    const params = new URLSearchParams(searchParams);
    if (value) {
      params.set('search', value);
    } else {
      params.delete('search');
    }
    params.set('page', '1');
    setSearchParams(params);
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await contentApi.deleteTeam(deleteId);
      fetchTeams();
    } catch (error) {
      console.error('Error deleting team:', error);
    } finally {
      setDeleteId(null);
    }
  };

  const handleDuplicate = async (id) => {
    // Защита от повторных кликов
    if (duplicatingId === id) {
      return;
    }
    
    setDuplicatingId(id);
    try {
      await contentApi.duplicateContent('teams', id);
      fetchTeams();
    } catch (error) {
      console.error('Error duplicating team:', error);
      alert('Ошибка при копировании команды');
    } finally {
      setDuplicatingId(null);
    }
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Команды</h1>
          <p className="text-muted-foreground">Управление командами КВН, Лиги Смеха и других шоу</p>
        </div>
        <Button asChild data-testid="add-team-btn">
          <Link to="/admin/teams/new">
            <Plus className="mr-2 h-4 w-4" /> Добавить
          </Link>
        </Button>
      </div>

      <Tabs defaultValue="list" className="space-y-6">
        <TabsList>
          <TabsTrigger value="list">Список</TabsTrigger>
          <TabsTrigger value="bulk">Импорт списком</TabsTrigger>
        </TabsList>

        <TabsContent value="list" className="space-y-6">
          {/* Filters */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex flex-col md:flex-row gap-4">
                <div className="flex-1">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Поиск по названию..."
                      className="pl-9"
                      value={search}
                      onChange={(e) => handleSearch(e.target.value)}
                      data-testid="search-input"
                    />
                  </div>
                </div>
                <Select 
                  value={teamType || 'all'} 
                  onValueChange={(v) => {
                    const params = new URLSearchParams(searchParams);
                    if (v && v !== 'all') {
                      params.set('team_type', v);
                    } else {
                      params.delete('team_type');
                    }
                    params.set('page', '1');
                    setSearchParams(params);
                  }}
                >
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Тип команды" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Все типы</SelectItem>
                    <SelectItem value="kvn">КВН</SelectItem>
                    <SelectItem value="liga_smeha">Лига Смеха</SelectItem>
                    <SelectItem value="improv">Импровизация</SelectItem>
                    <SelectItem value="other">Другое</SelectItem>
                  </SelectContent>
                </Select>
                <Select 
                  value={status || 'all'} 
                  onValueChange={(v) => {
                    const params = new URLSearchParams(searchParams);
                    if (v && v !== 'all') {
                      params.set('status', v);
                    } else {
                      params.delete('status');
                    }
                    params.set('page', '1');
                    setSearchParams(params);
                  }}
                >
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Статус" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Все статусы</SelectItem>
                    <SelectItem value="published">Опубликовано</SelectItem>
                    <SelectItem value="draft">Черновики</SelectItem>
                    <SelectItem value="archived">Архив</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Table */}
          <Card>
            <CardContent className="p-0">
              {loading ? (
                <div className="flex items-center justify-center h-64">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
              ) : teams.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  Ничего не найдено
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[60px]">Лого</TableHead>
                      <TableHead>Название</TableHead>
                      <TableHead>Тип</TableHead>
                      <TableHead>Статус</TableHead>
                      <TableHead>Город</TableHead>
                      <TableHead className="w-[100px]">Просмотр</TableHead>
                      <TableHead className="text-right">Просмотры</TableHead>
                      <TableHead className="w-[50px]"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {teams.map((team) => {
                      // Получаем URL логотипа из различных полей
                      const getLogoUrl = () => {
                        const logo = team.logo || team.image || team.cover_image?.url || team.cover_image || team.poster;
                        if (!logo) return null;
                        if (typeof logo === 'string') {
                          return logo.startsWith('/') || logo.startsWith('http') ? logo : `/${logo}`;
                        }
                        if (typeof logo === 'object' && logo.url) {
                          const url = logo.url;
                          return url.startsWith('/') || url.startsWith('http') ? url : `/${url}`;
                        }
                        return null;
                      };
                      const logoUrl = getLogoUrl();
                      
                      return (
                      <TableRow key={team._id} data-testid={`team-row-${team._id}`}>
                        <TableCell>
                          <div className="w-10 h-10 rounded overflow-hidden bg-muted flex items-center justify-center">
                            {logoUrl ? (
                              <img 
                                src={logoUrl} 
                                alt={team.name || team.title}
                                className="w-full h-full object-cover"
                                onError={(e) => {
                                  e.target.style.display = 'none';
                                  e.target.nextElementSibling.style.display = 'flex';
                                }}
                              />
                            ) : null}
                            <span className={`text-lg font-bold text-muted-foreground ${logoUrl ? 'hidden' : 'flex'}`}>
                              {(team.name || team.title)?.charAt(0)?.toUpperCase()}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Link 
                            to={`/admin/teams/${team._id}`}
                            className="font-medium hover:underline"
                          >
                            {team.name || team.title}
                          </Link>
                          <div className="text-sm text-muted-foreground">
                            /{team.slug}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {teamTypeLabels[team.team_type] || team.team_type}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={statusLabels[team.status]?.variant || 'secondary'}>
                            {statusLabels[team.status]?.label || team.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{team.facts?.city || '-'}</TableCell>
                        <TableCell>
                          {team.slug && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => window.open(`/kvn/teams/${team.slug}`, '_blank')}
                              className="h-8"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          )}
                        </TableCell>
                        <TableCell className="text-right">{team.views || 0}</TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem asChild>
                                <Link to={`/admin/teams/${team._id}`}>
                                  <Edit className="mr-2 h-4 w-4" /> Редактировать
                                </Link>
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => window.open(`/kvn/teams/${team.slug}`, '_blank')}
                              >
                                <Eye className="mr-2 h-4 w-4" /> Просмотр
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => handleDuplicate(team._id)}
                                disabled={duplicatingId === team._id}
                              >
                                <Copy className="mr-2 h-4 w-4" /> 
                                {duplicatingId === team._id ? 'Копирование...' : 'Копировать'}
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                className="text-destructive"
                                onClick={() => setDeleteId(team._id)}
                              >
                                <Trash2 className="mr-2 h-4 w-4" /> Удалить
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <div className="text-sm text-muted-foreground">
                Показано {(page - 1) * limit + 1}-{Math.min(page * limit, total)} из {total}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="icon"
                  disabled={page <= 1}
                  onClick={() => {
                    const params = new URLSearchParams(searchParams);
                    params.set('page', String(page - 1));
                    setSearchParams(params);
                  }}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm">{page} / {totalPages}</span>
                <Button
                  variant="outline"
                  size="icon"
                  disabled={page >= totalPages}
                  onClick={() => {
                    const params = new URLSearchParams(searchParams);
                    params.set('page', String(page + 1));
                    setSearchParams(params);
                  }}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </TabsContent>

        <TabsContent value="bulk" className="space-y-6">
          <Card>
            <CardContent className="pt-6 space-y-4">
              <div className="space-y-2">
                <div className="text-sm text-muted-foreground">
                  Вставьте список строк вида <span className="font-mono">«Название» (Город)</span>. Город можно опустить.
                </div>
                <Textarea
                  value={bulkText}
                  onChange={(e) => setBulkText(e.target.value)}
                  placeholder="«Сборная Армении»&#10;«Столица» (Москва)"
                  className="min-h-[180px]"
                />
              </div>
              <div className="flex items-center gap-2">
                <Button onClick={handleBulkCheck} disabled={bulkChecking}>
                  {bulkChecking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Проверить
                </Button>
                <Button
                  variant="default"
                  onClick={handleBulkApply}
                  disabled={bulkRows.length === 0 || bulkApplying || !canApplyBulk}
                >
                  {bulkApplying ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Создать/применить
                </Button>
                {!canApplyBulk && (
                  <div className="text-sm text-muted-foreground">
                    Подтвердите пропуск для всех найденных команд.
                  </div>
                )}
              </div>
              {bulkError && <div className="text-sm text-destructive">{bulkError}</div>}
              {bulkSuccess && <div className="text-sm">{bulkSuccess}</div>}
            </CardContent>
          </Card>

          {bulkRows.length > 0 && (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[70px]">Создавать</TableHead>
                      <TableHead>Строка</TableHead>
                      <TableHead>Имя</TableHead>
                      <TableHead>Город</TableHead>
                      <TableHead className="w-[140px]">Статус</TableHead>
                      <TableHead className="w-[260px]">Действия</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {bulkRows.map((r, idx) => (
                      <TableRow key={idx}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Checkbox
                              checked={!!r.create}
                              disabled={r.status !== 'not_found'}
                              onCheckedChange={(v) => {
                                setBulkRows((prev) => {
                                  const next = [...prev];
                                  next[idx] = { ...next[idx], create: !!v };
                                  return next;
                                });
                              }}
                            />
                          </div>
                        </TableCell>
                        <TableCell className="max-w-[380px] truncate" title={r.raw_line}>
                          {r.raw_line}
                        </TableCell>
                        <TableCell>{r.name || <span className="text-muted-foreground">—</span>}</TableCell>
                        <TableCell>{r.city || <span className="text-muted-foreground">—</span>}</TableCell>
                        <TableCell>
                          {r.status === 'found' ? (
                            <Badge variant="default">Найдено</Badge>
                          ) : r.status === 'not_found' ? (
                            <Badge variant="secondary">Не найдено</Badge>
                          ) : (
                            <Badge variant="outline">Ошибка</Badge>
                          )}
                          {r.status === 'found' && r.team_display_name ? (
                            <div className="text-xs text-muted-foreground mt-1">
                              {r.team_display_name} {r.team_slug ? <span className="font-mono">/{r.team_slug}</span> : null}
                            </div>
                          ) : null}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-2">
                            {r.status === 'found' && (
                              <label className="flex items-center gap-2 text-sm">
                                <Checkbox
                                  checked={!!r.confirmed_skip}
                                  onCheckedChange={(v) => {
                                    setBulkRows((prev) => {
                                      const next = [...prev];
                                      next[idx] = { ...next[idx], confirmed_skip: !!v };
                                      return next;
                                    });
                                  }}
                                />
                                Подтверждаю пропуск
                              </label>
                            )}
                            {r.status === 'not_found' && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => openMatchDialog(idx)}
                              >
                                Сопоставить с существующей
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          <Dialog open={matchDialogOpen} onOpenChange={setMatchDialogOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Сопоставить с существующей командой</DialogTitle>
                <DialogDescription>
                  Начните вводить название — выберите команду из БД. После выбора строка будет считаться найденной и потребует подтверждения пропуска.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3">
                <Input
                  value={matchSearch}
                  onChange={(e) => searchMatchTeams(e.target.value)}
                  placeholder="Поиск команды..."
                />
                <div className="border rounded-md max-h-[260px] overflow-auto">
                  {matchLoading ? (
                    <div className="p-4 flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" /> Поиск...
                    </div>
                  ) : matchResults.length === 0 ? (
                    <div className="p-4 text-sm text-muted-foreground">Нет результатов</div>
                  ) : (
                    <div className="divide-y">
                      {matchResults.map((t) => (
                        <button
                          type="button"
                          key={t._id}
                          className="w-full text-left p-3 hover:bg-muted"
                          onClick={() => chooseExistingTeam(t)}
                        >
                          <div className="font-medium">{t.name || t.title}</div>
                          <div className="text-xs text-muted-foreground">
                            <span className="font-mono">/{t.slug}</span>{t.facts?.city ? ` · ${t.facts.city}` : ''}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setMatchDialogOpen(false)}>
                  Закрыть
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>
      </Tabs>

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить команду?</AlertDialogTitle>
            <AlertDialogDescription>
              Это действие нельзя отменить.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
