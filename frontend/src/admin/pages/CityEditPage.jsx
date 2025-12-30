import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { contentApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select, SelectContent, SelectItem, 
  SelectTrigger, SelectValue
} from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Save, ArrowLeft, Loader2, Plus, X, GripVertical,
  Image as ImageIcon, Trash2, MapPin
} from 'lucide-react';
import ModuleEditor from '../components/ModuleEditor';
import TagSelector from '../components/TagSelector';
import MediaSelector from '../components/MediaSelector';

const emptyCity = {
  title: '',
  slug: '',
  name: '',
  status: 'draft',
  poster: null,
  description: '',
  facts: {},
  modules: [],
  tags: [],
  seo: {
    meta_title: '',
    meta_description: '',
    keywords: []
  },
  related_person_ids: [],
  related_team_ids: []
};

export default function CityEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';

  const [city, setCity] = useState(emptyCity);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [newFactKey, setNewFactKey] = useState('');
  const [newFactValue, setNewFactValue] = useState('');

  useEffect(() => {
    if (!isNew) {
      const fetchCity = async () => {
        try {
          const response = await contentApi.getCity(id);
          const data = response.data;
          
          // Normalize poster
          let poster = data.poster;
          if (poster && typeof poster === 'string') {
            poster = { url: poster, alt: '', caption: '', thumbnail: poster };
          }
          
          setCity({
            ...emptyCity,
            ...data,
            poster: poster || null,
            facts: data.facts || {},
            modules: data.modules || [],
            tags: data.tags || [],
            seo: data.seo || emptyCity.seo,
            related_person_ids: data.related_person_ids || [],
            related_team_ids: data.related_team_ids || []
          });
        } catch (error) {
          console.error('Error fetching city:', error);
          setError('Ошибка загрузки города');
        } finally {
          setLoading(false);
        }
      };
      fetchCity();
    }
  }, [id, isNew]);

  const handleChange = (field, value) => {
    setCity(prev => ({ ...prev, [field]: value }));
    setError('');
    setSuccess('');
  };

  const handleSeoChange = (field, value) => {
    setCity(prev => ({
      ...prev,
      seo: { ...prev.seo, [field]: value }
    }));
  };

  const generateSlug = () => {
    const slug = (city.name || city.title)
      .toLowerCase()
      .replace(/[а-яё]/g, char => {
        const map = {
          'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
          'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
          'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
          'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
          'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        };
        return map[char] || char;
      })
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
    handleChange('slug', slug);
  };

  const handleAddFact = () => {
    if (!newFactKey.trim() || !newFactValue.trim()) return;
    handleChange('facts', {
      ...city.facts,
      [newFactKey.trim()]: newFactValue.trim()
    });
    setNewFactKey('');
    setNewFactValue('');
  };

  const handleRemoveFact = (key) => {
    const newFacts = { ...city.facts };
    delete newFacts[key];
    handleChange('facts', newFacts);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      const payload = {
        title: city.title,
        slug: city.slug,
        name: city.name,
        poster: city.poster,
        description: city.description,
        facts: city.facts,
        modules: city.modules,
        tags: city.tags,
        seo: city.seo,
        status: city.status,
        related_person_ids: city.related_person_ids,
        related_team_ids: city.related_team_ids
      };

      if (isNew) {
        const response = await contentApi.createCity(payload);
        setSuccess('Город создан');
        navigate(`/admin/cities/${response.data.id}`);
      } else {
        await contentApi.updateCity(id, payload);
        setSuccess('Изменения сохранены');
      }
    } catch (error) {
      console.error('Error saving city:', error);
      setError(error.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/admin/cities')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Назад
          </Button>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <MapPin className="h-6 w-6" />
              {isNew ? 'Новый город' : city.title || city.name}
            </h1>
            {!isNew && city.slug && (
              <a 
                href={`/city/${city.slug}`} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:underline"
              >
                /city/{city.slug}
              </a>
            )}
          </div>
        </div>
        <Button onClick={handleSubmit} disabled={saving}>
          {saving ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          Сохранить
        </Button>
      </div>

      {/* Messages */}
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

      <form onSubmit={handleSubmit}>
        <Tabs defaultValue="main" className="space-y-6">
          <TabsList>
            <TabsTrigger value="main">Основное</TabsTrigger>
            <TabsTrigger value="content">Контент</TabsTrigger>
            <TabsTrigger value="facts">Факты</TabsTrigger>
            <TabsTrigger value="seo">SEO</TabsTrigger>
          </TabsList>

          {/* Main Tab */}
          <TabsContent value="main" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Main info */}
              <div className="lg:col-span-2 space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Основная информация</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="title">Заголовок страницы *</Label>
                        <Input
                          id="title"
                          value={city.title}
                          onChange={(e) => handleChange('title', e.target.value)}
                          placeholder="Москва"
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="name">Название города *</Label>
                        <Input
                          id="name"
                          value={city.name}
                          onChange={(e) => handleChange('name', e.target.value)}
                          placeholder="Москва"
                          required
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="slug">URL (slug) *</Label>
                      <div className="flex gap-2">
                        <Input
                          id="slug"
                          value={city.slug}
                          onChange={(e) => handleChange('slug', e.target.value)}
                          placeholder="moscow"
                          required
                        />
                        <Button type="button" variant="outline" onClick={generateSlug}>
                          Генерировать
                        </Button>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="description">Краткое описание</Label>
                      <Textarea
                        id="description"
                        value={city.description || ''}
                        onChange={(e) => handleChange('description', e.target.value)}
                        placeholder="Краткое описание города и его связи с юмором..."
                        rows={4}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label>Теги</Label>
                      <TagSelector
                        selected={city.tags}
                        onChange={(tags) => handleChange('tags', tags)}
                      />
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Sidebar */}
              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Статус</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Select 
                      value={city.status} 
                      onValueChange={(value) => handleChange('status', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="draft">Черновик</SelectItem>
                        <SelectItem value="published">Опубликовано</SelectItem>
                        <SelectItem value="archived">В архиве</SelectItem>
                      </SelectContent>
                    </Select>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Постер</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <MediaSelector
                      value={city.poster}
                      onChange={(media) => handleChange('poster', media)}
                      type="image"
                    />
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* Content Tab */}
          <TabsContent value="content">
            <Card>
              <CardHeader>
                <CardTitle>Модули контента</CardTitle>
                <CardDescription>
                  Добавьте текстовые блоки, галереи и другие модули
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ModuleEditor
                  modules={city.modules}
                  onChange={(modules) => handleChange('modules', modules)}
                />
              </CardContent>
            </Card>
          </TabsContent>

          {/* Facts Tab */}
          <TabsContent value="facts">
            <Card>
              <CardHeader>
                <CardTitle>Факты о городе</CardTitle>
                <CardDescription>
                  Ключевые факты для таблицы на странице города
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Existing facts */}
                {Object.entries(city.facts || {}).map(([key, value]) => (
                  <div key={key} className="flex items-center gap-2">
                    <Input value={key} disabled className="w-1/3" />
                    <Input value={value} disabled className="flex-1" />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => handleRemoveFact(key)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}

                {/* Add new fact */}
                <div className="flex items-center gap-2">
                  <Input
                    value={newFactKey}
                    onChange={(e) => setNewFactKey(e.target.value)}
                    placeholder="Название факта"
                    className="w-1/3"
                  />
                  <Input
                    value={newFactValue}
                    onChange={(e) => setNewFactValue(e.target.value)}
                    placeholder="Значение"
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleAddFact}
                    disabled={!newFactKey.trim() || !newFactValue.trim()}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* SEO Tab */}
          <TabsContent value="seo">
            <Card>
              <CardHeader>
                <CardTitle>SEO настройки</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="meta_title">Meta Title</Label>
                  <Input
                    id="meta_title"
                    value={city.seo?.meta_title || ''}
                    onChange={(e) => handleSeoChange('meta_title', e.target.value)}
                    placeholder="SEO заголовок"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="meta_description">Meta Description</Label>
                  <Textarea
                    id="meta_description"
                    value={city.seo?.meta_description || ''}
                    onChange={(e) => handleSeoChange('meta_description', e.target.value)}
                    placeholder="SEO описание"
                    rows={3}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </form>
    </div>
  );
}
