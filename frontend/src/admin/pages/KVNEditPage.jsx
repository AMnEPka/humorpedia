import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { contentApi, getErrorMessage } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Save, ArrowLeft, Loader2, Plus, X, ExternalLink } from 'lucide-react';
import ModuleEditor from '../components/ModuleEditor';
import TagSelector from '../components/TagSelector';
import PersonSelector from '../components/PersonSelector';
// import TeamSelector from '../components/TeamSelector'; // TODO: создать компонент
import MediaSelector from '../components/MediaSelector';
import SeasonDataEditor from '../components/SeasonDataEditor';
import FactsEditor from '../components/FactsEditor';
import { cleanTeamName } from '@/utils/team';

const emptyKvn = {
  title: '', slug: '', name: '', status: 'draft',
  poster: null, description: '',
  parent_id: null,  // Для корневой страницы - null
  facts: {},
  facts_order: [],
  social_links: {},
  modules: [], tags: [], person_ids: [], team_ids: [],
  seo: { meta_title: '', meta_description: '' },
  jury_cards: {}  // { [juryName]: { photo: {...}, text: '' } }
};

export default function KVNEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';

  const [kvn, setKvn] = useState(emptyKvn);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [newFactKey, setNewFactKey] = useState('');
  const [newFactValue, setNewFactValue] = useState('');
  const [parentOptions, setParentOptions] = useState([]);
  const [juryMembers, setJuryMembers] = useState([]);
  const [loadingJury, setLoadingJury] = useState(false);

  // Загружаем список родителей для выбора
  useEffect(() => {
    let cancelled = false;
    const loadParents = async () => {
      try {
        const response = await contentApi.listKvnHierarchy();
        if (cancelled) return;
        
        // Функция для рекурсивного обхода дерева
        const flattenTree = (nodes, result = [], level = 0) => {
          for (const node of nodes) {
            if (node.id !== id) {  // Исключаем текущую страницу
              result.push({ ...node, level });
              if (node.children && node.children.length > 0) {
                flattenTree(node.children, result, level + 1);
              }
            }
          }
          return result;
        };
        const flat = flattenTree(response.data.items || []);
        if (!cancelled) {
          setParentOptions(flat);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Error loading parents:', err);
        }
      }
    };
    loadParents();
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (!isNew) {
      let cancelled = false;
      contentApi.getKvn(id).then(res => {
        if (cancelled) return;
        
        let poster = res.data.poster;
        if (poster) {
          if (typeof poster === 'string') {
            poster = { url: poster, alt: '', caption: '', thumbnail: poster };
          }
        }
        
        if (!cancelled) {
          setKvn({ 
            ...emptyKvn, 
            ...res.data, 
            poster: poster,
            parent_id: res.data.parent_id || null,  // null для корневой страницы
            facts: res.data.facts || {},
            facts_order: res.data.facts_order || [],
            social_links: res.data.social_links || {},
            seo: { ...emptyKvn.seo, ...res.data.seo },
            season_data: res.data.season_data || null,  // Сохраняем season_data для редактирования
            jury_cards: res.data.jury_cards || {}  // Сохраняем карточки жюри
          });
        }
      }).catch(() => {
        if (!cancelled) {
          setError('Ошибка загрузки');
        }
      }).finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
      
      return () => {
        cancelled = true;
      };
    }
  }, [id, isNew]);

  // Автоматически добавляем теги с названиями команд при изменении списка команд-участников
  useEffect(() => {
    if (!kvn.season_data?.all_teams || kvn.season_data.all_teams.length === 0) return;

    const updateTagsFromTeams = async () => {
      const allTeams = kvn.season_data.all_teams || [];
      const currentTags = kvn.tags || [];
      const teamNamesToAdd = [];

      // Загружаем базовые теги команд из базы данных
      await Promise.all(
        allTeams.map(async (teamItem) => {
          let teamTag = '';
          let teamName = '';
          
          if (typeof teamItem === 'object' && teamItem !== null) {
            const teamSlug = teamItem.slug || teamItem.team_slug || teamItem.id || '';
            teamName = teamItem.name || teamItem.team_name || '';
            
            // Если есть slug, загружаем данные команды из базы данных
            if (teamSlug) {
              try {
                const res = await contentApi.getTeam(teamSlug);
                const teamData = res.data;
                // Используем primary_tag, если он задан, иначе используем название команды
                teamTag = teamData.primary_tag || teamData.name || teamData.title || '';
                teamName = teamData.name || teamData.title || '';
              } catch (err) {
                // Если команда не найдена, используем данные из объекта
                teamTag = teamItem.primary_tag || teamItem.name || teamItem.team_name || teamSlug;
                teamName = teamItem.name || teamItem.team_name || teamSlug;
              }
            } else if (teamName) {
              // Если есть название, но нет slug, используем primary_tag из объекта или название
              teamTag = teamItem.primary_tag || teamName;
            } else {
              teamTag = '';
            }
          } else {
            // Старый формат - строка (slug или название)
            const teamSlug = String(teamItem);
            try {
              const res = await contentApi.getTeam(teamSlug);
              const teamData = res.data;
              // Используем primary_tag, если он задан, иначе используем название команды
              teamTag = teamData.primary_tag || teamData.name || teamData.title || teamSlug;
              teamName = teamData.name || teamData.title || teamSlug;
            } catch (err) {
              teamTag = teamSlug;
              teamName = teamSlug;
            }
          }

          // Если primary_tag не задан, используем очищенное название команды
          if (!teamTag && teamName) {
            teamTag = cleanTeamName(teamName);
          }
          
          // Добавляем базовый тег команды в список, если его еще нет в тегах
          if (teamTag && !currentTags.some(tag => tag.toLowerCase() === teamTag.toLowerCase())) {
            teamNamesToAdd.push(teamTag);
          }
        })
      );

      // Обновляем теги, добавляя новые названия команд
      if (teamNamesToAdd.length > 0) {
        setKvn(prev => ({
          ...prev,
          tags: [...(prev.tags || []), ...teamNamesToAdd]
        }));
      }
    };

    updateTagsFromTeams();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kvn.season_data?.all_teams]);

  // Load jury members if this is the jury stats page
  useEffect(() => {
    // Reset loading state when slug changes
    if (kvn.slug !== 'vl-jury') {
      setLoadingJury(false);
      setJuryMembers([]);
      return;
    }

    let cancelled = false;
    setLoadingJury(true);
    contentApi.getKvnJuryStats({ league_slug: 'vl-kvn' })
      .then(res => {
        if (!cancelled) {
          setJuryMembers(res.data.jury_members || []);
        }
      })
      .catch(err => {
        if (!cancelled) {
          console.error('Error loading jury members:', err);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingJury(false);
        }
      });

    return () => {
      cancelled = true;
      setLoadingJury(false);
    };
  }, [kvn.slug]);

  const generateSlug = (t) => t.toLowerCase().replace(/[а-яё]/g, c => ({ 'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ы':'y','э':'e','ю':'yu','я':'ya' }[c] || '')).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  const handleSave = async () => {
    setError(''); setSuccess(''); setSaving(true);
    try {
      const dataToSend = {};
      
      if (kvn.title !== undefined) dataToSend.title = kvn.title;
      if (kvn.slug !== undefined) dataToSend.slug = kvn.slug;
      if (kvn.name !== undefined) dataToSend.name = kvn.name || '';
      if (kvn.poster) {
        if (typeof kvn.poster === 'string') {
          dataToSend.poster = { url: kvn.poster, alt: '', caption: '', thumbnail: kvn.poster };
        } else if (kvn.poster.url) {
          dataToSend.poster = kvn.poster;
        }
      } else if (kvn.poster === null) {
        dataToSend.poster = null;
      }
      if (kvn.facts && Object.keys(kvn.facts).length > 0) dataToSend.facts = kvn.facts;
      if (kvn.facts_order && Array.isArray(kvn.facts_order) && kvn.facts_order.length > 0) {
        dataToSend.facts_order = kvn.facts_order;
      }
      if (kvn.description) dataToSend.description = kvn.description;
      // parent_id может быть null для корневой страницы
      if (kvn.parent_id !== undefined) {
        dataToSend.parent_id = kvn.parent_id || null;
      }
      if (kvn.modules) dataToSend.modules = kvn.modules;
      if (kvn.tags) dataToSend.tags = kvn.tags;
      if (kvn.seo) dataToSend.seo = kvn.seo;
      if (kvn.status) dataToSend.status = kvn.status;
      if (kvn.person_ids !== undefined) dataToSend.person_ids = Array.isArray(kvn.person_ids) ? kvn.person_ids : [];
      if (kvn.team_ids !== undefined) dataToSend.team_ids = Array.isArray(kvn.team_ids) ? kvn.team_ids : [];
      if (kvn.social_links) dataToSend.social_links = kvn.social_links;
      if (kvn.season_data !== undefined) dataToSend.season_data = kvn.season_data;  // Сохраняем season_data
      if (kvn.jury_cards !== undefined) dataToSend.jury_cards = kvn.jury_cards;  // Сохраняем карточки жюри
      
      if (isNew) {
        const res = await contentApi.createKvn(dataToSend);
        setSuccess('Создано!');
        navigate(`/admin/kvn/${res.data.id}`, { replace: true });
      } else {
        const oldSlug = kvn.slug;
        await contentApi.updateKvn(id, dataToSend);
        setSuccess('Сохранено!');
        // Reload data after save to get updated full_path and other fields
        // This is especially important if slug changed
        try {
          const res = await contentApi.getKvn(id);
          let poster = res.data.poster;
          if (poster) {
            if (typeof poster === 'string') {
              poster = { url: poster, alt: '', caption: '', thumbnail: poster };
            }
          }
          setKvn({ 
            ...emptyKvn, 
            ...res.data, 
            poster: poster,
            parent_id: res.data.parent_id || null,
            facts: res.data.facts || {},
            facts_order: res.data.facts_order || [],
            social_links: res.data.social_links || {},
            seo: { ...emptyKvn.seo, ...res.data.seo },
            season_data: res.data.season_data || null,
            jury_cards: res.data.jury_cards || {}
          });
        } catch (reloadErr) {
          console.error('Error reloading data after save:', reloadErr);
          // Don't show error to user, just log it
        }
      }
    } catch (err) {
      setError(getErrorMessage(err, 'Ошибка сохранения'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-6">
      <div className="sticky top-0 z-50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b pb-4 pt-4 -mx-6 px-6 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate('/admin/kvn')}><ArrowLeft className="h-5 w-5" /></Button>
            <div>
              <h1 className="text-2xl font-bold">{isNew ? 'Новая страница КВН' : kvn.name || 'Редактирование'}</h1>
              {!isNew && <p className="text-sm text-muted-foreground">/{kvn.full_path || kvn.slug}</p>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!isNew && kvn.full_path && (
              <Button variant="outline" onClick={() => window.open(`/${kvn.full_path}`, '_blank')}>
                <ExternalLink className="mr-2 h-4 w-4" />Предпросмотр
              </Button>
            )}
            <Select value={kvn.status} onValueChange={(v) => setKvn(p => ({ ...p, status: v }))}>
              <SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="draft">Черновик</SelectItem>
                <SelectItem value="published">Опубликовать</SelectItem>
                <SelectItem value="archived">В архив</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />} Сохранить
            </Button>
          </div>
        </div>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {success && <Alert><AlertDescription>{success}</AlertDescription></Alert>}

      <Tabs defaultValue="main" className="space-y-6">
        <TabsList>
          <TabsTrigger value="main">Основное</TabsTrigger>
          <TabsTrigger value="facts">Факты</TabsTrigger>
          <TabsTrigger value="modules">Модули ({kvn.modules.length})</TabsTrigger>
          <TabsTrigger value="season">Сезон</TabsTrigger>
          {kvn.slug === 'vl-jury' && <TabsTrigger value="jury-cards">Карточки жюри</TabsTrigger>}
          <TabsTrigger value="seo">SEO</TabsTrigger>
        </TabsList>

        <TabsContent value="main" className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>Основная информация</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Название</Label>
                  <Input value={kvn.name} onChange={(e) => setKvn(p => ({ ...p, name: e.target.value, title: p.title || e.target.value, slug: p.slug || generateSlug(e.target.value) }))} placeholder="Название страницы" />
                </div>
                <div className="space-y-2">
                  <Label>Заголовок страницы</Label>
                  <Input value={kvn.title} onChange={(e) => setKvn(p => ({ ...p, title: e.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label>URL (slug)</Label>
                  <Input value={kvn.slug} onChange={(e) => setKvn(p => ({ ...p, slug: e.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label>Описание</Label>
                  <Textarea value={kvn.description || ''} onChange={(e) => setKvn(p => ({ ...p, description: e.target.value }))} rows={4} />
                </div>
                <MediaSelector
                  value={kvn.poster}
                  onChange={(poster) => setKvn(p => ({ ...p, poster }))}
                  label="Постер"
                />
                <div className="space-y-2">
                  <Label>Родительская страница</Label>
                  <Select
                    value={kvn.parent_id || 'null'}
                    onValueChange={(v) => setKvn(p => ({ ...p, parent_id: v === 'null' ? null : v }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Корневая страница" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="null">Корневая страница (без родителя)</SelectItem>
                      {parentOptions.map((parent) => (
                        <SelectItem key={parent.id} value={parent.id}>
                          {'  '.repeat(parent.level || 0)}
                          {parent.name || parent.title} ({parent.full_path || parent.slug})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Выберите родительскую страницу для создания иерархии. Оставьте "Корневая страница" для страниц верхнего уровня.
                  </p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Теги</CardTitle></CardHeader>
              <CardContent>
                <TagSelector value={kvn.tags} onChange={(tags) => setKvn(p => ({ ...p, tags }))} placeholder="Выберите или добавьте тег..." />
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Связанные люди</CardTitle></CardHeader>
              <CardContent>
                <PersonSelector value={kvn.person_ids || []} onChange={(ids) => setKvn(p => ({ ...p, person_ids: ids }))} placeholder="Выберите людей..." />
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Связанные команды</CardTitle></CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">Выбор команд будет добавлен позже</p>
                {/* TODO: добавить TeamSelector */}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="facts" className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Факты</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {Object.keys(kvn.facts || {}).length > 0 ? (
                <FactsEditor
                  facts={kvn.facts || {}}
                  factsOrder={kvn.facts_order || []}
                  onChange={({ facts, facts_order }) => setKvn(p => ({ ...p, facts, facts_order }))}
                />
              ) : <p className="text-muted-foreground text-sm">Нет фактов</p>}
              
              <div className="flex items-center gap-2 pt-4 border-t">
                <Input value={newFactKey} onChange={(e) => setNewFactKey(e.target.value)} placeholder="Название" className="w-1/3" />
                <Input value={newFactValue} onChange={(e) => setNewFactValue(e.target.value)} placeholder="Значение" className="flex-1" onKeyDown={(e) => {
                  if (e.key === 'Enter' && newFactKey.trim() && newFactValue.trim()) {
                    setKvn(p => ({
                      ...p,
                      facts: { ...p.facts, [newFactKey.trim()]: newFactValue.trim() },
                      facts_order: [...(p.facts_order || []), newFactKey.trim()]
                    }));
                    setNewFactKey('');
                    setNewFactValue('');
                  }
                }} />
                <Button variant="outline" onClick={() => {
                  if (newFactKey.trim() && newFactValue.trim()) {
                    setKvn(p => ({
                      ...p,
                      facts: { ...p.facts, [newFactKey.trim()]: newFactValue.trim() },
                      facts_order: [...(p.facts_order || []), newFactKey.trim()]
                    }));
                    setNewFactKey('');
                    setNewFactValue('');
                  }
                }}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Ссылки</CardTitle></CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {['website', 'vk', 'telegram', 'youtube', 'instagram'].map(key => (
                  <div key={key} className="space-y-2">
                    <Label>{key === 'website' ? 'Официальный сайт' : key === 'vk' ? 'ВКонтакте' : key.charAt(0).toUpperCase() + key.slice(1)}</Label>
                    <Input value={kvn.social_links?.[key] || ''} onChange={(e) => setKvn(p => ({ ...p, social_links: { ...p.social_links, [key]: e.target.value } }))} placeholder="https://..." />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="modules">
          <ModuleEditor modules={kvn.modules} onChange={(m) => setKvn(p => ({ ...p, modules: m }))} contentType="kvn" />
        </TabsContent>

        <TabsContent value="season">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Данные сезона</CardTitle>
                {!kvn.season_data && (
                  <Button 
                    onClick={() => {
                      const newSeasonData = {
                        league_name: '',
                        year: new Date().getFullYear(),
                        season_number: 0,
                        winners: [],
                        all_teams: [],
                        intro_html: '',
                        description: '',
                        stages: []
                      };
                      setKvn(p => ({ ...p, season_data: newSeasonData }));
                    }}
                    variant="outline"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Создать шаблон сезона
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <SeasonDataEditor 
                seasonData={kvn.season_data} 
                onChange={(seasonData) => setKvn(p => ({ ...p, season_data: seasonData }))} 
              />
            </CardContent>
          </Card>
        </TabsContent>

        {kvn.slug === 'vl-jury' && (
          <TabsContent value="jury-cards">
            <Card>
              <CardHeader>
                <CardTitle>Редактирование карточек судей</CardTitle>
              </CardHeader>
              <CardContent>
                {loadingJury ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin" />
                  </div>
                ) : (
                  <div className="space-y-6">
                    {juryMembers.map((jury) => {
                      const juryCard = kvn.jury_cards?.[jury.name] || { photo: null, text: '' };
                      return (
                        <Card key={jury.name}>
                          <CardHeader>
                            <CardTitle className="text-lg">{jury.name}</CardTitle>
                            <p className="text-sm text-muted-foreground">Игр в жюри: {jury.games_count}</p>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="space-y-2">
                              <Label>Фото</Label>
                              <MediaSelector
                                value={juryCard.photo}
                                onChange={(photo) => {
                                  setKvn(p => ({
                                    ...p,
                                    jury_cards: {
                                      ...(p.jury_cards || {}),
                                      [jury.name]: {
                                        ...(p.jury_cards?.[jury.name] || {}),
                                        photo
                                      }
                                    }
                                  }));
                                }}
                                label=""
                              />
                            </div>
                            <div className="space-y-2">
                              <Label>Текст</Label>
                              <Textarea
                                value={juryCard.text || ''}
                                onChange={(e) => {
                                  setKvn(p => ({
                                    ...p,
                                    jury_cards: {
                                      ...(p.jury_cards || {}),
                                      [jury.name]: {
                                        ...(p.jury_cards?.[jury.name] || {}),
                                        text: e.target.value
                                      }
                                    }
                                  }));
                                }}
                                rows={4}
                                placeholder="Введите текст для карточки судьи..."
                              />
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        <TabsContent value="seo">
          <Card>
            <CardHeader><CardTitle>SEO настройки</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2"><Label>Meta Title</Label><Input value={kvn.seo.meta_title || ''} onChange={(e) => setKvn(p => ({ ...p, seo: { ...p.seo, meta_title: e.target.value } }))} /></div>
              <div className="space-y-2"><Label>Meta Description</Label><Textarea value={kvn.seo.meta_description || ''} onChange={(e) => setKvn(p => ({ ...p, seo: { ...p.seo, meta_description: e.target.value } }))} rows={3} /></div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

