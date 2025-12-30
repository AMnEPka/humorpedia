import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { contentApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select, SelectContent, SelectItem, 
  SelectTrigger, SelectValue
} from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Save, ArrowLeft, Loader2, Plus, X, ExternalLink } from 'lucide-react';
import ModuleEditor from '../components/ModuleEditor';
import TagSelector from '../components/TagSelector';
import MediaSelector from '../components/MediaSelector';

const emptyTeam = {
  title: '',
  slug: '',
  name: '',
  team_type: 'kvn',
  status: 'draft',
  logo: null,
  facts: {},  // Гибкая таблица фактов (ключ-значение)
  structured_facts: {
    founded_year: null,
    disbanded_year: null,
    captain_name: '',
    city: '',
    status: 'active',
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

export default function TeamEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';

  const [team, setTeam] = useState(emptyTeam);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [achievementInput, setAchievementInput] = useState('');
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

  useEffect(() => {
    if (!isNew) {
      const fetchTeam = async () => {
        try {
          const response = await contentApi.getTeam(id);
          // Преобразуем logo из строки в объект MediaFile, если нужно
          // Также проверяем альтернативные поля: image, cover_image, poster
          let logo = response.data.logo || response.data.image || response.data.cover_image?.url || response.data.cover_image || response.data.poster;
          
          // Проверяем, есть ли реальный логотип
          const hasValidLogo = logo && (
            (typeof logo === 'string' && logo.trim() !== '') ||
            (typeof logo === 'object' && logo !== null && 
             ((logo.url && logo.url.trim() !== '') || (logo.thumbnail && logo.thumbnail.trim() !== '')))
          );
          
          if (hasValidLogo) {
            if (typeof logo === 'string') {
              // Добавляем / в начало если путь не абсолютный
              const logoUrl = logo.startsWith('/') || logo.startsWith('http') ? logo : `/${logo}`;
              logo = {
                url: logoUrl,
                alt: '',
                caption: '',
                thumbnail: logoUrl
              };
            } else if (typeof logo === 'object' && logo !== null) {
              // Если logo уже объект, нормализуем структуру
              let logoUrl = (logo.url && logo.url.trim() !== '') ? logo.url : 
                            (logo.thumbnail && logo.thumbnail.trim() !== '') ? logo.thumbnail : '';
              // Добавляем / в начало если путь не абсолютный
              if (logoUrl && !logoUrl.startsWith('/') && !logoUrl.startsWith('http')) {
                logoUrl = `/${logoUrl}`;
              }
              let logoThumbnail = (logo.thumbnail && logo.thumbnail.trim() !== '') ? logo.thumbnail : 
                                  (logo.url && logo.url.trim() !== '') ? logo.url : '';
              if (logoThumbnail && !logoThumbnail.startsWith('/') && !logoThumbnail.startsWith('http')) {
                logoThumbnail = `/${logoThumbnail}`;
              }
              
              // Если есть хотя бы один валидный URL, создаём нормализованный объект
              if (logoUrl) {
                logo = {
                  url: logoUrl,
                  alt: logo.alt || '',
                  caption: logo.caption || '',
                  thumbnail: logoThumbnail
                };
              } else {
                // Если нет валидного URL, считаем что логотипа нет
                logo = getRandomPattern();
              }
            }
          } else {
            // Если логотипа нет или пустой, устанавливаем случайный паттерн
            logo = getRandomPattern();
          }
          
          // Разбираем facts - отделяем структурированные данные от произвольных
          const loadedFacts = response.data.facts || {};
          const structuredFields = ['founded_year', 'disbanded_year', 'captain_name', 'city', 'status', 'achievements'];
          
          // Структурированные факты (из старого формата)
          const structuredFacts = {
            founded_year: loadedFacts.founded_year || null,
            disbanded_year: loadedFacts.disbanded_year || null,
            captain_name: loadedFacts.captain_name || '',
            city: loadedFacts.city || '',
            status: loadedFacts.status || 'active',
            achievements: loadedFacts.achievements || []
          };
          
          // Произвольные факты (ключ-значение) - все остальные поля
          const customFacts = {};
          Object.entries(loadedFacts).forEach(([key, value]) => {
            if (!structuredFields.includes(key) && typeof value === 'string') {
              customFacts[key] = value;
            }
          });
          
          setTeam({
            ...emptyTeam,
            ...response.data,
            logo: logo,
            facts: customFacts,
            structured_facts: structuredFacts,
            social_links: { ...emptyTeam.social_links, ...response.data.social_links },
            seo: { ...emptyTeam.seo, ...response.data.seo }
          });
        } catch (err) {
          setError('Ошибка загрузки данных');
        } finally {
          setLoading(false);
        }
      };
      fetchTeam();
    } else {
      // Для новой страницы устанавливаем случайный паттерн
      setTeam({
        ...emptyTeam,
        logo: getRandomPattern()
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

  const handleNameChange = (e) => {
    const name = e.target.value;
    setTeam(prev => ({
      ...prev,
      name,
      title: prev.title || name,
      slug: prev.slug || generateSlug(name)
    }));
  };

  const handleSave = async () => {
    setError('');
    setSuccess('');
    setSaving(true);

    try {
      // Объединяем структурированные и произвольные факты перед сохранением
      const combinedFacts = {
        ...team.structured_facts,
        ...team.facts
      };
      
      const teamToSave = {
        ...team,
        facts: combinedFacts
      };
      // Удаляем временное поле structured_facts
      delete teamToSave.structured_facts;
      
      if (isNew) {
        const response = await contentApi.createTeam(teamToSave);
        setSuccess('Создано!');
        navigate(`/admin/teams/${response.data.id}`, { replace: true });
      } else {
        await contentApi.updateTeam(id, teamToSave);
        setSuccess('Сохранено!');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const addAchievement = () => {
    const achievements = team.structured_facts?.achievements || [];
    if (achievementInput.trim() && !achievements.includes(achievementInput.trim())) {
      setTeam(prev => ({
        ...prev,
        structured_facts: {
          ...prev.structured_facts,
          achievements: [...(prev.structured_facts?.achievements || []), achievementInput.trim()]
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
          <Button variant="ghost" size="icon" onClick={() => navigate('/admin/teams')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">
              {isNew ? 'Новая команда' : team.name || 'Редактирование'}
            </h1>
            {!isNew && <p className="text-sm text-muted-foreground">/{team.slug}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isNew && team.slug && (
            <Button 
              variant="outline" 
              onClick={() => window.open(`/kvn/teams/${team.slug}`, '_blank')}
            >
              <ExternalLink className="mr-2 h-4 w-4" />
              Предпросмотр
            </Button>
          )}
          <Select 
            value={team.status} 
            onValueChange={(v) => setTeam(prev => ({ ...prev, status: v }))}
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

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {success && <Alert><AlertDescription>{success}</AlertDescription></Alert>}

      <Tabs defaultValue="main" className="space-y-6">
        <TabsList>
          <TabsTrigger value="main">Основное</TabsTrigger>
          <TabsTrigger value="facts">Факты</TabsTrigger>
          <TabsTrigger value="modules">Модули ({team.modules.length})</TabsTrigger>
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
                  <Label>Название команды</Label>
                  <Input
                    value={team.name}
                    onChange={handleNameChange}
                    placeholder="Сборная Пятигорска"
                    data-testid="name-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Заголовок страницы</Label>
                  <Input
                    value={team.title}
                    onChange={(e) => setTeam(prev => ({ ...prev, title: e.target.value }))}
                    placeholder="Сборная Пятигорска - команда КВН"
                  />
                </div>
                <div className="space-y-2">
                  <Label>URL (slug)</Label>
                  <Input
                    value={team.slug}
                    onChange={(e) => setTeam(prev => ({ ...prev, slug: e.target.value }))}
                    placeholder="sbornaya-pyatigorska"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Тип команды</Label>
                  <Select 
                    value={team.team_type} 
                    onValueChange={(v) => setTeam(prev => ({ ...prev, team_type: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="kvn">КВН</SelectItem>
                      <SelectItem value="liga_smeha">Лига Смеха</SelectItem>
                      <SelectItem value="improv">Импровизация</SelectItem>
                      <SelectItem value="comedy_club">Comedy Club</SelectItem>
                      <SelectItem value="other">Другое</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <MediaSelector
                  value={team.logo}
                  onChange={(logo) => setTeam(prev => ({ ...prev, logo }))}
                  label="Логотип команды"
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Теги</CardTitle>
              </CardHeader>
              <CardContent>
                <TagSelector
                  value={team.tags}
                  onChange={(tags) => setTeam(prev => ({ ...prev, tags }))}
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
                {Object.entries({ vk: 'ВКонтакте', telegram: 'Telegram', youtube: 'YouTube', instagram: 'Instagram', website: 'Сайт' }).map(([key, label]) => (
                  <div key={key} className="space-y-2">
                    <Label>{label}</Label>
                    <Input
                      value={team.social_links[key] || ''}
                      onChange={(e) => setTeam(prev => ({
                        ...prev,
                        social_links: { ...prev.social_links, [key]: e.target.value }
                      }))}
                      placeholder="https://..."
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
              <CardTitle>Основные данные о команде</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Год основания</Label>
                  <Input
                    type="number"
                    value={team.structured_facts?.founded_year || ''}
                    onChange={(e) => setTeam(prev => ({
                      ...prev,
                      structured_facts: { ...prev.structured_facts, founded_year: parseInt(e.target.value) || null }
                    }))}
                    placeholder="2010"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Год распада</Label>
                  <Input
                    type="number"
                    value={team.structured_facts?.disbanded_year || ''}
                    onChange={(e) => setTeam(prev => ({
                      ...prev,
                      structured_facts: { ...prev.structured_facts, disbanded_year: parseInt(e.target.value) || null }
                    }))}
                    placeholder="Оставить пустым если активна"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Капитан</Label>
                  <Input
                    value={team.structured_facts?.captain_name || ''}
                    onChange={(e) => setTeam(prev => ({
                      ...prev,
                      structured_facts: { ...prev.structured_facts, captain_name: e.target.value }
                    }))}
                    placeholder="Имя капитана"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Город</Label>
                  <Input
                    value={team.structured_facts?.city || ''}
                    onChange={(e) => setTeam(prev => ({
                      ...prev,
                      structured_facts: { ...prev.structured_facts, city: e.target.value }
                    }))}
                    placeholder="Пятигорск"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Статус</Label>
                  <Select 
                    value={team.structured_facts?.status || 'active'} 
                    onValueChange={(v) => setTeam(prev => ({ ...prev, structured_facts: { ...prev.structured_facts, status: v } }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">Активна</SelectItem>
                      <SelectItem value="disbanded">Расформирована</SelectItem>
                      <SelectItem value="reformed">Переформирована</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
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
                  placeholder="Чемпионы Высшей лиги 2024"
                />
                <Button type="button" variant="outline" onClick={addAchievement}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="space-y-2">
                {(team.structured_facts?.achievements || []).map((item, i) => (
                  <div key={i} className="flex items-center justify-between bg-muted p-2 rounded">
                    <span>{item}</span>
                    <button
                      type="button"
                      onClick={() => setTeam(prev => ({
                        ...prev,
                        structured_facts: {
                          ...prev.structured_facts,
                          achievements: prev.structured_facts.achievements.filter((_, j) => j !== i)
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
              <CardTitle>Таблица фактов</CardTitle>
              <CardDescription>
                Дополнительные факты о команде, которые отображаются в модуле facts_table
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Существующие факты */}
              {Object.entries(team.facts || {}).length > 0 ? (
                <div className="space-y-2">
                  {Object.entries(team.facts).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2 p-2 bg-muted rounded">
                      <Input 
                        value={key} 
                        className="w-1/3 bg-background"
                        onChange={(e) => {
                          const newFacts = { ...team.facts };
                          delete newFacts[key];
                          newFacts[e.target.value] = value;
                          setTeam(prev => ({ ...prev, facts: newFacts }));
                        }}
                      />
                      <Input 
                        value={value} 
                        className="flex-1 bg-background"
                        onChange={(e) => setTeam(prev => ({ 
                          ...prev, 
                          facts: { ...prev.facts, [key]: e.target.value } 
                        }))}
                      />
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => {
                          const newFacts = { ...team.facts };
                          delete newFacts[key];
                          setTeam(prev => ({ ...prev, facts: newFacts }));
                        }}
                      >
                        <X className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">Нет дополнительных фактов</p>
              )}
              
              {/* Добавить новый факт */}
              <div className="flex items-center gap-2 pt-4 border-t">
                <Input
                  value={newFactKey}
                  onChange={(e) => setNewFactKey(e.target.value)}
                  placeholder="Название (напр. Лига)"
                  className="w-1/3"
                />
                <Input
                  value={newFactValue}
                  onChange={(e) => setNewFactValue(e.target.value)}
                  placeholder="Значение"
                  className="flex-1"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && newFactKey.trim() && newFactValue.trim()) {
                      setTeam(prev => ({
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
                      setTeam(prev => ({
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
        </TabsContent>

        {/* Modules tab */}
        <TabsContent value="modules">
          <ModuleEditor
            modules={team.modules}
            onChange={(modules) => setTeam(prev => ({ ...prev, modules }))}
            contentType="team"
          />
        </TabsContent>

        {/* SEO tab */}
        <TabsContent value="seo">
          <Card>
            <CardHeader>
              <CardTitle>SEO настройки</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Meta Title</Label>
                <Input
                  value={team.seo.meta_title || ''}
                  onChange={(e) => setTeam(prev => ({ ...prev, seo: { ...prev.seo, meta_title: e.target.value } }))}
                  placeholder="Заголовок для поисковиков"
                />
              </div>
              <div className="space-y-2">
                <Label>Meta Description</Label>
                <Input
                  value={team.seo.meta_description || ''}
                  onChange={(e) => setTeam(prev => ({ ...prev, seo: { ...prev.seo, meta_description: e.target.value } }))}
                  placeholder="Описание для поисковиков"
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
