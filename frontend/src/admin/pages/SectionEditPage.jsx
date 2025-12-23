import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { sectionsApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Switch } from '@/components/ui/switch';
import { Save, ArrowLeft, Loader2, ExternalLink } from 'lucide-react';
import ModuleEditor from '../components/ModuleEditor';
import TagSelector from '../components/TagSelector';

const emptySection = {
  title: '',
  slug: '',
  description: '',
  parent_id: null,
  order: 0,
  in_main_menu: false,
  menu_title: '',
  modules: [],
  child_types: [],
  show_children_list: true,
  status: 'draft',
  tags: [],
  seo: { meta_title: '', meta_description: '' }
};

export default function SectionEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';

  const [section, setSection] = useState(emptySection);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [tree, setTree] = useState([]);

  useEffect(() => {
    loadTree();
    if (!isNew) {
      sectionsApi
        .getSection(id)
        .then((res) =>
          setSection({ ...emptySection, ...res.data, seo: { ...emptySection.seo, ...res.data.seo } })
        )
        .catch(() => setError('Ошибка загрузки'))
        .finally(() => setLoading(false));
    }
  }, [id, isNew]);

  const loadTree = async () => {
    try {
      const res = await sectionsApi.getTree();
      setTree(flattenTree(res.data));
    } catch (err) {
      console.error('Error loading tree:', err);
    }
  };

  const flattenTree = (nodes, result = []) => {
    for (const node of nodes) {
      result.push(node);
      if (node.children && node.children.length > 0) {
        flattenTree(node.children, result);
      }
    }
    return result;
  };

  const generateSlug = (t) =>
    t
      .toLowerCase()
      .replace(
        /[а-яё]/g,
        (c) =>
          ({
            а: 'a',
            б: 'b',
            в: 'v',
            г: 'g',
            д: 'd',
            е: 'e',
            ё: 'yo',
            ж: 'zh',
            з: 'z',
            и: 'i',
            й: 'y',
            к: 'k',
            л: 'l',
            м: 'm',
            н: 'n',
            о: 'o',
            п: 'p',
            р: 'r',
            с: 's',
            т: 't',
            у: 'u',
            ф: 'f',
            х: 'kh',
            ц: 'ts',
            ч: 'ch',
            ш: 'sh',
            щ: 'shch',
            ы: 'y',
            э: 'e',
            ю: 'yu',
            я: 'ya'
          }[c] || '')
      )
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');

  const handleSave = async () => {
    setError('');
    setSuccess('');
    setSaving(true);
    try {
      const payload = { ...section };
      if (!payload.parent_id) payload.parent_id = null;
      if (!payload.menu_title) payload.menu_title = null;

      if (isNew) {
        const res = await sectionsApi.createSection(payload);
        setSuccess('Создано!');
        navigate(`/admin/sections/${res.data.id}`, { replace: true });
      } else {
        await sectionsApi.updateSection(id, payload);
        setSuccess('Сохранено!');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка');
    } finally {
      setSaving(false);
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
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/admin/sections')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">
              {isNew ? 'Новый раздел' : section.title || 'Редактирование'}
            </h1>
            {!isNew && <p className="text-sm text-muted-foreground">{section.full_path}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isNew && section.full_path && (
            <Button variant="outline" onClick={() => window.open(section.full_path, '_blank')}>
              <ExternalLink className="mr-2 h-4 w-4" />
              Предпросмотр
            </Button>
          )}
          <Select value={section.status} onValueChange={(v) => setSection((p) => ({ ...p, status: v }))}>
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="draft">Черновик</SelectItem>
              <SelectItem value="published">Опубликовать</SelectItem>
              <SelectItem value="archived">В архив</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Сохранить
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {success && (
        <Alert>
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="main" className="space-y-6">
        <TabsList>
          <TabsTrigger value="main">Основное</TabsTrigger>
          <TabsTrigger value="modules">Модули ({section.modules.length})</TabsTrigger>
          <TabsTrigger value="hierarchy">Иерархия</TabsTrigger>
          <TabsTrigger value="seo">SEO</TabsTrigger>
        </TabsList>

        <TabsContent value="main" className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Основная информация</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Заголовок</Label>
                  <Input
                    value={section.title}
                    onChange={(e) =>
                      setSection((p) => ({
                        ...p,
                        title: e.target.value,
                        slug: p.slug || generateSlug(e.target.value)
                      }))
                    }
                    placeholder="Заголовок раздела"
                  />
                </div>
                <div className="space-y-2">
                  <Label>URL (slug)</Label>
                  <Input
                    value={section.slug}
                    onChange={(e) => setSection((p) => ({ ...p, slug: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Описание</Label>
                  <Textarea
                    value={section.description || ''}
                    onChange={(e) => setSection((p) => ({ ...p, description: e.target.value }))}
                    rows={3}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Настройки</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-2">
                  <Switch
                    checked={section.in_main_menu}
                    onCheckedChange={(v) => setSection((p) => ({ ...p, in_main_menu: v }))}
                  />
                  <Label>Показать в главном меню</Label>
                </div>
                <div className="space-y-2">
                  <Label>Заголовок для меню (опционально)</Label>
                  <Input
                    value={section.menu_title || ''}
                    onChange={(e) => setSection((p) => ({ ...p, menu_title: e.target.value }))}
                    placeholder="Если нужен короткий вариант"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Порядок сортировки</Label>
                  <Input
                    type="number"
                    value={section.order}
                    onChange={(e) => setSection((p) => ({ ...p, order: parseInt(e.target.value) || 0 }))}
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Теги</CardTitle>
            </CardHeader>
            <CardContent>
              <TagSelector
                value={section.tags}
                onChange={(tags) => setSection((p) => ({ ...p, tags }))}
                placeholder="Выберите или добавьте тег..."
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="modules">
          <ModuleEditor
            modules={section.modules}
            onChange={(m) => setSection((p) => ({ ...p, modules: m }))}
            contentType="section"
          />
        </TabsContent>

        <TabsContent value="hierarchy" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Иерархия</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Родительский раздел</Label>
                <Select
                  value={section.parent_id || 'null'}
                  onValueChange={(v) => setSection((p) => ({ ...p, parent_id: v === 'null' ? null : v }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Корневой раздел" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="null">Корневой раздел (без родителя)</SelectItem>
                    {tree
                      .filter((s) => s.id !== id)
                      .map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {'  '.repeat(s.level)}
                          {s.title} ({s.full_path})
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2">
                <Switch
                  checked={section.show_children_list}
                  onCheckedChange={(v) => setSection((p) => ({ ...p, show_children_list: v }))}
                />
                <Label>Показывать список дочерних страниц</Label>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="seo">
          <Card>
            <CardHeader>
              <CardTitle>SEO настройки</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Meta Title</Label>
                <Input
                  value={section.seo.meta_title || ''}
                  onChange={(e) =>
                    setSection((p) => ({ ...p, seo: { ...p.seo, meta_title: e.target.value } }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Meta Description</Label>
                <Textarea
                  value={section.seo.meta_description || ''}
                  onChange={(e) =>
                    setSection((p) => ({ ...p, seo: { ...p.seo, meta_description: e.target.value } }))
                  }
                  rows={3}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
