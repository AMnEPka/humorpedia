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
import { Checkbox } from '@/components/ui/checkbox';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Save, ArrowLeft, Loader2, Plus, Trash2, ExternalLink, GripVertical } from 'lucide-react';
import TagSelector from '../components/TagSelector';

const emptyQuiz = {
  title: '',
  slug: '',
  status: 'draft',
  description: '',
  cover_image: null,
  modules: [],
  tags: [],
  seo: { meta_title: '', meta_description: '' }
};

// Question types
const QUESTION_TYPES = {
  SINGLE: 'single',     // Single correct answer from options
  MULTIPLE: 'multiple', // Multiple correct answers from options
  TEXT: 'text'          // Free text answer
};

export default function QuizEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';

  const [quiz, setQuiz] = useState(emptyQuiz);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [questions, setQuestions] = useState([]);
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (!isNew) {
      contentApi.getQuiz(id)
        .then(res => {
          setQuiz({ ...emptyQuiz, ...res.data, seo: { ...emptyQuiz.seo, ...res.data.seo } });
          const qModule = res.data.modules?.find(m => m.type === 'quiz_questions');
          const rModule = res.data.modules?.find(m => m.type === 'quiz_results');
          if (qModule?.data?.questions) setQuestions(qModule.data.questions);
          if (rModule?.data?.results) setResults(rModule.data.results);
        })
        .catch(() => setError('Ошибка загрузки'))
        .finally(() => setLoading(false));
    }
  }, [id, isNew]);

  const generateSlug = (t) => t.toLowerCase()
    .replace(/[а-яё]/g, c => ({
      'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z',
      'и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r',
      'с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh',
      'щ':'shch','ы':'y','э':'e','ю':'yu','я':'ya'
    }[c] || ''))
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');

  const handleSave = async () => {
    setError('');
    setSuccess('');
    setSaving(true);
    
    const modules = [
      { id: 'quiz-questions', type: 'quiz_questions', order: 0, visible: true, data: { questions } },
      { id: 'quiz-results', type: 'quiz_results', order: 1, visible: true, data: { results } }
    ];
    
    const dataToSave = { ...quiz, modules };
    
    try {
      if (isNew) {
        const res = await contentApi.createQuiz(dataToSave);
        setSuccess('Создано!');
        navigate(`/admin/quizzes/${res.data.id}`, { replace: true });
      } else {
        await contentApi.updateQuiz(id, dataToSave);
        setSuccess('Сохранено!');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  // Question management
  const addQuestion = (type = QUESTION_TYPES.SINGLE) => {
    const newQuestion = {
      id: Date.now(),
      type,
      question: '',
      explanation: ''
    };
    
    if (type === QUESTION_TYPES.TEXT) {
      newQuestion.correct_answer = '';
    } else {
      newQuestion.options = [
        { id: 'a', text: '', correct: false }
      ];
    }
    
    setQuestions([...questions, newQuestion]);
  };

  const removeQuestion = (idx) => {
    setQuestions(questions.filter((_, i) => i !== idx));
  };

  const updateQuestion = (idx, field, value) => {
    const q = [...questions];
    q[idx] = { ...q[idx], [field]: value };
    setQuestions(q);
  };

  // Option management for choice questions
  const addOption = (qIdx) => {
    const q = [...questions];
    const optionCount = q[qIdx].options.length;
    const newId = String.fromCharCode(97 + optionCount); // a, b, c, d...
    q[qIdx].options.push({ id: newId, text: '', correct: false });
    setQuestions(q);
  };

  const removeOption = (qIdx, oIdx) => {
    const q = [...questions];
    if (q[qIdx].options.length > 1) {
      q[qIdx].options = q[qIdx].options.filter((_, i) => i !== oIdx);
      setQuestions(q);
    }
  };

  const updateOption = (qIdx, oIdx, field, value) => {
    const q = [...questions];
    q[qIdx].options[oIdx] = { ...q[qIdx].options[oIdx], [field]: value };
    setQuestions(q);
  };

  const toggleCorrectOption = (qIdx, oIdx) => {
    const q = [...questions];
    if (q[qIdx].type === QUESTION_TYPES.SINGLE) {
      // Single choice - only one correct
      q[qIdx].options = q[qIdx].options.map((o, i) => ({ ...o, correct: i === oIdx }));
    } else {
      // Multiple choice - toggle
      q[qIdx].options[oIdx].correct = !q[qIdx].options[oIdx].correct;
    }
    setQuestions(q);
  };

  // Results management
  const addResult = () => {
    setResults([...results, { min_score: 0, max_score: 0, title: '', description: '' }]);
  };

  const removeResult = (idx) => {
    setResults(results.filter((_, i) => i !== idx));
  };

  const updateResult = (idx, field, value) => {
    const r = [...results];
    r[idx] = { ...r[idx], [field]: value };
    setResults(r);
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
          <Button variant="ghost" size="icon" onClick={() => navigate('/admin/quizzes')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{isNew ? 'Новый квиз' : quiz.title || 'Редактирование'}</h1>
            {!isNew && <p className="text-sm text-muted-foreground">/{quiz.slug}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isNew && quiz.slug && (
            <Button variant="outline" onClick={() => window.open(`/quizzes/${quiz.slug}`, '_blank')}>
              <ExternalLink className="mr-2 h-4 w-4" />Предпросмотр
            </Button>
          )}
          <Select value={quiz.status} onValueChange={(v) => setQuiz(p => ({ ...p, status: v }))}>
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="draft">Черновик</SelectItem>
              <SelectItem value="published">Опубликовать</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={handleSave} disabled={saving}>
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
          <TabsTrigger value="questions">Вопросы ({questions.length})</TabsTrigger>
          <TabsTrigger value="results">Результаты ({results.length})</TabsTrigger>
        </TabsList>

        {/* Main Tab */}
        <TabsContent value="main" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Основная информация</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Название квиза</Label>
                <Input
                  value={quiz.title}
                  onChange={(e) => setQuiz(p => ({
                    ...p,
                    title: e.target.value,
                    slug: p.slug || generateSlug(e.target.value)
                  }))}
                  placeholder="Угадай команду по шутке"
                />
              </div>
              <div className="space-y-2">
                <Label>URL (slug)</Label>
                <Input
                  value={quiz.slug}
                  onChange={(e) => setQuiz(p => ({ ...p, slug: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Описание</Label>
                <Textarea
                  value={quiz.description || ''}
                  onChange={(e) => setQuiz(p => ({ ...p, description: e.target.value }))}
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <Label>Теги</Label>
                <TagSelector
                  value={quiz.tags}
                  onChange={(tags) => setQuiz(p => ({ ...p, tags }))}
                  placeholder="Выберите или добавьте тег..."
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Questions Tab */}
        <TabsContent value="questions" className="space-y-4">
          {questions.map((q, qIdx) => (
            <Card key={q.id || qIdx}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <div className="flex items-center gap-2">
                  <GripVertical className="h-4 w-4 text-muted-foreground" />
                  <CardTitle className="text-base">Вопрос {qIdx + 1}</CardTitle>
                  <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                    {q.type === QUESTION_TYPES.TEXT ? 'Текстовый ответ' : 
                     q.type === QUESTION_TYPES.MULTIPLE ? 'Несколько ответов' : 'Один ответ'}
                  </span>
                </div>
                <Button variant="ghost" size="icon" onClick={() => removeQuestion(qIdx)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Question Type Selector */}
                <div className="space-y-2">
                  <Label>Тип вопроса</Label>
                  <Select
                    value={q.type || QUESTION_TYPES.SINGLE}
                    onValueChange={(v) => {
                      const newQ = { ...q, type: v };
                      if (v === QUESTION_TYPES.TEXT) {
                        delete newQ.options;
                        newQ.correct_answer = '';
                      } else if (!newQ.options) {
                        newQ.options = [{ id: 'a', text: '', correct: false }];
                        delete newQ.correct_answer;
                      }
                      updateQuestion(qIdx, 'type', v);
                      if (v === QUESTION_TYPES.TEXT && q.options) {
                        const updated = [...questions];
                        delete updated[qIdx].options;
                        updated[qIdx].correct_answer = '';
                        setQuestions(updated);
                      } else if (v !== QUESTION_TYPES.TEXT && !q.options) {
                        const updated = [...questions];
                        updated[qIdx].options = [{ id: 'a', text: '', correct: false }];
                        delete updated[qIdx].correct_answer;
                        setQuestions(updated);
                      }
                    }}
                  >
                    <SelectTrigger className="w-[200px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={QUESTION_TYPES.SINGLE}>Один правильный ответ</SelectItem>
                      <SelectItem value={QUESTION_TYPES.MULTIPLE}>Несколько правильных</SelectItem>
                      <SelectItem value={QUESTION_TYPES.TEXT}>Текстовый ответ</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Question Text */}
                <div className="space-y-2">
                  <Label>Текст вопроса</Label>
                  <Input
                    value={q.question}
                    onChange={(e) => updateQuestion(qIdx, 'question', e.target.value)}
                    placeholder="Введите вопрос..."
                  />
                </div>

                {/* Text Answer Input */}
                {q.type === QUESTION_TYPES.TEXT ? (
                  <div className="space-y-2">
                    <Label>Правильный ответ</Label>
                    <Input
                      value={q.correct_answer || ''}
                      onChange={(e) => updateQuestion(qIdx, 'correct_answer', e.target.value)}
                      placeholder="Введите правильный ответ..."
                    />
                    <p className="text-xs text-muted-foreground">
                      Ответ пользователя будет сравниваться с этим значением (без учёта регистра)
                    </p>
                  </div>
                ) : (
                  /* Options for choice questions */
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Варианты ответов</Label>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => addOption(qIdx)}
                      >
                        <Plus className="h-3 w-3 mr-1" /> Добавить вариант
                      </Button>
                    </div>
                    <div className="space-y-2">
                      {q.options?.map((o, oIdx) => (
                        <div key={o.id || oIdx} className="flex items-center gap-2">
                          <Checkbox
                            checked={o.correct}
                            onCheckedChange={() => toggleCorrectOption(qIdx, oIdx)}
                          />
                          <Input
                            value={o.text}
                            onChange={(e) => updateOption(qIdx, oIdx, 'text', e.target.value)}
                            placeholder={`Вариант ${String.fromCharCode(65 + oIdx)}`}
                            className="flex-1"
                          />
                          {q.options.length > 1 && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={() => removeOption(qIdx, oIdx)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Отметьте галочкой правильный(е) вариант(ы) ответа
                    </p>
                  </div>
                )}

                {/* Explanation */}
                <div className="space-y-2">
                  <Label>Объяснение (опционально)</Label>
                  <Input
                    value={q.explanation || ''}
                    onChange={(e) => updateQuestion(qIdx, 'explanation', e.target.value)}
                    placeholder="Пояснение к правильному ответу..."
                  />
                </div>
              </CardContent>
            </Card>
          ))}

          {/* Add Question Buttons */}
          <div className="flex gap-2">
            <Button onClick={() => addQuestion(QUESTION_TYPES.SINGLE)} className="flex-1">
              <Plus className="mr-2 h-4 w-4" /> С выбором ответа
            </Button>
            <Button onClick={() => addQuestion(QUESTION_TYPES.TEXT)} variant="outline" className="flex-1">
              <Plus className="mr-2 h-4 w-4" /> С текстовым ответом
            </Button>
          </div>
        </TabsContent>

        {/* Results Tab */}
        <TabsContent value="results" className="space-y-4">
          {results.map((r, rIdx) => (
            <Card key={rIdx}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-base">Результат {rIdx + 1}</CardTitle>
                <Button variant="ghost" size="icon" onClick={() => removeResult(rIdx)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Мин. балл</Label>
                    <Input
                      type="number"
                      value={r.min_score}
                      onChange={(e) => updateResult(rIdx, 'min_score', parseInt(e.target.value) || 0)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Макс. балл</Label>
                    <Input
                      type="number"
                      value={r.max_score}
                      onChange={(e) => updateResult(rIdx, 'max_score', parseInt(e.target.value) || 0)}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Заголовок</Label>
                  <Input
                    value={r.title}
                    onChange={(e) => updateResult(rIdx, 'title', e.target.value)}
                    placeholder="Знаток КВН"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Описание</Label>
                  <Textarea
                    value={r.description}
                    onChange={(e) => updateResult(rIdx, 'description', e.target.value)}
                    rows={2}
                  />
                </div>
              </CardContent>
            </Card>
          ))}
          <Button onClick={addResult} className="w-full">
            <Plus className="mr-2 h-4 w-4" /> Добавить результат
          </Button>
        </TabsContent>
      </Tabs>
    </div>
  );
}
