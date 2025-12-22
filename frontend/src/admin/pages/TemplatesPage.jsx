import { useState, useEffect, useCallback } from 'react';
import { templatesApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Plus, Edit, Trash2, Star, Loader2, LayoutTemplate } from 'lucide-react';

const contentTypes = [
  { value: 'person', label: 'Человек' },
  { value: 'team', label: 'Команда' },
  { value: 'show', label: 'Шоу' },
  { value: 'article', label: 'Статья' },
  { value: 'news', label: 'Новость' },
  { value: 'quiz', label: 'Квиз' },
  { value: 'wiki', label: 'Вики' },
  { value: 'page', label: 'Страница' }
];

export default function TemplatesPage() {
  const [templates, setTemplates] = useState([]);
  const [moduleTypes, setModuleTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editTemplate, setEditTemplate] = useState(null);
  const [deleteId, setDeleteId] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [newTemplate, setNewTemplate] = useState({ name: '', description: '', content_type: 'person', modules: [] });
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [templatesRes, typesRes] = await Promise.all([
        templatesApi.list({ ...(filter && { content_type: filter }) }),
        templatesApi.getModuleTypes()
      ]);
      setTemplates(templatesRes.data.items);
      setModuleTypes(typesRes.data);
    } catch (err) { console.error(err); } finally { setLoading(false); }
  }, [filter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleCreate = async () => {
    if (!newTemplate.name.trim()) return;
    setSaving(true);
    try {
      await templatesApi.create(newTemplate);
      setShowNew(false);
      setNewTemplate({ name: '', description: '', content_type: 'person', modules: [] });
      fetchData();
    } catch (err) { console.error(err); } finally { setSaving(false); }
  };

  const handleSetDefault = async (id) => {
    try { await templatesApi.setDefault(id); fetchData(); } catch (err) { console.error(err); }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try { await templatesApi.delete(deleteId); setDeleteId(null); fetchData(); } catch (err) { console.error(err); }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-3xl font-bold">Шаблоны</h1><p className="text-muted-foreground">Управление шаблонами страниц</p></div>
        <Button onClick={() => setShowNew(true)}><Plus className="mr-2 h-4 w-4" /> Создать</Button>
      </div>

      <Card><CardContent className="pt-6">
        <Select value={filter || 'all'} onValueChange={(v) => setFilter(v === 'all' ? '' : v)}>
          <SelectTrigger className="w-[200px]"><SelectValue placeholder="Тип контента" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Все типы</SelectItem>{contentTypes.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}</SelectContent>
        </Select>
      </CardContent></Card>

      <Card><CardContent className="p-0">
        {loading ? <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div> : templates.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground"><LayoutTemplate className="h-12 w-12 mx-auto mb-4 opacity-50" /><p>Нет шаблонов</p></div>
        ) : (
          <Table>
            <TableHeader><TableRow><TableHead>Название</TableHead><TableHead>Тип</TableHead><TableHead>Модулей</TableHead><TableHead>Статус</TableHead><TableHead className="w-[150px]"></TableHead></TableRow></TableHeader>
            <TableBody>
              {templates.map((t) => (
                <TableRow key={t._id}>
                  <TableCell><div className="font-medium">{t.name}</div>{t.description && <div className="text-sm text-muted-foreground">{t.description}</div>}</TableCell>
                  <TableCell><Badge variant="outline">{contentTypes.find(c => c.value === t.content_type)?.label || t.content_type}</Badge></TableCell>
                  <TableCell>{t.modules?.length || 0}</TableCell>
                  <TableCell>{t.is_default && <Badge><Star className="h-3 w-3 mr-1" />По умолчанию</Badge>}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {!t.is_default && <Button variant="ghost" size="icon" onClick={() => handleSetDefault(t._id)} title="Сделать по умолчанию"><Star className="h-4 w-4" /></Button>}
                      <Button variant="ghost" size="icon" onClick={() => setDeleteId(t._id)} className="text-destructive"><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent></Card>

      {/* Module types reference */}
      <Card>
        <CardHeader><CardTitle>Доступные модули</CardTitle><CardDescription>Типы модулей для страниц</CardDescription></CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-3 lg:grid-cols-4 gap-3">
            {moduleTypes.map((m) => (
              <div key={m.type} className="border rounded-lg p-3">
                <div className="font-medium">{m.name}</div>
                <div className="text-sm text-muted-foreground">{m.description}</div>
                <div className="flex flex-wrap gap-1 mt-2">{m.for_types.map(t => <Badge key={t} variant="outline" className="text-xs">{t}</Badge>)}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* New template dialog */}
      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent><DialogHeader><DialogTitle>Новый шаблон</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2"><Label>Название</Label><Input value={newTemplate.name} onChange={(e) => setNewTemplate({ ...newTemplate, name: e.target.value })} placeholder="Шаблон для команд КВН" /></div>
            <div className="space-y-2"><Label>Описание</Label><Textarea value={newTemplate.description} onChange={(e) => setNewTemplate({ ...newTemplate, description: e.target.value })} rows={2} /></div>
            <div className="space-y-2"><Label>Тип контента</Label><Select value={newTemplate.content_type} onValueChange={(v) => setNewTemplate({ ...newTemplate, content_type: v })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{contentTypes.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}</SelectContent></Select></div>
          </div>
          <DialogFooter><Button onClick={handleCreate} disabled={saving}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Создать</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Удалить шаблон?</AlertDialogTitle><AlertDialogDescription>Это действие нельзя отменить.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Отмена</AlertDialogCancel><AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">Удалить</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </div>
  );
}
