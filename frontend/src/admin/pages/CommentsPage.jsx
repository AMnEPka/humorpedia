import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { commentsApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Check, X, Trash2, Loader2, ChevronLeft, ChevronRight, MessageSquare } from 'lucide-react';

export default function CommentsPage() {
  const [comments, setComments] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const tab = searchParams.get('tab') || 'pending';
  const page = parseInt(searchParams.get('page') || '1');
  const limit = 20;

  const fetchComments = useCallback(async () => {
    setLoading(true);
    try {
      const params = { skip: (page - 1) * limit, limit };
      const response = tab === 'pending' ? await commentsApi.listPending(params) : await commentsApi.list({ ...params, resource_type: 'article', resource_id: 'all' }).catch(() => ({ data: { items: [], total: 0 } }));
      setComments(response.data.items || []);
      setTotal(response.data.total || 0);
    } catch (err) { console.error(err); setComments([]); } finally { setLoading(false); }
  }, [tab, page]);

  useEffect(() => { fetchComments(); }, [fetchComments]);

  const handleApprove = async (id) => { try { await commentsApi.approve(id); fetchComments(); } catch (err) { console.error(err); } };
  const handleReject = async (id) => { try { await commentsApi.reject(id); fetchComments(); } catch (err) { console.error(err); } };
  const handleDelete = async () => { if (!deleteId) return; try { await commentsApi.delete(deleteId); setDeleteId(null); fetchComments(); } catch (err) { console.error(err); } };

  const totalPages = Math.ceil(total / limit);
  const formatDate = (d) => d ? new Date(d).toLocaleString('ru-RU') : '-';

  return (
    <div className="space-y-6">
      <div><h1 className="text-3xl font-bold">Комментарии</h1><p className="text-muted-foreground">Модерация комментариев</p></div>

      <Tabs value={tab} onValueChange={(v) => { const p = new URLSearchParams(); p.set('tab', v); setSearchParams(p); }}>
        <TabsList><TabsTrigger value="pending">На модерации</TabsTrigger><TabsTrigger value="all">Все</TabsTrigger></TabsList>

        <TabsContent value={tab} className="mt-6">
          <Card><CardContent className="p-0">
            {loading ? <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div> : comments.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground"><MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" /><p>{tab === 'pending' ? 'Нет комментариев на модерации' : 'Нет комментариев'}</p></div>
            ) : (
              <Table>
                <TableHeader><TableRow><TableHead>Автор</TableHead><TableHead>Текст</TableHead><TableHead>Дата</TableHead><TableHead>Статус</TableHead><TableHead className="w-[150px]"></TableHead></TableRow></TableHeader>
                <TableBody>
                  {comments.map((c) => (
                    <TableRow key={c._id}>
                      <TableCell><div className="flex items-center gap-2">{c.author_avatar && <img src={c.author_avatar} alt="" className="w-8 h-8 rounded-full" />}<span className="font-medium">{c.author_name}</span></div></TableCell>
                      <TableCell className="max-w-md"><p className="truncate">{c.text}</p><span className="text-xs text-muted-foreground">{c.resource_type} / {c.resource_id}</span></TableCell>
                      <TableCell className="text-sm">{formatDate(c.created_at)}</TableCell>
                      <TableCell>{c.approved ? <Badge>Одобрен</Badge> : <Badge variant="secondary">Ожидает</Badge>}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {!c.approved && <Button variant="outline" size="icon" onClick={() => handleApprove(c._id)} title="Одобрить"><Check className="h-4 w-4 text-green-600" /></Button>}
                          {!c.approved && <Button variant="outline" size="icon" onClick={() => handleReject(c._id)} title="Отклонить"><X className="h-4 w-4 text-red-600" /></Button>}
                          <Button variant="ghost" size="icon" onClick={() => setDeleteId(c._id)} className="text-destructive"><Trash2 className="h-4 w-4" /></Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent></Card>

          {totalPages > 1 && <div className="flex items-center justify-center gap-2 mt-4"><Button variant="outline" size="icon" disabled={page <= 1} onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', String(page - 1)); setSearchParams(p); }}><ChevronLeft className="h-4 w-4" /></Button><span className="text-sm">{page} / {totalPages}</span><Button variant="outline" size="icon" disabled={page >= totalPages} onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', String(page + 1)); setSearchParams(p); }}><ChevronRight className="h-4 w-4" /></Button></div>}
        </TabsContent>
      </Tabs>

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Удалить комментарий?</AlertDialogTitle><AlertDialogDescription>Это действие нельзя отменить.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Отмена</AlertDialogCancel><AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">Удалить</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </div>
  );
}
