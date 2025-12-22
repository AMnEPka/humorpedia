import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Loader2, ChevronLeft, ChevronRight, HelpCircle, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import publicApi from '../utils/api';

export default function QuizzesListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [quizzes, setQuizzes] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  
  const page = parseInt(searchParams.get('page') || '1');
  const limit = 12;

  useEffect(() => {
    const fetchQuizzes = async () => {
      setLoading(true);
      try {
        const res = await publicApi.getQuizzes({ 
          page, 
          limit,
          sort: '-published_at' 
        });
        setQuizzes(res.data.items || []);
        setTotal(res.data.total || 0);
      } catch (err) {
        console.error('Error fetching quizzes:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchQuizzes();
  }, [page]);

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm text-gray-500">
          <li><Link to="/" className="hover:text-blue-600">Главная</Link></li>
          <li>/</li>
          <li className="text-gray-900">Квизы</li>
        </ol>
      </nav>

      <h1 className="text-3xl font-bold text-gray-900 mb-8">Квизы и тесты</h1>

      {loading ? (
        <div className="flex items-center justify-center min-h-[40vh]">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      ) : quizzes.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <HelpCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>Нет квизов</p>
        </div>
      ) : (
        <>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {quizzes.map((quiz) => (
              <Link key={quiz.id} to={`/quizzes/${quiz.slug}`}>
                <Card className="overflow-hidden hover:shadow-lg transition-all group h-full hover:-translate-y-1">
                  <div className="aspect-video bg-gradient-to-br from-purple-500 to-blue-600 relative overflow-hidden">
                    {quiz.image ? (
                      <img 
                        src={quiz.image} 
                        alt={quiz.title}
                        className="w-full h-full object-cover opacity-80"
                      />
                    ) : null}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="w-16 h-16 bg-white/20 backdrop-blur rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                        <Play className="h-8 w-8 text-white fill-white" />
                      </div>
                    </div>
                  </div>
                  <CardContent className="p-5">
                    <h3 className="font-semibold text-lg text-gray-900 group-hover:text-blue-600 transition-colors">
                      {quiz.title}
                    </h3>
                    {quiz.excerpt && (
                      <p className="text-sm text-gray-600 mt-2 line-clamp-2">{quiz.excerpt}</p>
                    )}
                    <div className="flex items-center gap-2 mt-3">
                      {quiz.questions_count && (
                        <Badge variant="secondary">
                          {quiz.questions_count} вопросов
                        </Badge>
                      )}
                      {quiz.plays_count > 0 && (
                        <span className="text-xs text-gray-500">
                          Пройдено {quiz.plays_count} раз
                        </span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-8">
              <Button
                variant="outline"
                size="icon"
                disabled={page <= 1}
                onClick={() => setSearchParams({ page: page - 1 })}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="px-4 py-2 text-sm">
                Страница {page} из {totalPages}
              </span>
              <Button
                variant="outline"
                size="icon"
                disabled={page >= totalPages}
                onClick={() => setSearchParams({ page: page + 1 })}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
