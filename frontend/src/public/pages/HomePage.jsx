import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Sparkles, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import publicApi from '../utils/api';
import NewsCard from '../components/NewsCard';
import ArticleCard from '../components/ArticleCard';

export default function HomePage() {
  const [news, setNews] = useState([]);
  const [articles, setArticles] = useState([]);
  const [randomArticle, setRandomArticle] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [newsRes, articlesRes] = await Promise.all([
          publicApi.getNews({ limit: 10, sort: '-published_at' }),
          publicApi.getPopularArticles(5),
        ]);
        setNews(newsRes.data.items || []);
        setArticles(articlesRes.data.items || []);
        
        // Get random article
        try {
          const randomRes = await publicApi.getRandomArticle();
          setRandomArticle(randomRes.data);
        } catch (e) {
          // Random article is optional
        }
      } catch (err) {
        console.error('Error fetching data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Hero Section */}
      <section className="mb-12">
        <div className="bg-gradient-to-r from-blue-600 to-blue-800 rounded-2xl p-8 md:p-12 text-white">
          <h1 className="text-3xl md:text-4xl font-bold mb-4">
            Добро пожаловать в Humorpedia
          </h1>
          <p className="text-blue-100 text-lg max-w-2xl mb-6">
            Энциклопедия юмора — всё о КВН, комедийных шоу, командах и людях, 
            которые дарят нам смех.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button asChild variant="secondary" size="lg">
              <Link to="/kvn/teams">Команды КВН</Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="bg-transparent border-white text-white hover:bg-white/10">
              <Link to="/people">Люди</Link>
            </Button>
          </div>
        </div>
      </section>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* News Section */}
        <section className="lg:col-span-1">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Новости</h2>
            <Button asChild variant="ghost" size="sm">
              <Link to="/news">
                Все <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
          </div>
          <Card>
            <CardContent className="p-2">
              {news.length === 0 ? (
                <p className="text-center py-8 text-gray-500">Нет новостей</p>
              ) : (
                <div className="divide-y">
                  {news.map((item) => (
                    <NewsCard key={item.id} news={item} compact />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        {/* Articles Section */}
        <section className="lg:col-span-2">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Популярные статьи</h2>
            <Button asChild variant="ghost" size="sm">
              <Link to="/articles">
                Все статьи <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
          </div>
          
          {articles.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-gray-500">
                Нет статей
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-6">
              {articles.slice(0, 1).map((article) => (
                <ArticleCard key={article.id} article={article} featured />
              ))}
              <div className="grid md:grid-cols-2 gap-6">
                {articles.slice(1).map((article) => (
                  <ArticleCard key={article.id} article={article} />
                ))}
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Random Article Section */}
      {randomArticle && (
        <section className="mt-12">
          <div className="flex items-center gap-2 mb-6">
            <Sparkles className="h-6 w-6 text-amber-500" />
            <h2 className="text-2xl font-bold text-gray-900">Случайная статья</h2>
          </div>
          <ArticleCard article={randomArticle} featured />
        </section>
      )}
    </div>
  );
}
