import { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { contentApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Plus, Search, MoreHorizontal, Edit, Trash2, ChevronLeft, ChevronRight, Loader2, ChevronDown, ChevronRight as ChevronRightIcon, FolderTree } from 'lucide-react';

const statusLabels = {
  draft: { label: 'Черновик', variant: 'secondary' },
  published: { label: 'Опубликовано', variant: 'default' },
  archived: { label: 'В архиве', variant: 'outline' }
};

// Рекурсивный компонент для отображения строки шоу с вложенностью
function ShowRow({ show, level = 0, expandedIds, toggleExpand, onDelete }) {
  const hasChildren = show.children && show.children.length > 0;
  const isExpanded = expandedIds.has(show._id);
  const indent = level * 24;

  return (
    <>
      <TableRow className={level > 0 ? 'bg-muted/30' : ''}>
        <TableCell>
          <div className="flex items-center" style={{ paddingLeft: `${indent}px` }}>
            {hasChildren ? (
              <button 
                onClick={() => toggleExpand(show._id)}
                className="mr-2 p-1 hover:bg-muted rounded"
              >
                {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRightIcon className="h-4 w-4" />}
              </button>
            ) : (
              <span className="w-7" />
            )}
            <div>
              <Link to={`/admin/shows/${show._id}`} className="font-medium hover:underline">
                {show.name || show.title}
              </Link>
              <div className="text-sm text-muted-foreground">
                /{show.full_path || show.slug}
                {level > 0 && <Badge variant="outline" className="ml-2 text-xs">Уровень {level}</Badge>}
              </div>
            </div>
          </div>
        </TableCell>
        <TableCell>
          {hasChildren && (
            <Badge variant="secondary" className="text-xs">
              <FolderTree className="h-3 w-3 mr-1" />
              {show.children.length}
            </Badge>
          )}
        </TableCell>
        <TableCell><Badge variant={statusLabels[show.status]?.variant}>{statusLabels[show.status]?.label}</Badge></TableCell>
        <TableCell className="text-right">{show.views || 0}</TableCell>
        <TableCell>
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button variant="ghost" size="icon"><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild><Link to={`/admin/shows/${show._id}`}><Edit className="mr-2 h-4 w-4" /> Редактировать</Link></DropdownMenuItem>
              <DropdownMenuItem className="text-destructive" onClick={() => onDelete(show._id)}><Trash2 className="mr-2 h-4 w-4" /> Удалить</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </TableCell>
      </TableRow>
      {hasChildren && isExpanded && show.children.map(child => (
        <ShowRow 
          key={child._id} 
          show={child} 
          level={level + 1} 
          expandedIds={expandedIds}
          toggleExpand={toggleExpand}
          onDelete={onDelete}
        />
      ))}
    </>
  );
}

export default function ShowsListPage() {
  const [shows, setShows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState(null);
  const [viewMode, setViewMode] = useState('hierarchy'); // 'hierarchy' | 'flat'
  const [expandedIds, setExpandedIds] = useState(new Set());
  const [searchParams, setSearchParams] = useSearchParams();

  const page = parseInt(searchParams.get('page') || '1');
  const search = searchParams.get('search') || '';
  const status = searchParams.get('status') || '';
  const limit = 20;

  const toggleExpand = (id) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const expandAll = () => {
    const allIds = new Set();
    const collectIds = (items) => {
      items.forEach(item => {
        if (item.children && item.children.length > 0) {
          allIds.add(item._id);
          collectIds(item.children);
        }
      });
    };
    collectIds(shows);
    setExpandedIds(allIds);
  };

  const collapseAll = () => {
    setExpandedIds(new Set());
  };

  const fetchShows = useCallback(async () => {
    setLoading(true);
    try {
      if (viewMode === 'hierarchy' && !search) {
        // Иерархический режим
        const response = await contentApi.listShowsHierarchy();
        setShows(response.data.items);
        setTotal(response.data.total);
      } else {
        // Плоский режим (с поиском или фильтрацией)
        const params = { 
          skip: (page - 1) * limit, 
          limit, 
          include_children: true,
          ...(search && { search }), 
          ...(status && { status }) 
        };
        const response = await contentApi.listShows(params);
        setShows(response.data.items);
        setTotal(response.data.total);
      }
    } catch (error) {
      console.error('Error fetching shows:', error);
    } finally {
      setLoading(false);
    }
  }, [page, search, status, viewMode]);

  useEffect(() => { fetchShows(); }, [fetchShows]);

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await contentApi.deleteShow(deleteId);
      fetchShows();
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setDeleteId(null);
    }
  };

  const totalPages = Math.ceil(total / limit);
  const isHierarchyMode = viewMode === 'hierarchy' && !search;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Шоу</h1>
          <p className="text-muted-foreground">Управление шоу и проектами ({total} всего)</p>
        </div>
        <Button asChild><Link to="/admin/shows/new"><Plus className="mr-2 h-4 w-4" /> Добавить</Link></Button>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input placeholder="Поиск..." className="pl-9" value={search} onChange={(e) => {
                const params = new URLSearchParams(searchParams);
                e.target.value ? params.set('search', e.target.value) : params.delete('search');
                params.set('page', '1');
                setSearchParams(params);
              }} />
            </div>
            <Select value={status || 'all'} onValueChange={(v) => {
              const params = new URLSearchParams(searchParams);
              v && v !== 'all' ? params.set('status', v) : params.delete('status');
              params.set('page', '1');
              setSearchParams(params);
            }}>
              <SelectTrigger className="w-[180px]"><SelectValue placeholder="Статус" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все статусы</SelectItem>
                <SelectItem value="published">Опубликовано</SelectItem>
                <SelectItem value="draft">Черновики</SelectItem>
              </SelectContent>
            </Select>
            {!search && (
              <Select value={viewMode} onValueChange={setViewMode}>
                <SelectTrigger className="w-[180px]"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="hierarchy">Иерархия</SelectItem>
                  <SelectItem value="flat">Плоский список</SelectItem>
                </SelectContent>
              </Select>
            )}
          </div>
          {isHierarchyMode && shows.some(s => s.children?.length > 0) && (
            <div className="flex gap-2 mt-4">
              <Button variant="outline" size="sm" onClick={expandAll}>Развернуть все</Button>
              <Button variant="outline" size="sm" onClick={collapseAll}>Свернуть все</Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
          ) : shows.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">Ничего не найдено</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Название</TableHead>
                  <TableHead>Дочерние</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead className="text-right">Просмотры</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isHierarchyMode ? (
                  shows.map((show) => (
                    <ShowRow 
                      key={show._id} 
                      show={show} 
                      level={0}
                      expandedIds={expandedIds}
                      toggleExpand={toggleExpand}
                      onDelete={setDeleteId}
                    />
                  ))
                ) : (
                  shows.map((show) => (
                    <TableRow key={show._id} className={show.level > 0 ? 'bg-muted/30' : ''}>
                      <TableCell>
                        <Link to={`/admin/shows/${show._id}`} className="font-medium hover:underline">{show.name || show.title}</Link>
                        <div className="text-sm text-muted-foreground">
                          /{show.full_path || show.slug}
                          {show.level > 0 && <Badge variant="outline" className="ml-2 text-xs">Уровень {show.level}</Badge>}
                        </div>
                      </TableCell>
                      <TableCell>-</TableCell>
                      <TableCell><Badge variant={statusLabels[show.status]?.variant}>{statusLabels[show.status]?.label}</Badge></TableCell>
                      <TableCell className="text-right">{show.views || 0}</TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild><Button variant="ghost" size="icon"><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem asChild><Link to={`/admin/shows/${show._id}`}><Edit className="mr-2 h-4 w-4" /> Редактировать</Link></DropdownMenuItem>
                            <DropdownMenuItem className="text-destructive" onClick={() => setDeleteId(show._id)}><Trash2 className="mr-2 h-4 w-4" /> Удалить</DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {!isHierarchyMode && totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">Показано {(page - 1) * limit + 1}-{Math.min(page * limit, total)} из {total}</div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" disabled={page <= 1} onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', String(page - 1)); setSearchParams(p); }}><ChevronLeft className="h-4 w-4" /></Button>
            <span className="text-sm">{page} / {totalPages}</span>
            <Button variant="outline" size="icon" disabled={page >= totalPages} onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', String(page + 1)); setSearchParams(p); }}><ChevronRight className="h-4 w-4" /></Button>
          </div>
        </div>
      )}

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить шоу?</AlertDialogTitle>
            <AlertDialogDescription>Это действие нельзя отменить.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">Удалить</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
