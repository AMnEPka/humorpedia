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
import { Plus, Search, MoreHorizontal, Edit, Trash2, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';

const statusLabels = { draft: { label: 'Черновик', variant: 'secondary' }, published: { label: 'Опубликовано', variant: 'default' }, archived: { label: 'В архиве', variant: 'outline' } };

export default function QuizzesListPage() {
  const [quizzes, setQuizzes] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const page = parseInt(searchParams.get('page') || '1');
  const status = searchParams.get('status') || '';
  const limit = 20;

  const fetchQuizzes = useCallback(async () => {
    setLoading(true);
    try {
      const params = { skip: (page - 1) * limit, limit, ...(status && { status }) };
      const response = await contentApi.listQuizzes(params);
      setQuizzes(response.data.items);
      setTotal(response.data.total);
    } catch (error) { console.error(error); } finally { setLoading(false); }
  }, [page, status]);

  useEffect(() => { fetchQuizzes(); }, [fetchQuizzes]);

  const handleDelete = async () => { if (!deleteId) return; try { await contentApi.deleteQuiz(deleteId); fetchQuizzes(); } catch (e) { console.error(e); } finally { setDeleteId(null); } };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-3xl font-bold">Квизы</h1><p className="text-muted-foreground">Интерактивные викторины</p></div>
        <Button asChild><Link to="/admin/quizzes/new"><Plus className="mr-2 h-4 w-4" /> Добавить</Link></Button>
      </div>

      <Card><CardContent className="pt-6"><div className="flex gap-4">
        <Select value={status || 'all'} onValueChange={(v) => { const p = new URLSearchParams(searchParams); v !== 'all' ? p.set('status', v) : p.delete('status'); p.set('page', '1'); setSearchParams(p); }}><SelectTrigger className="w-[180px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Все</SelectItem><SelectItem value="published">Опубликовано</SelectItem><SelectItem value="draft">Черновики</SelectItem></SelectContent></Select>
      </div></CardContent></Card>

      <Card><CardContent className="p-0">
        {loading ? <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div> : quizzes.length === 0 ? <div className="text-center py-12 text-muted-foreground">Ничего не найдено</div> : (
          <Table><TableHeader><TableRow><TableHead>Название</TableHead><TableHead>Статус</TableHead><TableHead>Прохождения</TableHead><TableHead className="text-right">Просмотры</TableHead><TableHead className="w-[50px]"></TableHead></TableRow></TableHeader>
            <TableBody>{quizzes.map((q) => (
              <TableRow key={q._id}>
                <TableCell><Link to={`/admin/quizzes/${q._id}`} className="font-medium hover:underline">{q.title}</Link><div className="text-sm text-muted-foreground">/{q.slug}</div></TableCell>
                <TableCell><Badge variant={statusLabels[q.status]?.variant}>{statusLabels[q.status]?.label}</Badge></TableCell>
                <TableCell>{q.attempts_count || 0}</TableCell>
                <TableCell className="text-right">{q.views || 0}</TableCell>
                <TableCell><DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="icon"><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem asChild><Link to={`/admin/quizzes/${q._id}`}><Edit className="mr-2 h-4 w-4" /> Редактировать</Link></DropdownMenuItem><DropdownMenuItem className="text-destructive" onClick={() => setDeleteId(q._id)}><Trash2 className="mr-2 h-4 w-4" /> Удалить</DropdownMenuItem></DropdownMenuContent></DropdownMenu></TableCell>
              </TableRow>
            ))}</TableBody></Table>
        )}
      </CardContent></Card>

      {totalPages > 1 && <div className="flex items-center justify-between"><div className="text-sm text-muted-foreground">Показано {(page - 1) * limit + 1}-{Math.min(page * limit, total)} из {total}</div><div className="flex items-center gap-2"><Button variant="outline" size="icon" disabled={page <= 1} onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', String(page - 1)); setSearchParams(p); }}><ChevronLeft className="h-4 w-4" /></Button><span className="text-sm">{page} / {totalPages}</span><Button variant="outline" size="icon" disabled={page >= totalPages} onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', String(page + 1)); setSearchParams(p); }}><ChevronRight className="h-4 w-4" /></Button></div></div>}

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Удалить квиз?</AlertDialogTitle><AlertDialogDescription>Это действие нельзя отменить.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Отмена</AlertDialogCancel><AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">Удалить</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </div>
  );
}
