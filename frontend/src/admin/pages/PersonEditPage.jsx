import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { contentApi, tagsApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import {
  Select, SelectContent, SelectItem, 
  SelectTrigger, SelectValue
} from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Save, ArrowLeft, Loader2, Plus, X, GripVertical,
  Image as ImageIcon, Trash2, ExternalLink
} from 'lucide-react';
import ModuleEditor from '../components/ModuleEditor';

const emptyPerson = {
  title: '',
  slug: '',
  full_name: '',
  status: 'draft',
  photo: null,
  bio: {
    birth_date: '',
    death_date: '',
    birth_place: '',
    current_city: '',
    occupation: [],
    achievements: []
  },
  social_links: {
    vk: '',
    telegram: '',
    youtube: '',
    instagram: '',
    website: ''
  },
  modules: [],
  tags: [],
  seo: {
    meta_title: '',
    meta_description: '',
    keywords: []
  }
};

export default function PersonEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';

  const [person, setPerson] = useState(emptyPerson);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [tagInput, setTagInput] = useState('');
  const [occupationInput, setOccupationInput] = useState('');
  const [achievementInput, setAchievementInput] = useState('');

  useEffect(() => {
    if (!isNew) {
      const fetchPerson = async () => {
        try {
          const response = await contentApi.getPerson(id);
          setPerson({
            ...emptyPerson,
            ...response.data,
            bio: { ...emptyPerson.bio, ...response.data.bio },
            social_links: { ...emptyPerson.social_links, ...response.data.social_links },
            seo: { ...emptyPerson.seo, ...response.data.seo }
          });
        } catch (err) {
          setError('Ошибка загрузки данных');
        } finally {
          setLoading(false);
        }
      };
      fetchPerson();
    }
  }, [id, isNew]);

  const generateSlug = (title) => {
    const translitMap = {
      'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
      'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
      'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
      'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
      'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    };
    return title.toLowerCase()
      .split('')
      .map(char => translitMap[char] || char)
      .join('')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
  };

  const handleTitleChange = (e) => {
    const title = e.target.value;
    setPerson(prev => ({
      ...prev,
      title,
      full_name: prev.full_name || title,
      slug: prev.slug || generateSlug(title)
    }));
  };

  const handleSave = async () => {
    setError('');
    setSuccess('');
    setSaving(true);

    try {
      if (isNew) {
        const response = await contentApi.createPerson(person);
        setSuccess('Создано!');
        navigate(`/admin/people/${response.data.id}`, { replace: true });
      } else {
        await contentApi.updatePerson(id, person);
        setSuccess('Сохранено!');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const addTag = () => {
    if (tagInput.trim() && !person.tags.includes(tagInput.trim())) {
      setPerson(prev => ({
        ...prev,
        tags: [...prev.tags, tagInput.trim()]
      }));
      setTagInput('');
    }
  };

  const removeTag = (tag) => {
    setPerson(prev => ({
      ...prev,
      tags: prev.tags.filter(t => t !== tag)
    }));
  };

  const addOccupation = () => {
    if (occupationInput.trim() && !person.bio.occupation.includes(occupationInput.trim())) {
      setPerson(prev => ({
        ...prev,
        bio: {
          ...prev.bio,
          occupation: [...prev.bio.occupation, occupationInput.trim()]
        }
      }));
      setOccupationInput('');
    }
  };

  const addAchievement = () => {
    if (achievementInput.trim() && !person.bio.achievements.includes(achievementInput.trim())) {
      setPerson(prev => ({
        ...prev,
        bio: {
          ...prev.bio,
          achievements: [...prev.bio.achievements, achievementInput.trim()]
        }
      }));
      setAchievementInput('');
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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/admin/people')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">
              {isNew ? 'Новый человек' : person.title || 'Редактирование'}
            </h1>
            {!isNew && (
              <p className="text-sm text-muted-foreground">/{person.slug}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select 
            value={person.status} 
            onValueChange={(v) => setPerson(prev => ({ ...prev, status: v }))}
          >
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="draft">Черновик</SelectItem>
              <SelectItem value="published">Опубликовать</SelectItem>
              <SelectItem value="archived">В архив</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={handleSave} disabled={saving} data-testid="save-btn">
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
          <TabsTrigger value="bio">Биография</TabsTrigger>
          <TabsTrigger value="modules">Модули ({person.modules.length})</TabsTrigger>
          <TabsTrigger value="seo">SEO</TabsTrigger>
        </TabsList>

        {/* Main tab */}
        <TabsContent value="main" className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Основная информация</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Заголовок страницы</Label>
                  <Input
                    value={person.title}
                    onChange={handleTitleChange}
                    placeholder="Александр Масляков"
                    data-testid="title-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Полное имя</Label>
                  <Input
                    value={person.full_name}
                    onChange={(e) => setPerson(prev => ({ ...prev, full_name: e.target.value }))}
                    placeholder="Александр Васильевич Масляков"
                  />
                </div>

                <div className="space-y-2">
                  <Label>URL (slug)</Label>
                  <Input
                    value={person.slug}
                    onChange={(e) => setPerson(prev => ({ ...prev, slug: e.target.value }))}
                    placeholder="alexander-maslyakov"
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Теги</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Input
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
                    placeholder="Добавить тег..."
                  />
                  <Button type="button" variant="outline" onClick={addTag}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {person.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="pr-1">
                      {tag}
                      <button
                        type="button"
                        onClick={() => removeTag(tag)}
                        className="ml-1 hover:text-destructive"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Социальные сети</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries({
                  vk: 'ВКонтакте',
                  telegram: 'Telegram',
                  youtube: 'YouTube',
                  instagram: 'Instagram',
                  website: 'Сайт'
                }).map(([key, label]) => (
                  <div key={key} className="space-y-2">
                    <Label>{label}</Label>
                    <Input
                      value={person.social_links[key] || ''}
                      onChange={(e) => setPerson(prev => ({
                        ...prev,
                        social_links: { ...prev.social_links, [key]: e.target.value }
                      }))}
                      placeholder={`https://...`}
                    />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Bio tab */}
        <TabsContent value="bio" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Биографические данные</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Дата рождения</Label>
                  <Input
                    type="date"
                    value={person.bio.birth_date || ''}
                    onChange={(e) => setPerson(prev => ({
                      ...prev,
                      bio: { ...prev.bio, birth_date: e.target.value }
                    }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Дата смерти</Label>
                  <Input
                    type="date"
                    value={person.bio.death_date || ''}
                    onChange={(e) => setPerson(prev => ({
                      ...prev,
                      bio: { ...prev.bio, death_date: e.target.value }
                    }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Место рождения</Label>
                  <Input
                    value={person.bio.birth_place || ''}
                    onChange={(e) => setPerson(prev => ({
                      ...prev,
                      bio: { ...prev.bio, birth_place: e.target.value }
                    }))}
                    placeholder="Свердловск"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Текущий город</Label>
                  <Input
                    value={person.bio.current_city || ''}
                    onChange={(e) => setPerson(prev => ({
                      ...prev,
                      bio: { ...prev.bio, current_city: e.target.value }
                    }))}
                    placeholder="Москва"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Род деятельности</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Input
                    value={occupationInput}
                    onChange={(e) => setOccupationInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addOccupation())}
                    placeholder="Телеведущий"
                  />
                  <Button type="button" variant="outline" onClick={addOccupation}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <div className="space-y-2">
                  {person.bio.occupation.map((item, i) => (
                    <div key={i} className="flex items-center justify-between bg-muted p-2 rounded">
                      <span>{item}</span>
                      <button
                        type="button"
                        onClick={() => setPerson(prev => ({
                          ...prev,
                          bio: {
                            ...prev.bio,
                            occupation: prev.bio.occupation.filter((_, j) => j !== i)
                          }
                        }))}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Достижения</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Input
                    value={achievementInput}
                    onChange={(e) => setAchievementInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addAchievement())}
                    placeholder="Народный артист России"
                  />
                  <Button type="button" variant="outline" onClick={addAchievement}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <div className="space-y-2">
                  {person.bio.achievements.map((item, i) => (
                    <div key={i} className="flex items-center justify-between bg-muted p-2 rounded">
                      <span>{item}</span>
                      <button
                        type="button"
                        onClick={() => setPerson(prev => ({
                          ...prev,
                          bio: {
                            ...prev.bio,
                            achievements: prev.bio.achievements.filter((_, j) => j !== i)
                          }
                        }))}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Modules tab */}
        <TabsContent value="modules">
          <ModuleEditor
            modules={person.modules}
            onChange={(modules) => setPerson(prev => ({ ...prev, modules }))}
            contentType="person"
          />
        </TabsContent>

        {/* SEO tab */}
        <TabsContent value="seo">
          <Card>
            <CardHeader>
              <CardTitle>SEO настройки</CardTitle>
              <CardDescription>Мета-теги для поисковых систем</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Meta Title</Label>
                <Input
                  value={person.seo.meta_title || ''}
                  onChange={(e) => setPerson(prev => ({
                    ...prev,
                    seo: { ...prev.seo, meta_title: e.target.value }
                  }))}
                  placeholder="Заголовок для поисковиков"
                />
              </div>
              <div className="space-y-2">
                <Label>Meta Description</Label>
                <Textarea
                  value={person.seo.meta_description || ''}
                  onChange={(e) => setPerson(prev => ({
                    ...prev,
                    seo: { ...prev.seo, meta_description: e.target.value }
                  }))}
                  placeholder="Описание для поисковиков (150-160 символов)"
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
