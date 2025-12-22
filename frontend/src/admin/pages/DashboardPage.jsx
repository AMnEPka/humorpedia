import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { statsApi, commentsApi } from '../utils/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Users, UsersRound, Tv, FileText, Newspaper, 
  HelpCircle, BookOpen, MessageSquare, Tags, Eye,
  Plus, ArrowRight, Loader2
} from 'lucide-react';

const statCards = [
  { key: 'people', label: 'Люди', icon: Users, path: '/admin/people', color: 'bg-blue-500' },
  { key: 'teams', label: 'Команды', icon: UsersRound, path: '/admin/teams', color: 'bg-green-500' },
  { key: 'shows', label: 'Шоу', icon: Tv, path: '/admin/shows', color: 'bg-purple-500' },
  { key: 'articles', label: 'Статьи', icon: FileText, path: '/admin/articles', color: 'bg-orange-500' },
  { key: 'news', label: 'Новости', icon: Newspaper, path: '/admin/news', color: 'bg-red-500' },
  { key: 'quizzes', label: 'Квизы', icon: HelpCircle, path: '/admin/quizzes', color: 'bg-pink-500' },
  { key: 'wiki', label: 'Вики', icon: BookOpen, path: '/admin/wiki', color: 'bg-teal-500' },
  { key: 'users', label: 'Пользователи', icon: Users, path: '/admin/users', color: 'bg-indigo-500' },
  { key: 'comments', label: 'Комментарии', icon: MessageSquare, path: '/admin/comments', color: 'bg-yellow-500' },
  { key: 'tags', label: 'Теги', icon: Tags, path: '/admin/tags', color: 'bg-gray-500' },
];

const quickActions = [
  { label: 'Добавить человека', path: '/admin/people/new', icon: Users },
  { label: 'Добавить команду', path: '/admin/teams/new', icon: UsersRound },
  { label: 'Добавить статью', path: '/admin/articles/new', icon: FileText },
  { label: 'Добавить новость', path: '/admin/news/new', icon: Newspaper },
];

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [pendingComments, setPendingComments] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, commentsRes] = await Promise.all([
          statsApi.getStats(),
          commentsApi.listPending({ limit: 1 }).catch(() => ({ data: { total: 0 } }))
        ]);
        setStats(statsRes.data);
        setPendingComments(commentsRes.data?.total || 0);
      } catch (error) {
        console.error('Error fetching stats:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Панель управления</h1>
        <p className="text-muted-foreground mt-1">Добро пожаловать в админ-панель Humorpedia</p>
      </div>

      {/* Quick actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Быстрые действия</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action) => {
              const Icon = action.icon;
              return (
                <Button key={action.path} variant="outline" asChild>
                  <Link to={action.path}>
                    <Plus className="mr-2 h-4 w-4" />
                    {action.label}
                  </Link>
                </Button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Pending moderation */}
      {pendingComments > 0 && (
        <Card className="border-yellow-200 bg-yellow-50">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <MessageSquare className="h-5 w-5 text-yellow-600" />
                <span className="font-medium text-yellow-800">
                  {pendingComments} комментари{pendingComments === 1 ? 'й' : pendingComments < 5 ? 'я' : 'ев'} ожида{pendingComments === 1 ? 'ет' : 'ют'} модерации
                </span>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link to="/admin/comments?pending=true">
                  Проверить <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {statCards.map((card) => {
          const Icon = card.icon;
          const value = stats?.[card.key] || 0;

          return (
            <Link key={card.key} to={card.path}>
              <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-2xl font-bold">{value}</p>
                      <p className="text-sm text-muted-foreground">{card.label}</p>
                    </div>
                    <div className={`p-3 rounded-full ${card.color} text-white`}>
                      <Icon className="h-5 w-5" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>

      {/* Info */}
      <Card>
        <CardHeader>
          <CardTitle>О системе</CardTitle>
          <CardDescription>Humorpedia CMS v1.0</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground space-y-1">
            <p>• Модульная система страниц</p>
            <p>• Универсальные команды для любых шоу</p>
            <p>• Перекрестные ссылки между контентом</p>
            <p>• SEO-оптимизация</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
