import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './admin/hooks/useAuth';
import AdminLayout from './admin/components/AdminLayout';
import LoginPage from './admin/pages/LoginPage';
import DashboardPage from './admin/pages/DashboardPage';
// People
import PeopleListPage from './admin/pages/PeopleListPage';
import PersonEditPage from './admin/pages/PersonEditPage';
// Teams
import TeamsListPage from './admin/pages/TeamsListPage';
import TeamEditPage from './admin/pages/TeamEditPage';
// Shows
import ShowsListPage from './admin/pages/ShowsListPage';
import ShowEditPage from './admin/pages/ShowEditPage';
// Articles
import ArticlesListPage from './admin/pages/ArticlesListPage';
import ArticleEditPage from './admin/pages/ArticleEditPage';
// News
import NewsListPage from './admin/pages/NewsListPage';
import NewsEditPage from './admin/pages/NewsEditPage';
// Quizzes
import QuizzesListPage from './admin/pages/QuizzesListPage';
import QuizEditPage from './admin/pages/QuizEditPage';
// Wiki
import WikiListPage from './admin/pages/WikiListPage';
import WikiEditPage from './admin/pages/WikiEditPage';
// Management
import MediaPage from './admin/pages/MediaPage';
import TagsPage from './admin/pages/TagsPage';
import CommentsPage from './admin/pages/CommentsPage';
import UsersPage from './admin/pages/UsersPage';
import TemplatesPage from './admin/pages/TemplatesPage';

import { Loader2 } from 'lucide-react';
import '@/App.css';

// Protected route wrapper
function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/admin/login" replace />;
  }

  return <AdminLayout>{children}</AdminLayout>;
}

// Placeholder pages for content types not yet implemented
function PlaceholderPage({ title }) {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">{title}</h1>
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
        <p className="text-yellow-800">Эта страница в разработке</p>
      </div>
    </div>
  );
}

// Public home page (placeholder)
function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <div className="max-w-4xl mx-auto px-4 py-16 text-center">
        <h1 className="text-5xl font-bold mb-4">Humorpedia</h1>
        <p className="text-xl text-gray-600 mb-8">
          Энциклопедия российского юмора и КВН
        </p>
        <a
          href="/admin"
          className="inline-flex items-center px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity"
        >
          Войти в админ-панель
        </a>
      </div>
    </div>
  );
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<HomePage />} />
      
      {/* Admin routes */}
      <Route path="/admin/login" element={<LoginPage />} />
      
      <Route path="/admin" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      
      {/* People */}
      <Route path="/admin/people" element={<ProtectedRoute><PeopleListPage /></ProtectedRoute>} />
      <Route path="/admin/people/:id" element={<ProtectedRoute><PersonEditPage /></ProtectedRoute>} />
      
      {/* Teams */}
      <Route path="/admin/teams" element={<ProtectedRoute><TeamsListPage /></ProtectedRoute>} />
      <Route path="/admin/teams/:id" element={<ProtectedRoute><TeamEditPage /></ProtectedRoute>} />
      
      {/* Shows */}
      <Route path="/admin/shows" element={<ProtectedRoute><PlaceholderPage title="Шоу" /></ProtectedRoute>} />
      <Route path="/admin/shows/:id" element={<ProtectedRoute><PlaceholderPage title="Редактирование шоу" /></ProtectedRoute>} />
      
      {/* Articles */}
      <Route path="/admin/articles" element={<ProtectedRoute><PlaceholderPage title="Статьи" /></ProtectedRoute>} />
      <Route path="/admin/articles/:id" element={<ProtectedRoute><PlaceholderPage title="Редактирование статьи" /></ProtectedRoute>} />
      
      {/* News */}
      <Route path="/admin/news" element={<ProtectedRoute><PlaceholderPage title="Новости" /></ProtectedRoute>} />
      <Route path="/admin/news/:id" element={<ProtectedRoute><PlaceholderPage title="Редактирование новости" /></ProtectedRoute>} />
      
      {/* Quizzes */}
      <Route path="/admin/quizzes" element={<ProtectedRoute><PlaceholderPage title="Квизы" /></ProtectedRoute>} />
      <Route path="/admin/quizzes/:id" element={<ProtectedRoute><PlaceholderPage title="Редактирование квиза" /></ProtectedRoute>} />
      
      {/* Wiki */}
      <Route path="/admin/wiki" element={<ProtectedRoute><PlaceholderPage title="Вики" /></ProtectedRoute>} />
      <Route path="/admin/wiki/:id" element={<ProtectedRoute><PlaceholderPage title="Редактирование вики" /></ProtectedRoute>} />
      
      {/* Media */}
      <Route path="/admin/media" element={<ProtectedRoute><PlaceholderPage title="Медиабиблиотека" /></ProtectedRoute>} />
      
      {/* Tags */}
      <Route path="/admin/tags" element={<ProtectedRoute><PlaceholderPage title="Теги" /></ProtectedRoute>} />
      
      {/* Comments */}
      <Route path="/admin/comments" element={<ProtectedRoute><PlaceholderPage title="Комментарии" /></ProtectedRoute>} />
      
      {/* Users */}
      <Route path="/admin/users" element={<ProtectedRoute><PlaceholderPage title="Пользователи" /></ProtectedRoute>} />
      
      {/* Templates */}
      <Route path="/admin/templates" element={<ProtectedRoute><PlaceholderPage title="Шаблоны" /></ProtectedRoute>} />
      
      {/* Catch all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
