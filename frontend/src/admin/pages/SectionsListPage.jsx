import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { sectionsApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Plus, Edit2, Trash2, Loader2, ChevronRight, ChevronDown, Menu } from 'lucide-react';

function SectionTreeItem({ section, onEdit, onDelete, level = 0 }) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = section.children && section.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-2 py-2 px-3 hover:bg-accent rounded-md group"
        style={{ paddingLeft: `${level * 24 + 12}px` }}
      >
        {hasChildren ? (
          <button onClick={() => setExpanded(!expanded)} className="p-0">
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
        ) : (
          <div className="w-4" />
        )}
        
        <Menu className="h-4 w-4 text-muted-foreground" />
        
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium">{section.title}</span>
            <span className="text-xs text-muted-foreground">/{section.full_path}</span>
            {section.in_main_menu && <Badge variant="outline" className="text-xs">Меню</Badge>}
            <Badge variant={section.status === 'published' ? 'default' : 'secondary'} className="text-xs">
              {section.status === 'published' ? 'Опубликовано' : section.status === 'draft' ? 'Черновик' : 'Архив'}
            </Badge>
          </div>
          <div className="text-xs text-muted-foreground">Уровень: {section.level}</div>
        </div>

        <div className="opacity-0 group-hover:opacity-100 flex gap-1">
          <Button size="sm" variant="ghost" onClick={() => onEdit(section.id)}>
            <Edit2 className="h-4 w-4" />
          </Button>
          <Button size="sm" variant="ghost" onClick={() => onDelete(section.id)}>
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </div>

      {hasChildren && expanded && (
        <div>
          {section.children.map((child) => (
            <SectionTreeItem
              key={child.id}
              section={child}
              onEdit={onEdit}
              onDelete={onDelete}
              level={level + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SectionsListPage() {
  const navigate = useNavigate();
  const [tree, setTree] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    loadTree();
  }, []);

  const loadTree = async () => {
    try {
      const res = await sectionsApi.getTree();
      setTree(res.data);
    } catch (err) {
      setError('Ошибка загрузки разделов');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Удалить раздел?')) return;
    try {
      await sectionsApi.deleteSection(id);
      loadTree();
    } catch (err) {
      alert('Ошибка удаления');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Разделы</h1>
          <p className="text-muted-foreground">Иерархическая структура сайта</p>
        </div>
        <Button onClick={() => navigate('/admin/sections/new')}>
          <Plus className="mr-2 h-4 w-4" /> Новый раздел
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Структура разделов</CardTitle>
          <Input
            placeholder="Поиск..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </CardHeader>
        <CardContent>
          {tree.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <p>Нет разделов</p>
              <Button
                variant="link"
                onClick={() => navigate('/admin/sections/new')}
                className="mt-2"
              >
                Создать первый раздел
              </Button>
            </div>
          ) : (
            <div className="space-y-1">
              {tree.map((section) => (
                <SectionTreeItem
                  key={section.id}
                  section={section}
                  onEdit={(id) => navigate(`/admin/sections/${id}`)}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
