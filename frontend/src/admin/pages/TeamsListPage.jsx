import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { contentApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import {
  Table, TableBody, TableCell, TableHead, 
  TableHeader, TableRow
} from '@/components/ui/table';
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
  ChevronLeft, ChevronRight, Loader2 
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

export default function TeamsListPage() {
  const [teams, setTeams] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const page = parseInt(searchParams.get('page') || '1');
  const search = searchParams.get('search') || '';
  const status = searchParams.get('status') || '';
  const teamType = searchParams.get('team_type') || '';
  const limit = 20;

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
                  <TableHead>Название</TableHead>
                  <TableHead>Тип</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead>Город</TableHead>
                  <TableHead className="text-right">Просмотры</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {teams.map((team) => (
                  <TableRow key={team._id} data-testid={`team-row-${team._id}`}>
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
                            onClick={() => window.open(`/teams/${team.slug}`, '_blank')}
                          >
                            <Eye className="mr-2 h-4 w-4" /> Просмотр
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
                ))}
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
