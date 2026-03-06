import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { usePageTitle } from '@/utils/pageTitle';
import { AuthProvider, useAuth } from './admin/hooks/useAuth';
import AdminLayout from './admin/components/AdminLayout';
import LoginPage from './admin/pages/LoginPage';
import DashboardPage from './admin/pages/DashboardPage';
// Admin - People
import AdminPeopleListPage from './admin/pages/PeopleListPage';
import PersonEditPage from './admin/pages/PersonEditPage';
// Admin - Teams
import AdminTeamsListPage from './admin/pages/TeamsListPage';
import TeamEditPage from './admin/pages/TeamEditPage';
// Admin - Shows
import AdminShowsListPage from './admin/pages/ShowsListPage';
import ShowEditPage from './admin/pages/ShowEditPage';
// Admin - KVN
import KVNListPage from './admin/pages/KVNListPage';
import KVNEditPage from './admin/pages/KVNEditPage';
// Admin - Articles
import AdminArticlesListPage from './admin/pages/ArticlesListPage';
import ArticleEditPage from './admin/pages/ArticleEditPage';
// Admin - News
import AdminNewsListPage from './admin/pages/NewsListPage';
import NewsEditPage from './admin/pages/NewsEditPage';
// Admin - Quizzes
import AdminQuizzesListPage from './admin/pages/QuizzesListPage';
import QuizEditPage from './admin/pages/QuizEditPage';
// Admin - Wiki
import WikiListPage from './admin/pages/WikiListPage';
import WikiEditPage from './admin/pages/WikiEditPage';
// Admin - Cities (Geography)
import CitiesListPage from './admin/pages/CitiesListPage';
import CityEditPage from './admin/pages/CityEditPage';
// Admin - Sections
import SectionsListPage from './admin/pages/SectionsListPage';
import SectionEditPage from './admin/pages/SectionEditPage';
// Admin - Management
import MediaPage from './admin/pages/MediaPage';
import TagsPage from './admin/pages/TagsPage';
import CommentsPage from './admin/pages/CommentsPage';
import UsersPage from './admin/pages/UsersPage';
import TemplatesPage from './admin/pages/TemplatesPage';
import TemplateEditPage from './admin/pages/TemplateEditPage';
import MongoAdminPage from './admin/pages/MongoAdminPage';

// Public pages
import PublicLayout from './public/components/Layout';
import HomePage from './public/pages/HomePage';
import NewsListPage from './public/pages/NewsListPage';
import NewsDetailPage from './public/pages/NewsDetailPage';
import ArticlesListPage from './public/pages/ArticlesListPage';
import ArticleDetailPage from './public/pages/ArticleDetailPage';
import PeopleListPage from './public/pages/PeopleListPage';
import PersonDetailPage from './public/pages/PersonDetailPage';
import TeamsListPage from './public/pages/TeamsListPage';
import TeamDetailPage from './public/pages/TeamDetailPage';
import ShowsListPage from './public/pages/ShowsListPage';
import ShowDetailPage from './public/pages/ShowDetailPage';
import QuizzesListPage from './public/pages/QuizzesListPage';
import QuizDetailPage from './public/pages/QuizDetailPage';
import ContactsPage from './public/pages/ContactsPage';
import PolicyPage from './public/pages/PolicyPage';
import SectionDetailPage from './public/pages/SectionDetailPage';
import SearchPage from './public/pages/SearchPage';
import TagSearchPage from './public/pages/TagSearchPage';
import CitiesListPagePublic from './public/pages/CitiesListPage';
import CityDetailPage from './public/pages/CityDetailPage';
import JuryStatsPage from './public/pages/JuryStatsPage';

import { Loader2 } from 'lucide-react';
import '@/App.css';

function WithTitle({ title, children }) {
  usePageTitle(title);
  return children;
}

