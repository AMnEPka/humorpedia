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
import { Plus, Search, MoreHorizontal, Edit, Trash2, ChevronLeft, ChevronRight, Loader2, Star } from 'lucide-react';

const statusLabels = { draft: { label: 'Черновик', variant: 'secondary' }, published: { label: 'Опубликовано', variant: 'default' }, archived: { label: 'В архиве', variant: 'outline' } };

export default function ArticlesListPage() {
  const [articles, setArticles] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const page = parseInt(searchParams.get('page') || '1');
  const search = searchParams.get('search') || '';
  const status = searchParams.get('status') || '';
  const limit = 20;

  const fetchArticles = useCallback(async () => {
    setLoading(true);
    try {
      const params = { skip: (page - 1) * limit, limit, ...(search && { search }), ...(status && { status }) };
      const response = await contentApi.listArticles(params);
      setArticles(response.data.items);
      setTotal(response.data.total);
    } catch (error) { console.error(error); } finally { setLoading(false); }
  }, [page, search, status]);

  useEffect(() => { fetchArticles(); }, [fetchArticles]);

  const handleDelete = async () => {
    if (!deleteId) return;
    try { await contentApi.deleteArticle(deleteId); fetchArticles(); } catch (e) { console.error(e); } finally { setDeleteId(null); }
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-3xl font-bold">Статьи</h1><p className="text-muted-foreground">Аналитические материалы и обзоры</p></div>
        <Button asChild><Link to="/admin/articles/new"><Plus className="mr-2 h-4 w-4" /> Добавить</Link></Button>
      </div>

      <Card><CardContent className="pt-6"><div className="flex flex-col md:flex-row gap-4">
        <div className="flex-1 relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" /><Input placeholder="Поиск..." className="pl-9" value={search} onChange={(e) => { const p = new URLSearchParams(searchParams); e.target.value ? p.set('search', e.target.value) : p.delete('search'); p.set('page', '1'); setSearchParams(p); }} /></div>
        <Select value={status || 'all'} onValueChange={(v) => { const p = new URLSearchParams(searchParams); v !== 'all' ? p.set('status', v) : p.delete('status'); p.set('page', '1'); setSearchParams(p); }}><SelectTrigger className="w-[180px]"><SelectValue placeholder="Статус" /></SelectTrigger><SelectContent><SelectItem value="all">Все</SelectItem><SelectItem value="published">Опубликовано</SelectItem><SelectItem value="draft">Черновики</SelectItem></SelectContent></Select>
      </div></CardContent></Card>

      <Card><CardContent className="p-0">
        {loading ? <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div> : articles.length === 0 ? <div className="text-center py-12 text-muted-foreground">Ничего не найдено</div> : (
          <Table><TableHeader><TableRow><TableHead>Заголовок</TableHead><TableHead>Автор</TableHead><TableHead>Статус</TableHead><TableHead>Рейтинг</TableHead><TableHead className="text-right">Просмотры</TableHead><TableHead className="w-[50px]"></TableHead></TableRow></TableHeader>
            <TableBody>{articles.map((a) => (
              <TableRow key={a._id}>
                <TableCell><Link to={`/admin/articles/${a._id}`} className="font-medium hover:underline">{a.title}</Link>{a.featured && <Badge variant="outline" className="ml-2"><Star className="h-3 w-3 mr-1" />Избранное</Badge>}<div className="text-sm text-muted-foreground">/{a.slug}</div></TableCell>
                <TableCell>{a.author_name || '-'}</TableCell>
                <TableCell><Badge variant={statusLabels[a.status]?.variant}>{statusLabels[a.status]?.label}</Badge></TableCell>
                <TableCell>{a.rating ? `${a.rating}/10` : '-'}</TableCell>
                <TableCell className="text-right">{a.views || 0}</TableCell>
                <TableCell><DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="icon"><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem asChild><Link to={`/admin/articles/${a._id}`}><Edit className="mr-2 h-4 w-4" /> Редактировать</Link></DropdownMenuItem><DropdownMenuItem className="text-destructive" onClick={() => setDeleteId(a._id)}><Trash2 className="mr-2 h-4 w-4" /> Удалить</DropdownMenuItem></DropdownMenuContent></DropdownMenu></TableCell>
              </TableRow>
            ))}</TableBody></Table>
        )}
      </CardContent></Card>

      {totalPages > 1 && <div className="flex items-center justify-between"><div className="text-sm text-muted-foreground">Показано {(page - 1) * limit + 1}-{Math.min(page * limit, total)} из {total}</div><div className="flex items-center gap-2"><Button variant="outline" size="icon" disabled={page <= 1} onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', String(page - 1)); setSearchParams(p); }}><ChevronLeft className="h-4 w-4" /></Button><span className="text-sm">{page} / {totalPages}</span><Button variant="outline" size="icon" disabled={page >= totalPages} onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', String(page + 1)); setSearchParams(p); }}><ChevronRight className="h-4 w-4" /></Button></div></div>}

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Удалить статью?</AlertDialogTitle><AlertDialogDescription>Это действие нельзя отменить.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Отмена</AlertDialogCancel><AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">Удалить</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </div>
  );
}
