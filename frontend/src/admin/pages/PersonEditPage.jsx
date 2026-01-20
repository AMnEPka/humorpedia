import { useState, useEffect, useCallback, useMemo } from 'react';
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
  Image as ImageIcon, Trash2, ExternalLink
} from 'lucide-react';
import ModuleEditor from '../components/ModuleEditor';
import TagSelector from '../components/TagSelector';
import MediaSelector from '../components/MediaSelector';
import FactsEditor from '../components/FactsEditor';

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
  facts: {},  // Facts for facts_table module
  facts_order: [],
  primary_tag: null,  // Базовый тег человека
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
  const [newFactKey, setNewFactKey] = useState('');
  const [newFactValue, setNewFactValue] = useState('');


  // Функция для получения случайного паттерна
  const getRandomPattern = () => {
    const patterns = [
      '/media/imported/images/pattern-1.jpeg',
      '/media/imported/images/pattern-2.jpeg',
      '/media/imported/images/pattern-3.jpeg'
    ];
    const randomIndex = Math.floor(Math.random() * patterns.length);
    return {
      url: patterns[randomIndex],
      alt: '',
      caption: '',
      thumbnail: patterns[randomIndex]
    };
  };

  // Функция для преобразования "Фамилия Имя" в "Имя Фамилия"
  const swapNameOrder = (name) => {
    if (!name) return name;
    const parts = name.trim().split(/\s+/);
    if (parts.length === 2) {
      // Если две части, меняем местами: "Фамилия Имя" -> "Имя Фамилия"
      return `${parts[1]} ${parts[0]}`;
    }
    // Если одна часть или больше двух, возвращаем как есть
    return name;
  };

  useEffect(() => {
    if (!isNew) {
      const fetchPerson = async () => {
        try {
          const response = await contentApi.getPerson(id);
          // Преобразуем photo из строки в объект MediaFile, если нужно
          // Также проверяем альтернативные поля: image, cover_image, poster
          let photo = response.data.photo || response.data.image || response.data.cover_image?.url || response.data.cover_image || response.data.poster;
          
          // Проверяем, есть ли реальное фото
          const hasValidPhoto = photo && (
            (typeof photo === 'string' && photo.trim() !== '') ||
            (typeof photo === 'object' && photo !== null && 
             ((photo.url && photo.url.trim() !== '') || (photo.thumbnail && photo.thumbnail.trim() !== '')))
          );
          
          if (hasValidPhoto) {
            if (typeof photo === 'string') {
              // Добавляем / в начало если путь не абсолютный
              const photoUrl = photo.startsWith('/') || photo.startsWith('http') ? photo : `/${photo}`;
              photo = {
                url: photoUrl,
                alt: '',
                caption: '',
                thumbnail: photoUrl
              };
            } else if (typeof photo === 'object' && photo !== null) {
              // Если photo уже объект, нормализуем структуру
              let photoUrl = (photo.url && photo.url.trim() !== '') ? photo.url : 
                               (photo.thumbnail && photo.thumbnail.trim() !== '') ? photo.thumbnail : '';
              // Добавляем / в начало если путь не абсолютный
              if (photoUrl && !photoUrl.startsWith('/') && !photoUrl.startsWith('http')) {
                photoUrl = `/${photoUrl}`;
              }
              let photoThumbnail = (photo.thumbnail && photo.thumbnail.trim() !== '') ? photo.thumbnail : 
                                     (photo.url && photo.url.trim() !== '') ? photo.url : '';
              if (photoThumbnail && !photoThumbnail.startsWith('/') && !photoThumbnail.startsWith('http')) {
                photoThumbnail = `/${photoThumbnail}`;
              }
              
              // Если есть хотя бы один валидный URL, создаём нормализованный объект
              if (photoUrl) {
                photo = {
                  url: photoUrl,
                  alt: photo.alt || '',
                  caption: photo.caption || '',
                  thumbnail: photoThumbnail
                };
              } else {
                // Если нет валидного URL, считаем что фото нет
                photo = getRandomPattern();
              }
            }
          } else {
            // Если фото нет или пустое, устанавливаем случайный паттерн
            photo = getRandomPattern();
          }
          
          // Загружаем facts напрямую, фильтруя только валидные значения
          const loadedFacts = response.data.facts || {};
          const validFacts = {};
          for (const [key, value] of Object.entries(loadedFacts)) {
            if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
              validFacts[key] = String(value);
            }
          }
          
          // Устанавливаем primary_tag по умолчанию в формате "Имя Фамилия"
          const primaryTag = response.data.primary_tag || swapNameOrder(response.data.title) || swapNameOrder(response.data.full_name) || null;
          
          setPerson({
            ...emptyPerson,
            ...response.data,
            photo: photo,
            bio: { ...emptyPerson.bio, ...response.data.bio },
            facts: validFacts,
            facts_order: response.data.facts_order || [],
            primary_tag: primaryTag,
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
    } else {
      // Для новой страницы устанавливаем случайный паттерн
      setPerson({
        ...emptyPerson,
        photo: getRandomPattern()
      });
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
      slug: prev.slug || generateSlug(title),
      // Устанавливаем primary_tag по умолчанию в формате "Имя Фамилия"
      primary_tag: prev.primary_tag === null || prev.primary_tag === undefined 
        ? swapNameOrder(title) 
        : prev.primary_tag
    }));
  };

  const handleSave = async () => {
    setError('');
    setSuccess('');
    setSaving(true);

    try {
      // Фильтруем facts перед сохранением, оставляя только валидные строковые значения
      const validFacts = {};
      for (const [key, value] of Object.entries(person.facts || {})) {
        if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
          validFacts[key] = String(value);
        }
      }
      
      // Устанавливаем primary_tag по умолчанию в формате "Имя Фамилия"
      const primaryTag = person.primary_tag || swapNameOrder(person.title) || swapNameOrder(person.full_name) || null;
      
      const personToSave = {
        ...person,
        facts: validFacts,
        primary_tag: primaryTag
      };

      // facts_order: фильтруем и дополняем по текущим ключам
      const keys = Object.keys(validFacts);
      const order = Array.isArray(person.facts_order) ? person.facts_order : [];
      const filtered = order.filter((k) => keys.includes(k));
      const rest = keys.filter((k) => !filtered.includes(k));
      personToSave.facts_order = [...filtered, ...rest];

      if (isNew) {
        const response = await contentApi.createPerson(personToSave);
        setSuccess('Создано!');
        navigate(`/admin/people/${response.data.id}`, { replace: true });
      } else {
        await contentApi.updatePerson(id, personToSave);
        setSuccess('Сохранено!');
        
        // Перезагружаем данные после сохранения, чтобы обновить состояние
        try {
          const response = await contentApi.getPerson(id);
          let photo = response.data.photo || response.data.image || response.data.cover_image?.url || response.data.cover_image || response.data.poster;
          
          const hasValidPhoto = photo && (
            (typeof photo === 'string' && photo.trim() !== '') ||
            (typeof photo === 'object' && photo !== null && 
             ((photo.url && photo.url.trim() !== '') || (photo.thumbnail && photo.thumbnail.trim() !== '')))
          );
          
          if (hasValidPhoto) {
            if (typeof photo === 'string') {
              const photoUrl = photo.startsWith('/') || photo.startsWith('http') ? photo : `/${photo}`;
              photo = {
                url: photoUrl,
                alt: '',
                caption: '',
                thumbnail: photoUrl
              };
            } else if (typeof photo === 'object' && photo !== null) {
              let photoUrl = (photo.url && photo.url.trim() !== '') ? photo.url : 
                               (photo.thumbnail && photo.thumbnail.trim() !== '') ? photo.thumbnail : '';
              if (photoUrl && !photoUrl.startsWith('/') && !photoUrl.startsWith('http')) {
                photoUrl = `/${photoUrl}`;
              }
              let photoThumbnail = (photo.thumbnail && photo.thumbnail.trim() !== '') ? photo.thumbnail : 
                                     (photo.url && photo.url.trim() !== '') ? photo.url : '';
              if (photoThumbnail && !photoThumbnail.startsWith('/') && !photoThumbnail.startsWith('http')) {
                photoThumbnail = `/${photoThumbnail}`;
              }
              
              if (photoUrl) {
                photo = {
                  url: photoUrl,
                  alt: photo.alt || '',
                  caption: photo.caption || '',
                  thumbnail: photoThumbnail
                };
              } else {
                photo = getRandomPattern();
              }
            }
          } else {
            photo = getRandomPattern();
          }
          
          // Загружаем facts напрямую, фильтруя только валидные значения
          const loadedFacts = response.data.facts || {};
          const validFacts = {};
          for (const [key, value] of Object.entries(loadedFacts)) {
            if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
              validFacts[key] = String(value);
            }
          }
          
          setPerson(prev => ({
            ...prev,
            ...response.data,
            photo: photo,
            bio: { ...emptyPerson.bio, ...response.data.bio },
            facts: validFacts,
            social_links: { ...emptyPerson.social_links, ...response.data.social_links },
            seo: { ...emptyPerson.seo, ...response.data.seo }
          }));
        } catch (reloadErr) {
          // Если перезагрузка не удалась, это не критично
          console.warn('Не удалось перезагрузить данные после сохранения:', reloadErr);
        }
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка сохранения');
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
          {!isNew && person.slug && (
            <Button 
              variant="outline" 
              onClick={() => window.open(`/people/${person.slug}`, '_blank')}
            >
              <ExternalLink className="mr-2 h-4 w-4" />
              Предпросмотр
            </Button>
          )}
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
          <TabsTrigger value="facts">Факты</TabsTrigger>
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
                  <Label>URL (slug)</Label>
                  <Input
                    value={person.slug}
                    onChange={(e) => setPerson(prev => ({ ...prev, slug: e.target.value }))}
                    placeholder="alexander-maslyakov"
                  />
                </div>

                <MediaSelector
                  value={person.photo}
                  onChange={(photo) => setPerson(prev => ({ ...prev, photo }))}
                  label="Основная фотография"
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Теги</CardTitle>
                <CardDescription>
                  Базовый тег используется при автоматическом добавлении человека в сезоны КВН
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Базовый тег</Label>
                  <Input
                    value={person.primary_tag || ''}
                    onChange={(e) => setPerson(prev => ({ ...prev, primary_tag: e.target.value || null }))}
                    placeholder={swapNameOrder(person.title) || swapNameOrder(person.full_name) || 'Имя Фамилия'}
                  />
                  <p className="text-xs text-muted-foreground">
                    По умолчанию совпадает с ФИО в формате "Имя Фамилия". Можно изменить для использования другого тега в сезонах.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Все теги</Label>
                  <TagSelector
                    value={person.tags}
                    onChange={(tags) => setPerson(prev => ({ ...prev, tags }))}
                    placeholder="Выберите или добавьте тег..."
                  />
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

        {/* Facts tab */}
        <TabsContent value="facts" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Таблица фактов</CardTitle>
              <CardDescription>
                Дополнительные факты о человеке, которые отображаются в модуле facts_table
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Существующие факты */}
              {Object.keys(person.facts || {}).length > 0 ? (
                <FactsEditor
                  facts={person.facts || {}}
                  factsOrder={person.facts_order || []}
                  onChange={({ facts, facts_order }) => setPerson(prev => ({ ...prev, facts, facts_order }))}
                />
              ) : <p className="text-muted-foreground text-sm">Нет дополнительных фактов</p>}
              
              {/* Добавить новый факт */}
              <div className="flex items-center gap-2 pt-4 border-t">
                <Input
                  value={newFactKey}
                  onChange={(e) => setNewFactKey(e.target.value)}
                  placeholder="Название (напр. Полное имя)"
                  className="w-1/3"
                />
                <Input
                  value={newFactValue}
                  onChange={(e) => setNewFactValue(e.target.value)}
                  placeholder="Значение"
                  className="flex-1"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && newFactKey.trim() && newFactValue.trim()) {
                      // Добавляем в конец: сначала копируем все существующие факты, затем добавляем новый
                      setPerson(prev => {
                        const updatedFacts = { ...prev.facts };
                        updatedFacts[newFactKey.trim()] = newFactValue.trim();
                        return {
                          ...prev,
                          facts: updatedFacts,
                          facts_order: [...(prev.facts_order || []), newFactKey.trim()]
                        };
                      });
                      setNewFactKey('');
                      setNewFactValue('');
                    }
                  }}
                />
                <Button 
                  variant="outline"
                  onClick={() => {
                    if (newFactKey.trim() && newFactValue.trim()) {
                      // Добавляем в конец: сначала копируем все существующие факты, затем добавляем новый
                      setPerson(prev => {
                        const updatedFacts = { ...prev.facts };
                        updatedFacts[newFactKey.trim()] = newFactValue.trim();
                        return {
                          ...prev,
                          facts: updatedFacts,
                          facts_order: [...(prev.facts_order || []), newFactKey.trim()]
                        };
                      });
                      setNewFactKey('');
                      setNewFactValue('');
                    }
                  }}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
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
