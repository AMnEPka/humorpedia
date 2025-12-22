import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { templatesApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Save, ArrowLeft, Loader2, Star } from 'lucide-react';
import ModuleEditor from '../components/ModuleEditor';

const contentTypes = [
  { value: 'person', label: 'Человек', description: 'Шаблон для профилей людей' },
  { value: 'team', label: 'Команда', description: 'Шаблон для страниц команд' },
  { value: 'show', label: 'Шоу', description: 'Шаблон для шоу и проектов' },
  { value: 'article', label: 'Статья', description: 'Шаблон для статей' },
  { value: 'news', label: 'Новость', description: 'Шаблон для новостей' },
  { value: 'quiz', label: 'Квиз', description: 'Шаблон для викторин' },
  { value: 'wiki', label: 'Вики', description: 'Шаблон для вики-страниц' },
  { value: 'page', label: 'Страница', description: 'Общий шаблон страницы' }
];

const emptyTemplate = {
  name: '',
  description: '',
  content_type: 'person',
  modules: [],
  is_default: false
};

export default function TemplateEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';

  const [template, setTemplate] = useState(emptyTemplate);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (!isNew) {
      templatesApi.get(id)
        .then(res => setTemplate({ ...emptyTemplate, ...res.data }))
        .catch(() => setError('Ошибка загрузки шаблона'))
        .finally(() => setLoading(false));
    }
  }, [id, isNew]);

  const handleSave = async () => {
    if (!template.name.trim()) {
      setError('Укажите название шаблона');
      return;
    }

    setError('');
    setSuccess('');
    setSaving(true);

    try {
      if (isNew) {
        const res = await templatesApi.create(template);
        setSuccess('Шаблон создан!');
        navigate(`/admin/templates/${res.data.id}`, { replace: true });
      } else {
        await templatesApi.update(id, template);
        setSuccess('Шаблон сохранён!');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const handleSetDefault = async () => {
    if (isNew) return;
    try {
      await templatesApi.setDefault(id);
      setTemplate(p => ({ ...p, is_default: true }));
      setSuccess('Шаблон установлен по умолчанию!');
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const currentType = contentTypes.find(t => t.value === template.content_type);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/admin/templates')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">
              {isNew ? 'Новый шаблон' : template.name || 'Редактирование шаблона'}
            </h1>
            {currentType && (
              <p className="text-sm text-muted-foreground">{currentType.description}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isNew && !template.is_default && (
            <Button variant="outline" onClick={handleSetDefault}>
              <Star className="mr-2 h-4 w-4" /> По умолчанию
            </Button>
          )}
          {template.is_default && (
            <span className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm flex items-center gap-1">
              <Star className="h-3 w-3" /> По умолчанию
            </span>
          )}
          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Сохранить
          </Button>
        </div>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {success && <Alert><AlertDescription>{success}</AlertDescription></Alert>}

      {/* Main info */}
      <div className="grid md:grid-cols-3 gap-6">
        <div className="md:col-span-1 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Информация о шаблоне</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Название шаблона *</Label>
                <Input
                  value={template.name}
                  onChange={(e) => setTemplate(p => ({ ...p, name: e.target.value }))}
                  placeholder="Базовый шаблон команды"
                />
              </div>

              <div className="space-y-2">
                <Label>Описание</Label>
                <Textarea
                  value={template.description || ''}
                  onChange={(e) => setTemplate(p => ({ ...p, description: e.target.value }))}
                  placeholder="Для чего используется этот шаблон..."
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label>Тип контента</Label>
                <Select
                  value={template.content_type}
                  onValueChange={(v) => setTemplate(p => ({ ...p, content_type: v, modules: [] }))}
                  disabled={!isNew}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {contentTypes.map(t => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {!isNew && (
                  <p className="text-xs text-muted-foreground">
                    Тип контента нельзя изменить после создания
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Статистика</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Модулей:</span>
                <span className="font-medium">{template.modules?.length || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Тип:</span>
                <span className="font-medium">{currentType?.label}</span>
              </div>
              {template.is_default && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Статус:</span>
                  <span className="font-medium text-primary">По умолчанию</span>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="md:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Структура шаблона</CardTitle>
              <CardDescription>
                Добавьте модули, которые будут автоматически включены при создании нового контента этого типа.
                Перетаскивайте модули для изменения порядка.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ModuleEditor
                modules={template.modules || []}
                onChange={(modules) => setTemplate(p => ({ ...p, modules }))}
                contentType={template.content_type}
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
