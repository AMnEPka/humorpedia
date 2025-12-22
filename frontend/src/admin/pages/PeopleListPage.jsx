import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { contentApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import { cn } from '@/lib/utils';

const LETTERS = 'АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯ'.split('');

const statusLabels = {
  draft: { label: 'Черновик', variant: 'secondary' },
  published: { label: 'Опубликовано', variant: 'default' },
  archived: { label: 'В архиве', variant: 'outline' }
};

export default function PeopleListPage() {
  const [people, setPeople] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const page = parseInt(searchParams.get('page') || '1');
  const search = searchParams.get('search') || '';
  const status = searchParams.get('status') || '';
  const letter = searchParams.get('letter') || '';
  const limit = 20;

  const fetchPeople = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        skip: (page - 1) * limit,
        limit,
        ...(search && { search }),
        ...(status && { status }),
        ...(letter && { letter })
      };
      const response = await contentApi.listPeople(params);
      setPeople(response.data.items);
      setTotal(response.data.total);
    } catch (error) {
      console.error('Error fetching people:', error);
    } finally {
      setLoading(false);
    }
  }, [page, search, status, letter]);

  useEffect(() => {
    fetchPeople();
  }, [fetchPeople]);

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

  const handleStatusChange = (value) => {
    const params = new URLSearchParams(searchParams);
    if (value && value !== 'all') {
      params.set('status', value);
    } else {
      params.delete('status');
    }
    params.set('page', '1');
    setSearchParams(params);
  };

  const handleLetterClick = (l) => {
    const params = new URLSearchParams(searchParams);
    if (l === letter) {
      params.delete('letter');
    } else {
      params.set('letter', l);
    }
    params.set('page', '1');
    setSearchParams(params);
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await contentApi.deletePerson(deleteId);
      fetchPeople();
    } catch (error) {
      console.error('Error deleting person:', error);
    } finally {
      setDeleteId(null);
    }
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Люди</h1>
          <p className="text-muted-foreground">Управление профилями участников КВН и других шоу</p>
        </div>
        <Button asChild data-testid="add-person-btn">
          <Link to="/admin/people/new">
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
                  placeholder="Поиск по имени..."
                  className="pl-9"
                  value={search}
                  onChange={(e) => handleSearch(e.target.value)}
                  data-testid="search-input"
                />
              </div>
            </div>
            <Select value={status || 'all'} onValueChange={handleStatusChange}>
              <SelectTrigger className="w-[180px]" data-testid="status-filter">
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

          {/* Alphabetical filter */}
          <div className="flex flex-wrap gap-1 mt-4">
            {LETTERS.map((l) => (
              <button
                key={l}
                onClick={() => handleLetterClick(l)}
                className={cn(
                  "w-8 h-8 text-sm rounded-md transition-colors",
                  letter === l
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-muted"
                )}
              >
                {l}
              </button>
            ))}
            {letter && (
              <button
                onClick={() => handleLetterClick(letter)}
                className="px-3 h-8 text-sm text-muted-foreground hover:text-foreground"
              >
                Сбросить
              </button>
            )}
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
          ) : people.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              Ничего не найдено
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Имя</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead>Теги</TableHead>
                  <TableHead className="text-right">Просмотры</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {people.map((person) => (
                  <TableRow key={person._id} data-testid={`person-row-${person._id}`}>
                    <TableCell>
                      <Link 
                        to={`/admin/people/${person._id}`}
                        className="font-medium hover:underline"
                      >
                        {person.title || person.full_name}
                      </Link>
                      <div className="text-sm text-muted-foreground">
                        /{person.slug}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusLabels[person.status]?.variant || 'secondary'}>
                        {statusLabels[person.status]?.label || person.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {person.tags?.slice(0, 3).map((tag) => (
                          <Badge key={tag} variant="outline" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                        {person.tags?.length > 3 && (
                          <Badge variant="outline" className="text-xs">
                            +{person.tags.length - 3}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">{person.views || 0}</TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem asChild>
                            <Link to={`/admin/people/${person._id}`}>
                              <Edit className="mr-2 h-4 w-4" /> Редактировать
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => window.open(`/people/${person.slug}`, '_blank')}
                          >
                            <Eye className="mr-2 h-4 w-4" /> Просмотр
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() => setDeleteId(person._id)}
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
            <span className="text-sm">
              {page} / {totalPages}
            </span>
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
            <AlertDialogTitle>Удалить запись?</AlertDialogTitle>
            <AlertDialogDescription>
              Это действие нельзя отменить. Запись будет удалена навсегда.
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
