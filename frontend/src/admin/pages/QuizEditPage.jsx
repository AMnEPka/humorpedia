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
import { Checkbox } from '@/components/ui/checkbox';
import { Save, ArrowLeft, Loader2, Plus, X, Trash2 } from 'lucide-react';

const emptyQuiz = { title: '', slug: '', status: 'draft', description: '', cover_image: null, modules: [], tags: [], seo: { meta_title: '', meta_description: '' } };

export default function QuizEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';

  const [quiz, setQuiz] = useState(emptyQuiz);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [tagInput, setTagInput] = useState('');

  // Quiz questions state
  const [questions, setQuestions] = useState([]);
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (!isNew) {
      contentApi.getQuiz(id).then(res => {
        setQuiz({ ...emptyQuiz, ...res.data, seo: { ...emptyQuiz.seo, ...res.data.seo } });
        // Extract questions and results from modules
        const qModule = res.data.modules?.find(m => m.type === 'quiz_questions');
        const rModule = res.data.modules?.find(m => m.type === 'quiz_results');
        if (qModule?.data?.questions) setQuestions(qModule.data.questions);
        if (rModule?.data?.results) setResults(rModule.data.results);
      }).catch(() => setError('Ошибка загрузки')).finally(() => setLoading(false));
    }
  }, [id, isNew]);

  const generateSlug = (t) => t.toLowerCase().replace(/[а-яё]/g, c => ({'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ы':'y','э':'e','ю':'yu','я':'ya'}[c] || '')).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  const handleSave = async () => {
    setError(''); setSuccess(''); setSaving(true);
    // Build modules from questions and results
    const modules = [
      { id: 'quiz-questions', type: 'quiz_questions', order: 0, visible: true, data: { questions } },
      { id: 'quiz-results', type: 'quiz_results', order: 1, visible: true, data: { results } }
    ];
    const dataToSave = { ...quiz, modules };
    try {
      if (isNew) { const res = await contentApi.createQuiz(dataToSave); setSuccess('Создано!'); navigate(`/admin/quizzes/${res.data.id}`, { replace: true }); }
      else { await contentApi.updateQuiz(id, dataToSave); setSuccess('Сохранено!'); }
    } catch (err) { setError(err.response?.data?.detail || 'Ошибка'); } finally { setSaving(false); }
  };

  const addQuestion = () => setQuestions([...questions, { id: questions.length + 1, question: '', options: [{ id: 'a', text: '', correct: false }, { id: 'b', text: '', correct: false }, { id: 'c', text: '', correct: false }], explanation: '' }]);
  const removeQuestion = (idx) => setQuestions(questions.filter((_, i) => i !== idx));
  const updateQuestion = (idx, field, value) => { const q = [...questions]; q[idx] = { ...q[idx], [field]: value }; setQuestions(q); };
  const updateOption = (qIdx, oIdx, field, value) => { const q = [...questions]; q[qIdx].options[oIdx] = { ...q[qIdx].options[oIdx], [field]: value }; setQuestions(q); };
  const setCorrectOption = (qIdx, oIdx) => { const q = [...questions]; q[qIdx].options = q[qIdx].options.map((o, i) => ({ ...o, correct: i === oIdx })); setQuestions(q); };

  const addResult = () => setResults([...results, { min_score: 0, max_score: 0, title: '', description: '' }]);
  const removeResult = (idx) => setResults(results.filter((_, i) => i !== idx));
  const updateResult = (idx, field, value) => { const r = [...results]; r[idx] = { ...r[idx], [field]: value }; setResults(r); };

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/admin/quizzes')}><ArrowLeft className="h-5 w-5" /></Button>
          <div><h1 className="text-2xl font-bold">{isNew ? 'Новый квиз' : quiz.title || 'Редактирование'}</h1>{!isNew && <p className="text-sm text-muted-foreground">/{quiz.slug}</p>}</div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={quiz.status} onValueChange={(v) => setQuiz(p => ({ ...p, status: v }))}><SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="draft">Черновик</SelectItem><SelectItem value="published">Опубликовать</SelectItem></SelectContent></Select>
          <Button onClick={handleSave} disabled={saving}>{saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />} Сохранить</Button>
        </div>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {success && <Alert><AlertDescription>{success}</AlertDescription></Alert>}

      <Tabs defaultValue="main" className="space-y-6">
        <TabsList><TabsTrigger value="main">Основное</TabsTrigger><TabsTrigger value="questions">Вопросы ({questions.length})</TabsTrigger><TabsTrigger value="results">Результаты ({results.length})</TabsTrigger></TabsList>

        <TabsContent value="main" className="space-y-6">
          <Card><CardHeader><CardTitle>Основная информация</CardTitle></CardHeader><CardContent className="space-y-4">
            <div className="space-y-2"><Label>Название квиза</Label><Input value={quiz.title} onChange={(e) => setQuiz(p => ({ ...p, title: e.target.value, slug: p.slug || generateSlug(e.target.value) }))} placeholder="Угадай команду по шутке" /></div>
            <div className="space-y-2"><Label>URL (slug)</Label><Input value={quiz.slug} onChange={(e) => setQuiz(p => ({ ...p, slug: e.target.value }))} /></div>
            <div className="space-y-2"><Label>Описание</Label><Textarea value={quiz.description || ''} onChange={(e) => setQuiz(p => ({ ...p, description: e.target.value }))} rows={3} /></div>
            <div className="space-y-2"><Label>Теги</Label><div className="flex gap-2"><Input value={tagInput} onChange={(e) => setTagInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), tagInput.trim() && !quiz.tags.includes(tagInput.trim()) && (setQuiz(p => ({ ...p, tags: [...p.tags, tagInput.trim()] })), setTagInput('')))} /><Button variant="outline" onClick={() => tagInput.trim() && !quiz.tags.includes(tagInput.trim()) && (setQuiz(p => ({ ...p, tags: [...p.tags, tagInput.trim()] })), setTagInput(''))}><Plus className="h-4 w-4" /></Button></div></div>
            <div className="flex flex-wrap gap-2">{quiz.tags.map(tag => <Badge key={tag} variant="secondary" className="pr-1">{tag}<button onClick={() => setQuiz(p => ({ ...p, tags: p.tags.filter(t => t !== tag) }))} className="ml-1 hover:text-destructive"><X className="h-3 w-3" /></button></Badge>)}</div>
          </CardContent></Card>
        </TabsContent>

        <TabsContent value="questions" className="space-y-4">
          {questions.map((q, qIdx) => (
            <Card key={qIdx}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-base">Вопрос {qIdx + 1}</CardTitle>
                <Button variant="ghost" size="icon" onClick={() => removeQuestion(qIdx)}><Trash2 className="h-4 w-4" /></Button>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2"><Label>Текст вопроса</Label><Input value={q.question} onChange={(e) => updateQuestion(qIdx, 'question', e.target.value)} /></div>
                <div className="space-y-2"><Label>Варианты ответов</Label>
                  {q.options.map((o, oIdx) => (
                    <div key={oIdx} className="flex items-center gap-2">
                      <Checkbox checked={o.correct} onCheckedChange={() => setCorrectOption(qIdx, oIdx)} />
                      <Input value={o.text} onChange={(e) => updateOption(qIdx, oIdx, 'text', e.target.value)} placeholder={`Вариант ${String.fromCharCode(65 + oIdx)}`} />
                    </div>
                  ))}
                </div>
                <div className="space-y-2"><Label>Объяснение (опционально)</Label><Input value={q.explanation || ''} onChange={(e) => updateQuestion(qIdx, 'explanation', e.target.value)} /></div>
              </CardContent>
            </Card>
          ))}
          <Button onClick={addQuestion} className="w-full"><Plus className="mr-2 h-4 w-4" /> Добавить вопрос</Button>
        </TabsContent>

        <TabsContent value="results" className="space-y-4">
          {results.map((r, rIdx) => (
            <Card key={rIdx}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-base">Результат {rIdx + 1}</CardTitle>
                <Button variant="ghost" size="icon" onClick={() => removeResult(rIdx)}><Trash2 className="h-4 w-4" /></Button>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2"><Label>Мин. балл</Label><Input type="number" value={r.min_score} onChange={(e) => updateResult(rIdx, 'min_score', parseInt(e.target.value) || 0)} /></div>
                  <div className="space-y-2"><Label>Макс. балл</Label><Input type="number" value={r.max_score} onChange={(e) => updateResult(rIdx, 'max_score', parseInt(e.target.value) || 0)} /></div>
                </div>
                <div className="space-y-2"><Label>Заголовок</Label><Input value={r.title} onChange={(e) => updateResult(rIdx, 'title', e.target.value)} placeholder="Знаток КВН" /></div>
                <div className="space-y-2"><Label>Описание</Label><Textarea value={r.description} onChange={(e) => updateResult(rIdx, 'description', e.target.value)} rows={2} /></div>
              </CardContent>
            </Card>
          ))}
          <Button onClick={addResult} className="w-full"><Plus className="mr-2 h-4 w-4" /> Добавить результат</Button>
        </TabsContent>
      </Tabs>
    </div>
  );
}
