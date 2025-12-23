import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { contentApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Switch } from '@/components/ui/switch';
import { Save, ArrowLeft, Loader2, Plus, X } from 'lucide-react';
import ModuleEditor from '../components/ModuleEditor';
import TagSelector from '../components/TagSelector';

const emptyWiki = { title: '', slug: '', status: 'draft', content: '', cover_image: null, has_header: false, header_image: null, header_facts: [], modules: [], tags: [], seo: { meta_title: '', meta_description: '' } };

export default function WikiEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';

  const [wiki, setWiki] = useState(emptyWiki);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [tagInput, setTagInput] = useState('');
  const [factLabel, setFactLabel] = useState('');
  const [factValue, setFactValue] = useState('');

  useEffect(() => {
    if (!isNew) {
      contentApi.getWiki(id).then(res => setWiki({ ...emptyWiki, ...res.data, seo: { ...emptyWiki.seo, ...res.data.seo } })).catch(() => setError('Ошибка загрузки')).finally(() => setLoading(false));
    }
  }, [id, isNew]);

  const generateSlug = (t) => t.toLowerCase().replace(/[а-яё]/g, c => ({'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ы':'y','э':'e','ю':'yu','я':'ya'}[c] || '')).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  const handleSave = async () => {
    setError(''); setSuccess(''); setSaving(true);
    try {
      if (isNew) { const res = await contentApi.createWiki(wiki); setSuccess('Создано!'); navigate(`/admin/wiki/${res.data.id}`, { replace: true }); }
      else { await contentApi.updateWiki(id, wiki); setSuccess('Сохранено!'); }
    } catch (err) { setError(err.response?.data?.detail || 'Ошибка'); } finally { setSaving(false); }
  };

  const addFact = () => { if (factLabel.trim() && factValue.trim()) { setWiki(p => ({ ...p, header_facts: [...p.header_facts, { label: factLabel.trim(), value: factValue.trim() }] })); setFactLabel(''); setFactValue(''); } };

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/admin/wiki')}><ArrowLeft className="h-5 w-5" /></Button>
          <div><h1 className="text-2xl font-bold">{isNew ? 'Новая вики-страница' : wiki.title || 'Редактирование'}</h1>{!isNew && <p className="text-sm text-muted-foreground">/{wiki.slug}</p>}</div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={wiki.status} onValueChange={(v) => setWiki(p => ({ ...p, status: v }))}><SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="draft">Черновик</SelectItem><SelectItem value="published">Опубликовать</SelectItem><SelectItem value="archived">В архив</SelectItem></SelectContent></Select>
          <Button onClick={handleSave} disabled={saving}>{saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />} Сохранить</Button>
        </div>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {success && <Alert><AlertDescription>{success}</AlertDescription></Alert>}

      <Tabs defaultValue="main" className="space-y-6">
        <TabsList><TabsTrigger value="main">Основное</TabsTrigger><TabsTrigger value="content">Содержимое</TabsTrigger>{wiki.has_header && <TabsTrigger value="header">Шапка</TabsTrigger>}<TabsTrigger value="modules">Модули ({wiki.modules.length})</TabsTrigger><TabsTrigger value="seo">SEO</TabsTrigger></TabsList>

        <TabsContent value="main" className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            <Card><CardHeader><CardTitle>Основная информация</CardTitle></CardHeader><CardContent className="space-y-4">
              <div className="space-y-2"><Label>Заголовок</Label><Input value={wiki.title} onChange={(e) => setWiki(p => ({ ...p, title: e.target.value, slug: p.slug || generateSlug(e.target.value) }))} /></div>
              <div className="space-y-2"><Label>URL (slug)</Label><Input value={wiki.slug} onChange={(e) => setWiki(p => ({ ...p, slug: e.target.value }))} /></div>
              <div className="flex items-center gap-2"><Switch checked={wiki.has_header} onCheckedChange={(v) => setWiki(p => ({ ...p, has_header: v }))} /><Label>Страница с шапкой</Label></div>
            </CardContent></Card>
            <Card><CardHeader><CardTitle>Теги</CardTitle></CardHeader><CardContent className="space-y-4">
              <div className="flex gap-2"><Input value={tagInput} onChange={(e) => setTagInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), tagInput.trim() && !wiki.tags.includes(tagInput.trim()) && (setWiki(p => ({ ...p, tags: [...p.tags, tagInput.trim()] })), setTagInput('')))} placeholder="Добавить тег..." /><Button type="button" variant="outline" onClick={() => tagInput.trim() && !wiki.tags.includes(tagInput.trim()) && (setWiki(p => ({ ...p, tags: [...p.tags, tagInput.trim()] })), setTagInput(''))}><Plus className="h-4 w-4" /></Button></div>
              <div className="flex flex-wrap gap-2">{wiki.tags.map(tag => <Badge key={tag} variant="secondary" className="pr-1">{tag}<button onClick={() => setWiki(p => ({ ...p, tags: p.tags.filter(t => t !== tag) }))} className="ml-1 hover:text-destructive"><X className="h-3 w-3" /></button></Badge>)}</div>
            </CardContent></Card>
          </div>
        </TabsContent>

        <TabsContent value="content"><Card><CardHeader><CardTitle>Содержимое</CardTitle></CardHeader><CardContent>
          <Textarea value={wiki.content || ''} onChange={(e) => setWiki(p => ({ ...p, content: e.target.value }))} rows={15} placeholder="HTML контент" className="font-mono" />
        </CardContent></Card></TabsContent>

        {wiki.has_header && <TabsContent value="header"><Card><CardHeader><CardTitle>Шапка страницы</CardTitle></CardHeader><CardContent className="space-y-4">
          <div className="space-y-2"><Label>Факты</Label>
            <div className="flex gap-2">
              <Input value={factLabel} onChange={(e) => setFactLabel(e.target.value)} placeholder="Название" className="w-1/3" />
              <Input value={factValue} onChange={(e) => setFactValue(e.target.value)} placeholder="Значение" />
              <Button variant="outline" onClick={addFact}><Plus className="h-4 w-4" /></Button>
            </div>
          </div>
          <div className="space-y-2">{wiki.header_facts.map((f, i) => <div key={i} className="flex items-center justify-between bg-muted p-2 rounded"><span><strong>{f.label}:</strong> {f.value}</span><button onClick={() => setWiki(p => ({ ...p, header_facts: p.header_facts.filter((_, j) => j !== i) }))} className="text-muted-foreground hover:text-destructive"><X className="h-4 w-4" /></button></div>)}</div>
        </CardContent></Card></TabsContent>}

        <TabsContent value="modules"><ModuleEditor modules={wiki.modules} onChange={(m) => setWiki(p => ({ ...p, modules: m }))} contentType="wiki" /></TabsContent>

        <TabsContent value="seo"><Card><CardHeader><CardTitle>SEO настройки</CardTitle></CardHeader><CardContent className="space-y-4">
          <div className="space-y-2"><Label>Meta Title</Label><Input value={wiki.seo.meta_title || ''} onChange={(e) => setWiki(p => ({ ...p, seo: { ...p.seo, meta_title: e.target.value } }))} /></div>
          <div className="space-y-2"><Label>Meta Description</Label><Textarea value={wiki.seo.meta_description || ''} onChange={(e) => setWiki(p => ({ ...p, seo: { ...p.seo, meta_description: e.target.value } }))} rows={3} /></div>
        </CardContent></Card></TabsContent>
      </Tabs>
    </div>
  );
}
