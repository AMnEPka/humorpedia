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
import { Switch } from '@/components/ui/switch';
import { Save, ArrowLeft, Loader2, ExternalLink } from 'lucide-react';
import ModuleEditor from '../components/ModuleEditor';
import TagSelector from '../components/TagSelector';

const emptyArticle = { title: '', slug: '', status: 'draft', excerpt: '', cover_image: null, author_name: '', featured: false, modules: [], tags: [], seo: { meta_title: '', meta_description: '' } };

export default function ArticleEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';

  const [article, setArticle] = useState(emptyArticle);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (!isNew) {
      contentApi.getArticle(id).then(res => setArticle({ ...emptyArticle, ...res.data, seo: { ...emptyArticle.seo, ...res.data.seo } })).catch(() => setError('Ошибка загрузки')).finally(() => setLoading(false));
    }
  }, [id, isNew]);

  const generateSlug = (t) => t.toLowerCase().replace(/[а-яё]/g, c => ({'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ы':'y','э':'e','ю':'yu','я':'ya'}[c] || '')).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  const handleSave = async () => {
    setError(''); setSuccess(''); setSaving(true);
    try {
      if (isNew) { const res = await contentApi.createArticle(article); setSuccess('Создано!'); navigate(`/admin/articles/${res.data.id}`, { replace: true }); }
      else { await contentApi.updateArticle(id, article); setSuccess('Сохранено!'); }
    } catch (err) { setError(err.response?.data?.detail || 'Ошибка'); } finally { setSaving(false); }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/admin/articles')}><ArrowLeft className="h-5 w-5" /></Button>
          <div><h1 className="text-2xl font-bold">{isNew ? 'Новая статья' : article.title || 'Редактирование'}</h1>{!isNew && <p className="text-sm text-muted-foreground">/{article.slug}</p>}</div>
        </div>
        <div className="flex items-center gap-2">
          {!isNew && article.slug && <Button variant="outline" onClick={() => window.open(`/articles/${article.slug}`, '_blank')}><ExternalLink className="mr-2 h-4 w-4" />Предпросмотр</Button>}
          <Select value={article.status} onValueChange={(v) => setArticle(p => ({ ...p, status: v }))}><SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="draft">Черновик</SelectItem><SelectItem value="published">Опубликовать</SelectItem><SelectItem value="archived">В архив</SelectItem></SelectContent></Select>
          <Button onClick={handleSave} disabled={saving}>{saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />} Сохранить</Button>
        </div>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {success && <Alert><AlertDescription>{success}</AlertDescription></Alert>}

      <Tabs defaultValue="main" className="space-y-6">
        <TabsList><TabsTrigger value="main">Основное</TabsTrigger><TabsTrigger value="modules">Модули ({article.modules.length})</TabsTrigger><TabsTrigger value="seo">SEO</TabsTrigger></TabsList>

        <TabsContent value="main" className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            <Card><CardHeader><CardTitle>Основная информация</CardTitle></CardHeader><CardContent className="space-y-4">
              <div className="space-y-2"><Label>Заголовок</Label><Input value={article.title} onChange={(e) => setArticle(p => ({ ...p, title: e.target.value, slug: p.slug || generateSlug(e.target.value) }))} placeholder="Заголовок статьи" /></div>
              <div className="space-y-2"><Label>URL (slug)</Label><Input value={article.slug} onChange={(e) => setArticle(p => ({ ...p, slug: e.target.value }))} /></div>
              <div className="space-y-2"><Label>Автор</Label><Input value={article.author_name || ''} onChange={(e) => setArticle(p => ({ ...p, author_name: e.target.value }))} placeholder="Имя автора" /></div>
              <div className="space-y-2"><Label>Краткое описание</Label><Textarea value={article.excerpt || ''} onChange={(e) => setArticle(p => ({ ...p, excerpt: e.target.value }))} rows={3} /></div>
              <div className="flex items-center gap-2"><Switch checked={article.featured} onCheckedChange={(v) => setArticle(p => ({ ...p, featured: v }))} /><Label>Избранная статья</Label></div>
            </CardContent></Card>
            <Card><CardHeader><CardTitle>Теги</CardTitle></CardHeader><CardContent className="space-y-4">
              <div className="flex gap-2"><Input value={tagInput} onChange={(e) => setTagInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), tagInput.trim() && !article.tags.includes(tagInput.trim()) && (setArticle(p => ({ ...p, tags: [...p.tags, tagInput.trim()] })), setTagInput('')))} placeholder="Добавить тег..." /><Button type="button" variant="outline" onClick={() => tagInput.trim() && !article.tags.includes(tagInput.trim()) && (setArticle(p => ({ ...p, tags: [...p.tags, tagInput.trim()] })), setTagInput(''))}><Plus className="h-4 w-4" /></Button></div>
              <div className="flex flex-wrap gap-2">{article.tags.map(tag => <Badge key={tag} variant="secondary" className="pr-1">{tag}<button onClick={() => setArticle(p => ({ ...p, tags: p.tags.filter(t => t !== tag) }))} className="ml-1 hover:text-destructive"><X className="h-3 w-3" /></button></Badge>)}</div>
            </CardContent></Card>
          </div>
        </TabsContent>

        <TabsContent value="modules"><ModuleEditor modules={article.modules} onChange={(m) => setArticle(p => ({ ...p, modules: m }))} contentType="article" /></TabsContent>

        <TabsContent value="seo"><Card><CardHeader><CardTitle>SEO настройки</CardTitle></CardHeader><CardContent className="space-y-4">
          <div className="space-y-2"><Label>Meta Title</Label><Input value={article.seo.meta_title || ''} onChange={(e) => setArticle(p => ({ ...p, seo: { ...p.seo, meta_title: e.target.value } }))} /></div>
          <div className="space-y-2"><Label>Meta Description</Label><Textarea value={article.seo.meta_description || ''} onChange={(e) => setArticle(p => ({ ...p, seo: { ...p.seo, meta_description: e.target.value } }))} rows={3} /></div>
        </CardContent></Card></TabsContent>
      </Tabs>
    </div>
  );
}
