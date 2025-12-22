import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { contentApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select, SelectContent, SelectItem, 
  SelectTrigger, SelectValue
} from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Save, ArrowLeft, Loader2, Plus, X, ExternalLink } from 'lucide-react';
import ModuleEditor from '../components/ModuleEditor';
import TagSelector from '../components/TagSelector';

const emptyTeam = {
  title: '',
  slug: '',
  name: '',
  team_type: 'kvn',
  status: 'draft',
  logo: null,
  facts: {
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
  const [tagInput, setTagInput] = useState('');
  const [achievementInput, setAchievementInput] = useState('');

  useEffect(() => {
    if (!isNew) {
      const fetchTeam = async () => {
        try {
          const response = await contentApi.getTeam(id);
          setTeam({
            ...emptyTeam,
            ...response.data,
            facts: { ...emptyTeam.facts, ...response.data.facts },
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
      if (isNew) {
        const response = await contentApi.createTeam(team);
        setSuccess('Создано!');
        navigate(`/admin/teams/${response.data.id}`, { replace: true });
      } else {
        await contentApi.updateTeam(id, team);
        setSuccess('Сохранено!');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const addTag = () => {
    if (tagInput.trim() && !team.tags.includes(tagInput.trim())) {
      setTeam(prev => ({ ...prev, tags: [...prev.tags, tagInput.trim()] }));
      setTagInput('');
    }
  };

  const addAchievement = () => {
    if (achievementInput.trim() && !team.facts.achievements.includes(achievementInput.trim())) {
      setTeam(prev => ({
        ...prev,
        facts: {
          ...prev.facts,
          achievements: [...prev.facts.achievements, achievementInput.trim()]
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
              onClick={() => window.open(`/teams/${team.team_type || 'kvn'}/${team.slug}`, '_blank')}
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
              <CardTitle>Факты о команде</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Год основания</Label>
                  <Input
                    type="number"
                    value={team.facts.founded_year || ''}
                    onChange={(e) => setTeam(prev => ({
                      ...prev,
                      facts: { ...prev.facts, founded_year: parseInt(e.target.value) || null }
                    }))}
                    placeholder="2010"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Год распада</Label>
                  <Input
                    type="number"
                    value={team.facts.disbanded_year || ''}
                    onChange={(e) => setTeam(prev => ({
                      ...prev,
                      facts: { ...prev.facts, disbanded_year: parseInt(e.target.value) || null }
                    }))}
                    placeholder="Оставить пустым если активна"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Капитан</Label>
                  <Input
                    value={team.facts.captain_name || ''}
                    onChange={(e) => setTeam(prev => ({
                      ...prev,
                      facts: { ...prev.facts, captain_name: e.target.value }
                    }))}
                    placeholder="Имя капитана"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Город</Label>
                  <Input
                    value={team.facts.city || ''}
                    onChange={(e) => setTeam(prev => ({
                      ...prev,
                      facts: { ...prev.facts, city: e.target.value }
                    }))}
                    placeholder="Пятигорск"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Статус</Label>
                  <Select 
                    value={team.facts.status} 
                    onValueChange={(v) => setTeam(prev => ({ ...prev, facts: { ...prev.facts, status: v } }))}
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
                {team.facts.achievements.map((item, i) => (
                  <div key={i} className="flex items-center justify-between bg-muted p-2 rounded">
                    <span>{item}</span>
                    <button
                      type="button"
                      onClick={() => setTeam(prev => ({
                        ...prev,
                        facts: {
                          ...prev.facts,
                          achievements: prev.facts.achievements.filter((_, j) => j !== i)
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
