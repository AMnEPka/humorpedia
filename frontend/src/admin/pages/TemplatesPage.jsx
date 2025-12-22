import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { templatesApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Plus, Edit, Trash2, Star, Loader2, LayoutTemplate, Users, UsersRound, Tv, FileText, Newspaper, HelpCircle, BookOpen, File } from 'lucide-react';

const contentTypes = [
  { value: 'person', label: 'Человек', icon: Users },
  { value: 'team', label: 'Команда', icon: UsersRound },
  { value: 'show', label: 'Шоу', icon: Tv },
  { value: 'article', label: 'Статья', icon: FileText },
  { value: 'news', label: 'Новость', icon: Newspaper },
  { value: 'quiz', label: 'Квиз', icon: HelpCircle },
  { value: 'wiki', label: 'Вики', icon: BookOpen },
  { value: 'page', label: 'Страница', icon: File }
];

export default function TemplatesPage() {
  const [templates, setTemplates] = useState([]);
  const [moduleTypes, setModuleTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState(null);
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

  const handleSetDefault = async (id) => {
    try { await templatesApi.setDefault(id); fetchData(); } catch (err) { console.error(err); }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try { await templatesApi.delete(deleteId); setDeleteId(null); fetchData(); } catch (err) { console.error(err); }
  };

  // Group templates by content type
  const templatesByType = contentTypes.reduce((acc, type) => {
    acc[type.value] = templates.filter(t => t.content_type === type.value);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Шаблоны</h1>
          <p className="text-muted-foreground">Управление шаблонами для разных типов контента</p>
        </div>
        <Button asChild>
          <Link to="/admin/templates/new">
            <Plus className="mr-2 h-4 w-4" /> Создать шаблон
          </Link>
        </Button>
      </div>

      {/* Quick access to base templates */}
      <Card>
        <CardHeader>
          <CardTitle>Базовые шаблоны</CardTitle>
          <CardDescription>
            Быстрый доступ к созданию или редактированию шаблонов по умолчанию для каждого типа контента
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {contentTypes.map(type => {
              const Icon = type.icon;
              const defaultTemplate = templates.find(t => t.content_type === type.value && t.is_default);
              const hasTemplates = templatesByType[type.value]?.length > 0;
              
              return (
                <Link
                  key={type.value}
                  to={defaultTemplate ? `/admin/templates/${defaultTemplate._id}` : `/admin/templates/new?type=${type.value}`}
                  className="flex items-center gap-3 p-4 border rounded-lg hover:bg-muted/50 transition-colors"
                >
                  <div className="p-2 bg-muted rounded-lg">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium">{type.label}</div>
                    <div className="text-xs text-muted-foreground">
                      {defaultTemplate ? (
                        <span className="flex items-center gap-1">
                          <Star className="h-3 w-3 text-primary" /> Настроен
                        </span>
                      ) : hasTemplates ? (
                        `${templatesByType[type.value].length} шаблон(ов)`
                      ) : (
                        'Создать'
                      )}
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Filter */}
      <Card>
        <CardContent className="pt-6">
          <Select value={filter || 'all'} onValueChange={(v) => setFilter(v === 'all' ? '' : v)}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Фильтр по типу" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все типы</SelectItem>
              {contentTypes.map(t => (
                <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {/* Templates list */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : templates.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <LayoutTemplate className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>Нет шаблонов</p>
              <p className="text-sm mt-1">Создайте шаблон для типа контента</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Название</TableHead>
                  <TableHead>Тип контента</TableHead>
                  <TableHead>Модулей</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead className="w-[150px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {templates.map((t) => {
                  const typeInfo = contentTypes.find(c => c.value === t.content_type);
                  const Icon = typeInfo?.icon || File;
                  
                  return (
                    <TableRow key={t._id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-muted rounded">
                            <Icon className="h-4 w-4" />
                          </div>
                          <div>
                            <div className="font-medium">{t.name}</div>
                            {t.description && (
                              <div className="text-sm text-muted-foreground truncate max-w-xs">
                                {t.description}
                              </div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {typeInfo?.label || t.content_type}
                        </Badge>
                      </TableCell>
                      <TableCell>{t.modules?.length || 0}</TableCell>
                      <TableCell>
                        {t.is_default && (
                          <Badge className="bg-primary/10 text-primary hover:bg-primary/20">
                            <Star className="h-3 w-3 mr-1" /> По умолчанию
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="icon" asChild>
                            <Link to={`/admin/templates/${t._id}`}>
                              <Edit className="h-4 w-4" />
                            </Link>
                          </Button>
                          {!t.is_default && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleSetDefault(t._id)}
                              title="Сделать по умолчанию"
                            >
                              <Star className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setDeleteId(t._id)}
                            className="text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Module types reference */}
      <Card>
        <CardHeader>
          <CardTitle>Справочник модулей</CardTitle>
          <CardDescription>
            Доступные типы модулей для добавления в шаблоны
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-3 lg:grid-cols-4 gap-3">
            {moduleTypes.map((m) => (
              <div key={m.type} className="border rounded-lg p-3">
                <div className="font-medium">{m.name}</div>
                <div className="text-sm text-muted-foreground">{m.description}</div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {m.for_types.map(t => (
                    <Badge key={t} variant="outline" className="text-xs">{t}</Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить шаблон?</AlertDialogTitle>
            <AlertDialogDescription>
              Это действие нельзя отменить. Шаблон будет удалён навсегда.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
