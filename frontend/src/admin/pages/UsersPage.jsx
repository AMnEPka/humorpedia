import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { usersApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Search, Edit, Ban, CheckCircle, Trash2, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';

const roleLabels = { admin: 'Админ', editor: 'Редактор', moderator: 'Модератор', user: 'Пользователь' };
const roleColors = { admin: 'destructive', editor: 'default', moderator: 'secondary', user: 'outline' };

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [editUser, setEditUser] = useState(null);
  const [deleteId, setDeleteId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

  const page = parseInt(searchParams.get('page') || '1');
  const search = searchParams.get('search') || '';
  const role = searchParams.get('role') || '';
  const limit = 20;

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params = { skip: (page - 1) * limit, limit, ...(search && { search }), ...(role && { role }) };
      const response = await usersApi.list(params);
      setUsers(response.data.items);
      setTotal(response.data.total);
    } catch (err) { console.error(err); } finally { setLoading(false); }
  }, [page, search, role]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleBan = async (id, ban) => { try { ban ? await usersApi.ban(id) : await usersApi.unban(id); fetchUsers(); } catch (err) { console.error(err); } };
  const handleUpdate = async () => { if (!editUser) return; setSaving(true); try { await usersApi.update(editUser._id, editUser); setEditUser(null); fetchUsers(); } catch (err) { console.error(err); } finally { setSaving(false); } };
  const handleDelete = async () => { if (!deleteId) return; try { await usersApi.delete(deleteId); setDeleteId(null); fetchUsers(); } catch (err) { console.error(err); } };

  const totalPages = Math.ceil(total / limit);
  const formatDate = (d) => d ? new Date(d).toLocaleDateString('ru-RU') : '-';

  return (
    <div className="space-y-6">
      <div><h1 className="text-3xl font-bold">Пользователи</h1><p className="text-muted-foreground">Управление пользователями</p></div>

      <Card><CardContent className="pt-6"><div className="flex flex-col md:flex-row gap-4">
        <div className="flex-1 relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" /><Input placeholder="Поиск..." className="pl-9" value={search} onChange={(e) => { const p = new URLSearchParams(searchParams); e.target.value ? p.set('search', e.target.value) : p.delete('search'); p.set('page', '1'); setSearchParams(p); }} /></div>
        <Select value={role || 'all'} onValueChange={(v) => { const p = new URLSearchParams(searchParams); v !== 'all' ? p.set('role', v) : p.delete('role'); p.set('page', '1'); setSearchParams(p); }}><SelectTrigger className="w-[180px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Все роли</SelectItem><SelectItem value="admin">Админы</SelectItem><SelectItem value="editor">Редакторы</SelectItem><SelectItem value="moderator">Модераторы</SelectItem><SelectItem value="user">Пользователи</SelectItem></SelectContent></Select>
      </div></CardContent></Card>

      <Card><CardContent className="p-0">
        {loading ? <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div> : users.length === 0 ? <div className="text-center py-12 text-muted-foreground">Ничего не найдено</div> : (
          <Table>
            <TableHeader><TableRow><TableHead>Пользователь</TableHead><TableHead>Email</TableHead><TableHead>Роль</TableHead><TableHead>Регистрация</TableHead><TableHead>Статус</TableHead><TableHead className="w-[150px]"></TableHead></TableRow></TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u._id}>
                  <TableCell><div className="flex items-center gap-2">{u.profile?.avatar && <img src={u.profile.avatar} alt="" className="w-8 h-8 rounded-full" />}<span className="font-medium">{u.username}</span></div></TableCell>
                  <TableCell>{u.email || '-'}</TableCell>
                  <TableCell><Badge variant={roleColors[u.role]}>{roleLabels[u.role]}</Badge></TableCell>
                  <TableCell>{formatDate(u.created_at)}</TableCell>
                  <TableCell>{u.banned ? <Badge variant="destructive">Забанен</Badge> : u.verified ? <Badge variant="outline">Подтвержден</Badge> : <Badge variant="secondary">Не подтвержден</Badge>}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" onClick={() => setEditUser(u)}><Edit className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" onClick={() => handleBan(u._id, !u.banned)} title={u.banned ? 'Разблокировать' : 'Заблокировать'}>{u.banned ? <CheckCircle className="h-4 w-4 text-green-600" /> : <Ban className="h-4 w-4 text-orange-600" />}</Button>
                      <Button variant="ghost" size="icon" onClick={() => setDeleteId(u._id)} className="text-destructive"><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent></Card>

      {totalPages > 1 && <div className="flex items-center justify-center gap-2"><Button variant="outline" size="icon" disabled={page <= 1} onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', String(page - 1)); setSearchParams(p); }}><ChevronLeft className="h-4 w-4" /></Button><span className="text-sm">{page} / {totalPages}</span><Button variant="outline" size="icon" disabled={page >= totalPages} onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', String(page + 1)); setSearchParams(p); }}><ChevronRight className="h-4 w-4" /></Button></div>}

      {/* Edit user dialog */}
      <Dialog open={!!editUser} onOpenChange={() => setEditUser(null)}>
        <DialogContent><DialogHeader><DialogTitle>Редактировать пользователя</DialogTitle></DialogHeader>
          {editUser && <div className="space-y-4">
            <div className="space-y-2"><Label>Имя пользователя</Label><Input value={editUser.username} onChange={(e) => setEditUser({ ...editUser, username: e.target.value })} /></div>
            <div className="space-y-2"><Label>Email</Label><Input value={editUser.email || ''} onChange={(e) => setEditUser({ ...editUser, email: e.target.value })} /></div>
            <div className="space-y-2"><Label>Роль</Label><Select value={editUser.role} onValueChange={(v) => setEditUser({ ...editUser, role: v })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="user">Пользователь</SelectItem><SelectItem value="moderator">Модератор</SelectItem><SelectItem value="editor">Редактор</SelectItem><SelectItem value="admin">Админ</SelectItem></SelectContent></Select></div>
          </div>}
          <DialogFooter><Button onClick={handleUpdate} disabled={saving}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Сохранить</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Удалить пользователя?</AlertDialogTitle><AlertDialogDescription>Это действие нельзя отменить.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Отмена</AlertDialogCancel><AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">Удалить</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </div>
  );
}
