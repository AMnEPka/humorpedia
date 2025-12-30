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
  const [occupationInput, setOccupationInput] = useState('');
  const [achievementInput, setAchievementInput] = useState('');
  const [newFactKey, setNewFactKey] = useState('');
  const [newFactValue, setNewFactValue] = useState('');

  // Функция для расчёта возраста
  const calculateAge = (birthDate, endDate = null) => {
    if (!birthDate) return null;
    try {
      const birth = new Date(birthDate);
      if (isNaN(birth.getTime())) return null;
      const end = endDate ? new Date(endDate) : new Date();
      if (endDate && isNaN(end.getTime())) return null;
      let age = end.getFullYear() - birth.getFullYear();
      const monthDiff = end.getMonth() - birth.getMonth();
      if (monthDiff < 0 || (monthDiff === 0 && end.getDate() < birth.getDate())) {
        age--;
      }
      return age >= 0 ? age : null;
    } catch (e) {
      console.warn('Ошибка при расчете возраста:', e);
      return null;
    }
  };
  
  // Функция для форматирования даты в читаемый формат "9 декабря 1988 года"
  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return '';
      const months = [
        'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
      ];
      return `${date.getDate()} ${months[date.getMonth()]} ${date.getFullYear()} года`;
    } catch (e) {
      return '';
    }
  };

  // Функция для удаления возраста из текста даты (если он есть)
  // Используется для очистки фактов от возраста перед сохранением
  const removeAgeFromDate = (dateText) => {
    if (!dateText) return dateText;
    return dateText.replace(/\s*\(\d+\s+лет\)\s*$/, '').trim();
  };

  // Функция для синхронизации facts с полями биографии (БЕЗ добавления возраста)
  // Возраст добавляется только на фронтенде при отображении
  // ВАЖНО: Не удаляет факты, добавленные вручную, если их нет в bio
  const syncFactsWithBio = (facts, bio, fullName) => {
    const syncedFacts = { ...facts };
    
    // Полное имя - обновляем только если есть значение
    if (fullName) {
      syncedFacts['Полное имя'] = fullName;
    }
    // НЕ удаляем "Полное имя", если его нет в fullName - возможно оно было добавлено вручную
    
    // Дата рождения - обновляем только если есть birth_date, БЕЗ возраста
    if (bio?.birth_date) {
      try {
        const formattedBirthDate = formatDate(bio.birth_date);
        if (formattedBirthDate) {
          // Убираем возраст, если он был добавлен ранее
          syncedFacts['Дата рождения'] = removeAgeFromDate(formattedBirthDate);
        }
      } catch (e) {
        console.warn('Ошибка при форматировании даты рождения:', e);
      }
    }
    // НЕ удаляем "Дата рождения", если birth_date пустое - возможно она была добавлена вручную
    
    // Дата смерти - обновляем только если есть death_date в bio, БЕЗ возраста
    if (bio?.death_date) {
      try {
        const formattedDeathDate = formatDate(bio.death_date);
        if (formattedDeathDate) {
          syncedFacts['Дата смерти'] = removeAgeFromDate(formattedDeathDate);
        }
      } catch (e) {
        console.warn('Ошибка при форматировании даты смерти:', e);
      }
    }
    // НЕ удаляем "Дата смерти", если death_date пустое - возможно она была добавлена вручную
    
    // Место рождения - обновляем только если есть значение
    if (bio?.birth_place) {
      syncedFacts['Место рождения'] = bio.birth_place;
    }
    // НЕ удаляем "Место рождения", если его нет в bio - возможно оно было добавлено вручную
    
    return syncedFacts;
  };

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
          
          // Синхронизируем facts с полями биографии при загрузке
          // ВАЖНО: syncFactsWithBio не удаляет факты, добавленные вручную
          const loadedFacts = response.data.facts || {};
          const syncedFacts = syncFactsWithBio(loadedFacts, response.data.bio, response.data.full_name);
          
          setPerson({
            ...emptyPerson,
            ...response.data,
            photo: photo,
            bio: { ...emptyPerson.bio, ...response.data.bio },
            facts: syncedFacts,
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
      slug: prev.slug || generateSlug(title)
    }));
  };

  const handleSave = async () => {
    setError('');
    setSuccess('');
    setSaving(true);

    try {
      // Синхронизируем facts с полями биографии перед сохранением
      // ВАЖНО: syncFactsWithBio не удаляет факты, добавленные вручную
      const factsToSave = syncFactsWithBio(person.facts, person.bio, person.full_name);
      
      // Убеждаемся, что все факты сохранены (включая добавленные вручную)
      const personToSave = {
        ...person,
        facts: factsToSave
      };

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
          
          // Синхронизируем facts с полями биографии при перезагрузке
          // ВАЖНО: syncFactsWithBio не удаляет факты, добавленные вручную
          const loadedFacts = response.data.facts || {};
          const syncedFacts = syncFactsWithBio(loadedFacts, response.data.bio, response.data.full_name);
          
          // Убеждаемся, что все факты сохранены (включая добавленные вручную)
          setPerson(prev => ({
            ...prev,
            ...response.data,
            photo: photo,
            bio: { ...emptyPerson.bio, ...response.data.bio },
            facts: syncedFacts, // Все факты должны быть сохранены
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
              </CardHeader>
              <CardContent>
                <TagSelector
                  value={person.tags}
                  onChange={(tags) => setPerson(prev => ({ ...prev, tags }))}
                  placeholder="Выберите или добавьте тег..."
                />
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
              <CardDescription>
                Эти данные автоматически синхронизируются с таблицей фактов (модуль facts_table)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Полное имя</Label>
                  <Input
                    value={person.full_name || ''}
                    onChange={(e) => {
                      const newFullName = e.target.value;
                      const updatedFacts = syncFactsWithBio(person.facts, person.bio, newFullName);
                      setPerson(prev => ({
                        ...prev,
                        full_name: newFullName,
                        facts: updatedFacts
                      }));
                    }}
                    placeholder="Александр Васильевич Масляков"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Дата рождения</Label>
                  <Input
                    type="date"
                    value={person.bio.birth_date || ''}
                    onChange={(e) => {
                      const newBirthDate = e.target.value;
                      const updatedBio = { ...person.bio, birth_date: newBirthDate };
                      const updatedFacts = syncFactsWithBio(person.facts, updatedBio, person.full_name);
                      setPerson(prev => ({
                        ...prev,
                        bio: updatedBio,
                        facts: updatedFacts
                      }));
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Место рождения</Label>
                  <Input
                    value={person.bio.birth_place || ''}
                    onChange={(e) => {
                      const newBirthPlace = e.target.value;
                      const updatedBio = { ...person.bio, birth_place: newBirthPlace };
                      const updatedFacts = syncFactsWithBio(person.facts, updatedBio, person.full_name);
                      setPerson(prev => ({
                        ...prev,
                        bio: updatedBio,
                        facts: updatedFacts
                      }));
                    }}
                    placeholder="Свердловск"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Дата смерти</Label>
                  <Input
                    type="date"
                    value={person.bio.death_date || ''}
                    onChange={(e) => {
                      const newDeathDate = e.target.value;
                      const updatedBio = { ...person.bio, death_date: newDeathDate };
                      const updatedFacts = syncFactsWithBio(person.facts, updatedBio, person.full_name);
                      setPerson(prev => ({
                        ...prev,
                        bio: updatedBio,
                        facts: updatedFacts
                      }));
                    }}
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

          <Card>
            <CardHeader>
              <CardTitle>Таблица фактов</CardTitle>
              <CardDescription>
                Дополнительные факты, которые отображаются в модуле facts_table
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Существующие факты */}
              {Object.entries(person.facts || {}).length > 0 ? (
                <div className="space-y-2">
                  {Object.entries(person.facts).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2 p-2 bg-muted rounded">
                      <Input 
                        value={key} 
                        className="w-1/3 bg-background"
                        onChange={(e) => {
                          const newFacts = { ...person.facts };
                          delete newFacts[key];
                          newFacts[e.target.value] = value;
                          setPerson(prev => ({ ...prev, facts: newFacts }));
                        }}
                      />
                      <Input 
                        value={value} 
                        className="flex-1 bg-background"
                        onChange={(e) => setPerson(prev => ({ 
                          ...prev, 
                          facts: { ...prev.facts, [key]: e.target.value } 
                        }))}
                      />
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => {
                          const newFacts = { ...person.facts };
                          delete newFacts[key];
                          setPerson(prev => ({ ...prev, facts: newFacts }));
                        }}
                      >
                        <X className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">Нет фактов</p>
              )}
              
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
                      setPerson(prev => ({
                        ...prev,
                        facts: { ...prev.facts, [newFactKey.trim()]: newFactValue.trim() }
                      }));
                      setNewFactKey('');
                      setNewFactValue('');
                    }
                  }}
                />
                <Button 
                  variant="outline"
                  onClick={() => {
                    if (newFactKey.trim() && newFactValue.trim()) {
                      setPerson(prev => ({
                        ...prev,
                        facts: { ...prev.facts, [newFactKey.trim()]: newFactValue.trim() }
                      }));
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
