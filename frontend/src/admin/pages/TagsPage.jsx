import { useState, useEffect, useCallback } from 'react';
import { tagsApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Plus, Search, Edit, Trash2, Loader2 } from 'lucide-react';

export default function TagsPage() {
  const [tags, setTags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [editTag, setEditTag] = useState(null);
  const [deleteId, setDeleteId] = useState(null);
  const [newTag, setNewTag] = useState({ name: '', slug: '' });
  const [showNew, setShowNew] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchTags = useCallback(async () => {
    setLoading(true);
    try {
      const response = await tagsApi.list({ limit: 500, ...(search && { search }) });
      setTags(response.data.items);
    } catch (err) { console.error(err); } finally { setLoading(false); }
  }, [search]);

  useEffect(() => { fetchTags(); }, [fetchTags]);

  const handleCreate = async () => {
    if (!newTag.name.trim()) return;
    setSaving(true);
    try {
      await tagsApi.create(newTag);
      setShowNew(false);
      setNewTag({ name: '', slug: '' });
      fetchTags();
    } catch (err) { console.error(err); } finally { setSaving(false); }
  };

  const handleUpdate = async () => {
    if (!editTag?.name.trim()) return;
    setSaving(true);
    try {
      await tagsApi.update(editTag._id, editTag);
      setEditTag(null);
      fetchTags();
    } catch (err) { console.error(err); } finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await tagsApi.delete(deleteId);
      setDeleteId(null);
      fetchTags();
    } catch (err) { console.error(err); }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-3xl font-bold">Теги</h1><p className="text-muted-foreground">Управление тегами контента</p></div>
        <Button onClick={() => setShowNew(true)}><Plus className="mr-2 h-4 w-4" /> Добавить</Button>
      </div>

      <Card><CardContent className="pt-6">
        <div className="relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" /><Input placeholder="Поиск тегов..." className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
      </CardContent></Card>

      <Card><CardContent className="p-0">
        {loading ? <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div> : tags.length === 0 ? <div className="text-center py-12 text-muted-foreground">Нет тегов</div> : (
          <Table>
            <TableHeader><TableRow><TableHead>Название</TableHead><TableHead>Slug</TableHead><TableHead className="text-right">Использований</TableHead><TableHead className="w-[100px]"></TableHead></TableRow></TableHeader>
            <TableBody>
              {tags.map((tag) => (
                <TableRow key={tag._id}>
                  <TableCell className="font-medium">{tag.name}</TableCell>
                  <TableCell className="text-muted-foreground">{tag.slug}</TableCell>
                  <TableCell className="text-right">{tag.usage_count || 0}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" onClick={() => setEditTag(tag)}><Edit className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" onClick={() => setDeleteId(tag._id)} className="text-destructive"><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent></Card>

      {/* New tag dialog */}
      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent><DialogHeader><DialogTitle>Новый тег</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2"><Label>Название</Label><Input value={newTag.name} onChange={(e) => setNewTag({ ...newTag, name: e.target.value })} /></div>
            <div className="space-y-2"><Label>Slug (опционально)</Label><Input value={newTag.slug} onChange={(e) => setNewTag({ ...newTag, slug: e.target.value })} /></div>
          </div>
          <DialogFooter><Button onClick={handleCreate} disabled={saving}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Создать</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit tag dialog */}
      <Dialog open={!!editTag} onOpenChange={() => setEditTag(null)}>
        <DialogContent><DialogHeader><DialogTitle>Редактировать тег</DialogTitle></DialogHeader>
          {editTag && <div className="space-y-4">
            <div className="space-y-2"><Label>Название</Label><Input value={editTag.name} onChange={(e) => setEditTag({ ...editTag, name: e.target.value })} /></div>
            <div className="space-y-2"><Label>Slug</Label><Input value={editTag.slug} onChange={(e) => setEditTag({ ...editTag, slug: e.target.value })} /></div>
          </div>}
          <DialogFooter><Button onClick={handleUpdate} disabled={saving}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Сохранить</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Удалить тег?</AlertDialogTitle><AlertDialogDescription>Это действие нельзя отменить.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Отмена</AlertDialogCancel><AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">Удалить</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </div>
  );
}
