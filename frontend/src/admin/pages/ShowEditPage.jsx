import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { contentApi } from '../utils/api';
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

const emptyShow = {
  title: '', slug: '', name: '', status: 'draft',
  poster: null, description: '',
  facts: {},  // Произвольные факты key-value
  social_links: {},  // Социальные ссылки
  modules: [], tags: [],
  seo: { meta_title: '', meta_description: '' }
};

export default function ShowEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';

  const [show, setShow] = useState(emptyShow);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [newFactKey, setNewFactKey] = useState('');
  const [newFactValue, setNewFactValue] = useState('');

  useEffect(() => {
    if (!isNew) {
      contentApi.getShow(id).then(res => {
        setShow({ 
          ...emptyShow, 
          ...res.data, 
          facts: res.data.facts || {},
          social_links: res.data.social_links || {},
          seo: { ...emptyShow.seo, ...res.data.seo } 
        });
      }).catch(() => setError('Ошибка загрузки')).finally(() => setLoading(false));
    }
  }, [id, isNew]);

  const generateSlug = (t) => t.toLowerCase().replace(/[а-яё]/g, c => ({ 'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ы':'y','э':'e','ю':'yu','я':'ya' }[c] || '')).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  const handleSave = async () => {
    setError(''); setSuccess(''); setSaving(true);
    try {
      if (isNew) {
        const res = await contentApi.createShow(show);
        setSuccess('Создано!');
        navigate(`/admin/shows/${res.data.id}`, { replace: true });
      } else {
        await contentApi.updateShow(id, show);
        setSuccess('Сохранено!');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/admin/shows')}><ArrowLeft className="h-5 w-5" /></Button>
          <div>
            <h1 className="text-2xl font-bold">{isNew ? 'Новое шоу' : show.name || 'Редактирование'}</h1>
            {!isNew && <p className="text-sm text-muted-foreground">/{show.slug}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isNew && show.slug && (
            <Button variant="outline" onClick={() => window.open(`/shows/${show.slug}`, '_blank')}>
              <ExternalLink className="mr-2 h-4 w-4" />Предпросмотр
            </Button>
          )}
          <Select value={show.status} onValueChange={(v) => setShow(p => ({ ...p, status: v }))}>
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

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {success && <Alert><AlertDescription>{success}</AlertDescription></Alert>}

      <Tabs defaultValue="main" className="space-y-6">
        <TabsList>
          <TabsTrigger value="main">Основное</TabsTrigger>
          <TabsTrigger value="facts">Факты</TabsTrigger>
          <TabsTrigger value="modules">Модули ({show.modules.length})</TabsTrigger>
          <TabsTrigger value="seo">SEO</TabsTrigger>
        </TabsList>

        <TabsContent value="main" className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader><CardTitle>Основная информация</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Название шоу</Label>
                  <Input value={show.name} onChange={(e) => setShow(p => ({ ...p, name: e.target.value, title: p.title || e.target.value, slug: p.slug || generateSlug(e.target.value) }))} placeholder="Comedy Club" />
                </div>
                <div className="space-y-2">
                  <Label>Заголовок страницы</Label>
                  <Input value={show.title} onChange={(e) => setShow(p => ({ ...p, title: e.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label>URL (slug)</Label>
                  <Input value={show.slug} onChange={(e) => setShow(p => ({ ...p, slug: e.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label>Описание</Label>
                  <Textarea value={show.description || ''} onChange={(e) => setShow(p => ({ ...p, description: e.target.value }))} rows={4} />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Теги</CardTitle></CardHeader>
              <CardContent>
                <TagSelector value={show.tags} onChange={(tags) => setShow(p => ({ ...p, tags }))} placeholder="Выберите или добавьте тег..." />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="facts" className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Факты о шоу</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {/* Существующие факты */}
              {Object.entries(show.facts || {}).length > 0 ? (
                <div className="space-y-2">
                  {Object.entries(show.facts).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2 p-2 bg-muted rounded">
                      <Input 
                        value={key} 
                        className="w-1/3 bg-background"
                        onChange={(e) => {
                          const newFacts = { ...show.facts };
                          delete newFacts[key];
                          newFacts[e.target.value] = value;
                          setShow(p => ({ ...p, facts: newFacts }));
                        }}
                      />
                      <Input 
                        value={value} 
                        className="flex-1 bg-background"
                        onChange={(e) => setShow(p => ({ ...p, facts: { ...p.facts, [key]: e.target.value } }))}
                      />
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => {
                          const newFacts = { ...show.facts };
                          delete newFacts[key];
                          setShow(p => ({ ...p, facts: newFacts }));
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
                  placeholder="Название (напр. Статус шоу)"
                  className="w-1/3"
                />
                <Input 
                  value={newFactValue} 
                  onChange={(e) => setNewFactValue(e.target.value)}
                  placeholder="Значение"
                  className="flex-1"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && newFactKey.trim() && newFactValue.trim()) {
                      setShow(p => ({ ...p, facts: { ...p.facts, [newFactKey.trim()]: newFactValue.trim() } }));
                      setNewFactKey('');
                      setNewFactValue('');
                    }
                  }}
                />
                <Button 
                  variant="outline"
                  onClick={() => {
                    if (newFactKey.trim() && newFactValue.trim()) {
                      setShow(p => ({ ...p, facts: { ...p.facts, [newFactKey.trim()]: newFactValue.trim() } }));
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

          <Card>
            <CardHeader><CardTitle>Ссылки</CardTitle></CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {['website', 'vk', 'telegram', 'youtube', 'instagram'].map(key => (
                  <div key={key} className="space-y-2">
                    <Label>{key === 'website' ? 'Официальный сайт' : key === 'vk' ? 'ВКонтакте' : key.charAt(0).toUpperCase() + key.slice(1)}</Label>
                    <Input 
                      value={show.social_links?.[key] || ''} 
                      onChange={(e) => setShow(p => ({ ...p, social_links: { ...p.social_links, [key]: e.target.value } }))}
                      placeholder="https://..."
                    />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="modules">
          <ModuleEditor modules={show.modules} onChange={(m) => setShow(p => ({ ...p, modules: m }))} contentType="show" />
        </TabsContent>

        <TabsContent value="seo">
          <Card>
            <CardHeader><CardTitle>SEO настройки</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2"><Label>Meta Title</Label><Input value={show.seo.meta_title || ''} onChange={(e) => setShow(p => ({ ...p, seo: { ...p.seo, meta_title: e.target.value } }))} /></div>
              <div className="space-y-2"><Label>Meta Description</Label><Textarea value={show.seo.meta_description || ''} onChange={(e) => setShow(p => ({ ...p, seo: { ...p.seo, meta_description: e.target.value } }))} rows={3} /></div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