// Protected route wrapper for admin
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

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes with Layout */}
      <Route element={<PublicLayout />}>
        <Route path="/" element={<WithTitle title="Главная"><HomePage /></WithTitle>} />
        
        {/* News */}
        <Route path="/news" element={<WithTitle title="Новости"><NewsListPage /></WithTitle>} />
        <Route path="/news/:slug" element={<WithTitle title="Новость"><NewsDetailPage /></WithTitle>} />
        
        {/* Articles */}
        <Route path="/articles" element={<WithTitle title="Статьи"><ArticlesListPage /></WithTitle>} />
        <Route path="/articles/:slug" element={<WithTitle title="Статья"><ArticleDetailPage /></WithTitle>} />
        
        {/* People */}
        <Route path="/people" element={<WithTitle title="Люди"><PeopleListPage /></WithTitle>} />
        <Route path="/people/:slug" element={<WithTitle title="Человек"><PersonDetailPage /></WithTitle>} />
        
        {/* Teams with categories */}
        <Route path="/teams" element={<WithTitle title="Команды"><Navigate to="/kvn/teams" replace /></WithTitle>} />
        <Route path="/teams/:category" element={<WithTitle title="Команды"><Navigate to="/kvn/teams" replace /></WithTitle>} />
        <Route path="/kvn/teams" element={<WithTitle title="Команды КВН"><TeamsListPage /></WithTitle>} />
        <Route path="/kvn/teams/:slug" element={<WithTitle title="Команда"><TeamDetailPage /></WithTitle>} />
        
        {/* Shows */}
        <Route path="/shows" element={<WithTitle title="Шоу"><ShowsListPage /></WithTitle>} />
        <Route path="/shows/:slug" element={<WithTitle title="Шоу"><ShowDetailPage /></WithTitle>} />
        <Route path="/shows/:parentSlug/:childSlug" element={<WithTitle title="Шоу"><ShowDetailPage /></WithTitle>} />
        <Route path="/shows/:parentSlug/:childSlug/:grandchildSlug" element={<WithTitle title="Шоу"><ShowDetailPage /></WithTitle>} />
        <Route path="/shows/:parentSlug/:childSlug/:grandchildSlug/:greatGrandchildSlug" element={<WithTitle title="Шоу"><ShowDetailPage /></WithTitle>} />
        
        {/* Quizzes */}
        <Route path="/quizzes" element={<WithTitle title="Квизы"><QuizzesListPage /></WithTitle>} />
        <Route path="/quizzes/:slug" element={<WithTitle title="Квиз"><QuizDetailPage /></WithTitle>} />
        
        {/* Cities (Geography) */}
        <Route path="/city" element={<WithTitle title="География"><CitiesListPagePublic /></WithTitle>} />
        <Route path="/city/:slug" element={<WithTitle title="Город"><CityDetailPage /></WithTitle>} />
        
        {/* Static pages */}
        <Route path="/contacts" element={<WithTitle title="Контакты"><ContactsPage /></WithTitle>} />
        <Route path="/policy" element={<WithTitle title="Политика конфиденциальности"><PolicyPage /></WithTitle>} />
        
        {/* Search */}
        <Route path="/search" element={<WithTitle title="Поиск"><SearchPage /></WithTitle>} />
        <Route path="/tags/:tag" element={<WithTitle title="Тег"><TagSearchPage /></WithTitle>} />
        
        {/* KVN Jury Stats */}
        <Route path="/kvn/vl-kvn/vl-jury" element={<WithTitle title="Статистика жюри"><JuryStatsPage /></WithTitle>} />
        
        {/* Dynamic sections - catch-all for hierarchical URLs */}
        {/* SectionDetailPage автоматически определяет формат (старый/новый) по наличию season_data */}
        <Route path="/*" element={<WithTitle title="Раздел"><SectionDetailPage /></WithTitle>} />
      </Route>
      
      {/* Admin routes */}
      <Route path="/admin/login" element={<WithTitle title="Вход в админку"><LoginPage /></WithTitle>} />
      
      <Route path="/admin" element={<WithTitle title="Админка"><ProtectedRoute><DashboardPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - People */}
      <Route path="/admin/people" element={<WithTitle title="Админка: Люди"><ProtectedRoute><AdminPeopleListPage /></ProtectedRoute></WithTitle>} />
      <Route path="/admin/people/:id" element={<WithTitle title="Админка: Редактирование человека"><ProtectedRoute><PersonEditPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - Teams */}
      <Route path="/admin/teams" element={<WithTitle title="Админка: Команды"><ProtectedRoute><AdminTeamsListPage /></ProtectedRoute></WithTitle>} />
      <Route path="/admin/teams/:id" element={<WithTitle title="Админка: Редактирование команды"><ProtectedRoute><TeamEditPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - Shows */}
      <Route path="/admin/shows" element={<WithTitle title="Админка: Шоу"><ProtectedRoute><AdminShowsListPage /></ProtectedRoute></WithTitle>} />
      <Route path="/admin/shows/:id" element={<WithTitle title="Админка: Редактирование шоу"><ProtectedRoute><ShowEditPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - KVN */}
      <Route path="/admin/kvn" element={<WithTitle title="Админка: КВН"><ProtectedRoute><KVNListPage /></ProtectedRoute></WithTitle>} />
        <Route path="/admin/kvn/:id" element={<WithTitle title="Админка: Редактирование КВН"><ProtectedRoute><KVNEditPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - Articles */}
      <Route path="/admin/articles" element={<WithTitle title="Админка: Статьи"><ProtectedRoute><AdminArticlesListPage /></ProtectedRoute></WithTitle>} />
      <Route path="/admin/articles/:id" element={<WithTitle title="Админка: Редактирование статьи"><ProtectedRoute><ArticleEditPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - News */}
      <Route path="/admin/news" element={<WithTitle title="Админка: Новости"><ProtectedRoute><AdminNewsListPage /></ProtectedRoute></WithTitle>} />
      <Route path="/admin/news/:id" element={<WithTitle title="Админка: Редактирование новости"><ProtectedRoute><NewsEditPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - Quizzes */}
      <Route path="/admin/quizzes" element={<WithTitle title="Админка: Квизы"><ProtectedRoute><AdminQuizzesListPage /></ProtectedRoute></WithTitle>} />
      <Route path="/admin/quizzes/:id" element={<WithTitle title="Админка: Редактирование квиза"><ProtectedRoute><QuizEditPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - Wiki */}
      <Route path="/admin/wiki" element={<WithTitle title="Админка: Вики"><ProtectedRoute><WikiListPage /></ProtectedRoute></WithTitle>} />
      <Route path="/admin/wiki/:id" element={<WithTitle title="Админка: Редактирование вики"><ProtectedRoute><WikiEditPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - Cities (Geography) */}
      <Route path="/admin/cities" element={<WithTitle title="Админка: Города"><ProtectedRoute><CitiesListPage /></ProtectedRoute></WithTitle>} />
      <Route path="/admin/cities/:id" element={<WithTitle title="Админка: Редактирование города"><ProtectedRoute><CityEditPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - Sections */}
      <Route path="/admin/sections" element={<WithTitle title="Админка: Разделы"><ProtectedRoute><SectionsListPage /></ProtectedRoute></WithTitle>} />
      <Route path="/admin/sections/:id" element={<WithTitle title="Админка: Редактирование раздела"><ProtectedRoute><SectionEditPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - Media */}
      <Route path="/admin/media" element={<WithTitle title="Админка: Медиа"><ProtectedRoute><MediaPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - Tags */}
      <Route path="/admin/tags" element={<WithTitle title="Админка: Теги"><ProtectedRoute><TagsPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - Comments */}
      <Route path="/admin/comments" element={<WithTitle title="Админка: Комментарии"><ProtectedRoute><CommentsPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - Users */}
      <Route path="/admin/users" element={<WithTitle title="Админка: Пользователи"><ProtectedRoute><UsersPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - Templates */}
      <Route path="/admin/templates" element={<WithTitle title="Админка: Шаблоны"><ProtectedRoute><TemplatesPage /></ProtectedRoute></WithTitle>} />
      <Route path="/admin/templates/:id" element={<WithTitle title="Админка: Редактирование шаблона"><ProtectedRoute><TemplateEditPage /></ProtectedRoute></WithTitle>} />
      
      {/* Admin - MongoDB */}
      <Route path="/admin/database" element={<WithTitle title="Админка: База данных"><ProtectedRoute><MongoAdminPage /></ProtectedRoute></WithTitle>} />
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
