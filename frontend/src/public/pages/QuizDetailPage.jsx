import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { publicApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Loader2, CheckCircle2, XCircle, ArrowRight, RotateCcw, Share2, Trophy } from 'lucide-react';

export default function QuizDetailPage() {
  const { slug } = useParams();
  const [quiz, setQuiz] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Quiz state
  const [questions, setQuestions] = useState([]);
  const [results, setResults] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [answers, setAnswers] = useState({});
  const [textAnswer, setTextAnswer] = useState('');
  const [showResult, setShowResult] = useState(false);
  const [score, setScore] = useState(0);
  const [quizStarted, setQuizStarted] = useState(false);
  const [finalAnswers, setFinalAnswers] = useState({}); // Store final answers for results display

  useEffect(() => {
    publicApi.getQuiz(slug)
      .then(res => {
        setQuiz(res.data);
        const qModule = res.data.modules?.find(m => m.type === 'quiz_questions');
        const rModule = res.data.modules?.find(m => m.type === 'quiz_results');
        if (qModule?.data?.questions) setQuestions(qModule.data.questions);
        if (rModule?.data?.results) setResults(rModule.data.results);
      })
      .catch(() => setError('Квиз не найден'))
      .finally(() => setLoading(false));
  }, [slug]);

  const currentQ = questions[currentQuestion];
  const progress = questions.length > 0 ? ((currentQuestion + 1) / questions.length) * 100 : 0;

  const handleSelectOption = (optionIdx) => {
    if (!currentQ) return;
    
    if (currentQ.type === 'multiple') {
      // Multiple selection
      const current = answers[currentQuestion] || [];
      const newAnswers = current.includes(optionIdx)
        ? current.filter(i => i !== optionIdx)
        : [...current, optionIdx];
      setAnswers({ ...answers, [currentQuestion]: newAnswers });
    } else {
      // Single selection
      setAnswers({ ...answers, [currentQuestion]: optionIdx });
    }
  };

  const handleTextAnswer = () => {
    setAnswers({ ...answers, [currentQuestion]: textAnswer.trim() });
  };

  const isAnswered = () => {
    const answer = answers[currentQuestion];
    if (currentQ?.type === 'text') {
      return textAnswer.trim().length > 0 || (typeof answer === 'string' && answer.length > 0);
    }
    if (currentQ?.type === 'multiple') {
      return Array.isArray(answer) && answer.length > 0;
    }
    return answer !== undefined;
  };

  const handleNext = () => {
    // Save text answer if applicable
    let updatedAnswers = { ...answers };
    if (currentQ?.type === 'text' && textAnswer.trim()) {
      updatedAnswers[currentQuestion] = textAnswer.trim();
      setAnswers(updatedAnswers);
    }
    
    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion(currentQuestion + 1);
      setTextAnswer('');
    } else {
      // Calculate score with updated answers
      calculateScoreWithAnswers(updatedAnswers);
    }
  };

  const calculateScoreWithAnswers = (finalAns) => {
    let correct = 0;
    
    questions.forEach((q, idx) => {
      const answer = finalAns[idx];
      
      if (q.type === 'text') {
        const userAnswer = (typeof answer === 'string' ? answer : '').toLowerCase().trim();
        const correctAnswer = (q.correct_answer || '').toLowerCase().trim();
        if (userAnswer === correctAnswer) correct++;
      } else if (q.type === 'multiple') {
        const correctIndices = q.options
          .map((o, i) => o.correct ? i : -1)
          .filter(i => i !== -1);
        const userIndices = Array.isArray(answer) ? [...answer] : [];
        const sortedCorrect = [...correctIndices].sort();
        const sortedUser = [...userIndices].sort();
        if (JSON.stringify(sortedCorrect) === JSON.stringify(sortedUser)) {
          correct++;
        }
      } else {
        const correctIdx = q.options?.findIndex(o => o.correct);
        if (answer === correctIdx) correct++;
      }
    });
    
    setFinalAnswers(finalAns);
    setScore(correct);
    setShowResult(true);
  };

  const calculateScore = useCallback(() => {
    calculateScoreWithAnswers(answers);
  }, [questions, answers]);

  const getResultForScore = () => {
    const percentage = (score / questions.length) * 100;
    // Find matching result based on score percentage or raw score
    return results.find(r => {
      if (r.min_score <= score && r.max_score >= score) return true;
      if (r.min_score <= percentage && r.max_score >= percentage) return true;
      return false;
    }) || results[results.length - 1];
  };

  const restart = () => {
    setCurrentQuestion(0);
    setAnswers({});
    setFinalAnswers({});
    setTextAnswer('');
    setShowResult(false);
    setScore(0);
    setQuizStarted(false);
  };

  const share = () => {
    if (navigator.share) {
      navigator.share({
        title: quiz?.title,
        text: `Я прошёл квиз "${quiz?.title}" и набрал ${score} из ${questions.length}!`,
        url: window.location.href
      });
    } else {
      navigator.clipboard.writeText(window.location.href);
      alert('Ссылка скопирована!');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !quiz) {
    return (
      <div className="container max-w-2xl mx-auto py-12">
        <Alert variant="destructive">
          <AlertTitle>Ошибка</AlertTitle>
          <AlertDescription>{error || 'Квиз не найден'}</AlertDescription>
        </Alert>
        <Button asChild className="mt-4">
          <Link to="/quizzes">← К списку квизов</Link>
        </Button>
      </div>
    );
  }

  // Start screen
  if (!quizStarted) {
    return (
      <div className="container max-w-2xl mx-auto py-8 px-4">
        <Card className="overflow-hidden">
          {quiz.cover_image?.url && (
            <div className="h-48 bg-cover bg-center" style={{ backgroundImage: `url(${quiz.cover_image.url})` }} />
          )}
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">{quiz.title}</CardTitle>
            {quiz.description && (
              <CardDescription className="text-base mt-2">{quiz.description}</CardDescription>
            )}
          </CardHeader>
          <CardContent className="text-center space-y-4">
            <div className="flex justify-center gap-4 text-sm text-muted-foreground">
              <span>{questions.length} вопросов</span>
              {quiz.attempts_count > 0 && <span>Пройден {quiz.attempts_count} раз</span>}
            </div>
            {quiz.tags?.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2">
                {quiz.tags.map(tag => (
                  <Badge key={tag} variant="secondary">{tag}</Badge>
                ))}
              </div>
            )}
          </CardContent>
          <CardFooter className="justify-center pb-6">
            <Button size="lg" onClick={() => setQuizStarted(true)} disabled={questions.length === 0}>
              Начать квиз <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  // Result screen
  if (showResult) {
    const result = getResultForScore();
    const percentage = Math.round((score / questions.length) * 100);
    
    return (
      <div className="container max-w-2xl mx-auto py-8 px-4">
        <Card>
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center">
              <Trophy className="h-8 w-8 text-primary" />
            </div>
            <CardTitle className="text-2xl">
              {result?.title || 'Результат'}
            </CardTitle>
            <CardDescription className="text-lg mt-2">
              {result?.description || `Вы ответили правильно на ${score} из ${questions.length} вопросов`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="text-center">
              <div className="text-5xl font-bold text-primary">{percentage}%</div>
              <div className="text-muted-foreground mt-1">
                {score} из {questions.length} правильных ответов
              </div>
            </div>
            
            <Progress value={percentage} className="h-3" />
            
            {/* Show answers review */}
            <div className="space-y-3 pt-4 border-t">
              <h4 className="font-medium">Ваши ответы:</h4>
              {questions.map((q, idx) => {
                const answer = finalAnswers[idx];
                let isCorrect = false;
                let userAnswerText = '';
                let correctAnswerText = '';
                
                if (q.type === 'text') {
                  userAnswerText = answer || '(не отвечено)';
                  correctAnswerText = q.correct_answer;
                  isCorrect = (answer || '').toLowerCase().trim() === (q.correct_answer || '').toLowerCase().trim();
                } else {
                  const correctIdx = q.options?.findIndex(o => o.correct);
                  if (q.type === 'multiple') {
                    const correctIndices = q.options.map((o, i) => o.correct ? i : -1).filter(i => i !== -1);
                    userAnswerText = Array.isArray(answer) 
                      ? answer.map(i => q.options[i]?.text).join(', ') || '(не отвечено)'
                      : '(не отвечено)';
                    correctAnswerText = correctIndices.map(i => q.options[i]?.text).join(', ');
                    // Compare sorted copies
                    const sortedCorrect = [...correctIndices].sort();
                    const sortedUser = [...(answer || [])].sort();
                    isCorrect = JSON.stringify(sortedCorrect) === JSON.stringify(sortedUser);
                  } else {
                    userAnswerText = answer !== undefined ? q.options[answer]?.text : '(не отвечено)';
                    correctAnswerText = q.options[correctIdx]?.text;
                    isCorrect = answer === correctIdx;
                  }
                }
                
                return (
                  <div key={idx} className={`p-3 rounded-lg border ${isCorrect ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                    <div className="flex items-start gap-2">
                      {isCorrect ? (
                        <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                      ) : (
                        <XCircle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm">{q.question}</div>
                        <div className="text-sm mt-1">
                          <span className="text-muted-foreground">Ваш ответ: </span>
                          <span className={isCorrect ? 'text-green-700' : 'text-red-700'}>{userAnswerText}</span>
                        </div>
                        {!isCorrect && (
                          <div className="text-sm">
                            <span className="text-muted-foreground">Правильный: </span>
                            <span className="text-green-700">{correctAnswerText}</span>
                          </div>
                        )}
                        {q.explanation && (
                          <div className="text-xs text-muted-foreground mt-1 italic">{q.explanation}</div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
          <CardFooter className="flex gap-2 justify-center">
            <Button variant="outline" onClick={restart}>
              <RotateCcw className="mr-2 h-4 w-4" /> Пройти ещё раз
            </Button>
            <Button onClick={share}>
              <Share2 className="mr-2 h-4 w-4" /> Поделиться
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  // Question screen
  return (
    <div className="container max-w-2xl mx-auto py-8 px-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted-foreground">
              Вопрос {currentQuestion + 1} из {questions.length}
            </span>
            <Badge variant="outline">
              {currentQ?.type === 'text' ? 'Текстовый' : 
               currentQ?.type === 'multiple' ? 'Несколько' : 'Один ответ'}
            </Badge>
          </div>
          <Progress value={progress} className="h-2" />
          <CardTitle className="text-xl mt-4">{currentQ?.question}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {currentQ?.type === 'text' ? (
            <div className="space-y-2">
              <Input
                value={textAnswer}
                onChange={(e) => setTextAnswer(e.target.value)}
                placeholder="Введите ваш ответ..."
                className="text-lg"
                onKeyDown={(e) => e.key === 'Enter' && isAnswered() && handleNext()}
              />
            </div>
          ) : (
            currentQ?.options?.map((option, idx) => {
              const isSelected = currentQ.type === 'multiple'
                ? (answers[currentQuestion] || []).includes(idx)
                : answers[currentQuestion] === idx;
              
              return (
                <button
                  key={idx}
                  onClick={() => handleSelectOption(idx)}
                  className={`w-full p-4 text-left rounded-lg border-2 transition-all ${
                    isSelected 
                      ? 'border-primary bg-primary/5' 
                      : 'border-border hover:border-primary/50 hover:bg-muted/50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center font-medium ${
                      isSelected ? 'border-primary bg-primary text-primary-foreground' : 'border-muted-foreground'
                    }`}>
                      {String.fromCharCode(65 + idx)}
                    </div>
                    <span className="flex-1">{option.text}</span>
                    {isSelected && <CheckCircle2 className="h-5 w-5 text-primary" />}
                  </div>
                </button>
              );
            })
          )}
          
          {currentQ?.type === 'multiple' && (
            <p className="text-sm text-muted-foreground text-center">
              Выберите все правильные варианты
            </p>
          )}
        </CardContent>
        <CardFooter>
          <Button 
            onClick={handleNext} 
            disabled={!isAnswered()}
            className="w-full"
            size="lg"
          >
            {currentQuestion < questions.length - 1 ? (
              <>Далее <ArrowRight className="ml-2 h-4 w-4" /></>
            ) : (
              <>Завершить <CheckCircle2 className="ml-2 h-4 w-4" /></>
            )}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
