import React, { Suspense, useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigationType } from 'react-router-dom';
import { usePageTitle } from '@/utils/pageTitle';
import { AuthProvider, useAuth } from './admin/hooks/useAuth';

import { Loader2 } from 'lucide-react';
import '@/App.css';

// ─── Спиннер для Suspense ─────────────────────────────────────────────────────
function LazyFallback() {
  return (
    <div className="min-h-[40vh] flex items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
    </div>
  );
}

// ─── Public pages: синхронные (критический путь, грузятся сразу) ───────────────
import PublicLayout from './public/components/Layout';
import HomePage from './public/pages/HomePage';
import SectionDetailPage from './public/pages/SectionDetailPage';

// ─── Public pages: lazy (реже используются, грузятся по запросу) ───────────────
const NewsListPage = React.lazy(() => import('./public/pages/NewsListPage'));
const NewsDetailPage = React.lazy(() => import('./public/pages/NewsDetailPage'));
const ArticlesListPage = React.lazy(() => import('./public/pages/ArticlesListPage'));
const ArticleDetailPage = React.lazy(() => import('./public/pages/ArticleDetailPage'));
const PeopleListPage = React.lazy(() => import('./public/pages/PeopleListPage'));
const PersonDetailPage = React.lazy(() => import('./public/pages/PersonDetailPage'));
const TeamsListPage = React.lazy(() => import('./public/pages/TeamsListPage'));
const TeamDetailPage = React.lazy(() => import('./public/pages/TeamDetailPage'));
const ShowsListPage = React.lazy(() => import('./public/pages/ShowsListPage'));
const ShowDetailPage = React.lazy(() => import('./public/pages/ShowDetailPage'));
const QuizzesListPage = React.lazy(() => import('./public/pages/QuizzesListPage'));
const QuizDetailPage = React.lazy(() => import('./public/pages/QuizDetailPage'));
const ContactsPage = React.lazy(() => import('./public/pages/ContactsPage'));
const PolicyPage = React.lazy(() => import('./public/pages/PolicyPage'));
const SearchPage = React.lazy(() => import('./public/pages/SearchPage'));
const TagSearchPage = React.lazy(() => import('./public/pages/TagSearchPage'));
const CitiesListPagePublic = React.lazy(() => import('./public/pages/CitiesListPage'));
const CityDetailPage = React.lazy(() => import('./public/pages/CityDetailPage'));
const JuryStatsPage = React.lazy(() => import('./public/pages/JuryStatsPage'));

// ─── Admin pages: ВСЕ lazy (отдельный чанк, публичные пользователи не грузят) ─
const AdminLayout = React.lazy(() => import('./admin/components/AdminLayout'));
const LoginPage = React.lazy(() => import('./admin/pages/LoginPage'));
const DashboardPage = React.lazy(() => import('./admin/pages/DashboardPage'));
const AdminPeopleListPage = React.lazy(() => import('./admin/pages/PeopleListPage'));
const PersonEditPage = React.lazy(() => import('./admin/pages/PersonEditPage'));
const AdminTeamsListPage = React.lazy(() => import('./admin/pages/TeamsListPage'));
const TeamEditPage = React.lazy(() => import('./admin/pages/TeamEditPage'));
const AdminShowsListPage = React.lazy(() => import('./admin/pages/ShowsListPage'));
const ShowEditPage = React.lazy(() => import('./admin/pages/ShowEditPage'));
const KVNListPage = React.lazy(() => import('./admin/pages/KVNListPage'));
const KVNEditPage = React.lazy(() => import('./admin/pages/KVNEditPage'));
const AdminArticlesListPage = React.lazy(() => import('./admin/pages/ArticlesListPage'));
const ArticleEditPage = React.lazy(() => import('./admin/pages/ArticleEditPage'));
const AdminNewsListPage = React.lazy(() => import('./admin/pages/NewsListPage'));
const NewsEditPage = React.lazy(() => import('./admin/pages/NewsEditPage'));
const AdminQuizzesListPage = React.lazy(() => import('./admin/pages/QuizzesListPage'));
const QuizEditPage = React.lazy(() => import('./admin/pages/QuizEditPage'));
const WikiListPage = React.lazy(() => import('./admin/pages/WikiListPage'));
const WikiEditPage = React.lazy(() => import('./admin/pages/WikiEditPage'));
const CitiesListPage = React.lazy(() => import('./admin/pages/CitiesListPage'));
const CityEditPage = React.lazy(() => import('./admin/pages/CityEditPage'));
const SectionsListPage = React.lazy(() => import('./admin/pages/SectionsListPage'));
const SectionEditPage = React.lazy(() => import('./admin/pages/SectionEditPage'));
const MediaPage = React.lazy(() => import('./admin/pages/MediaPage'));
const TagsPage = React.lazy(() => import('./admin/pages/TagsPage'));
const CommentsPage = React.lazy(() => import('./admin/pages/CommentsPage'));
const UsersPage = React.lazy(() => import('./admin/pages/UsersPage'));
const TemplatesPage = React.lazy(() => import('./admin/pages/TemplatesPage'));
const TemplateEditPage = React.lazy(() => import('./admin/pages/TemplateEditPage'));
const MongoAdminPage = React.lazy(() => import('./admin/pages/MongoAdminPage'));


function ScrollRestoration() {
  const location = useLocation();
  const navigationType = useNavigationType();
  const isFirstRenderRef = useRef(true);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const storageKey = `scroll:${location.key || location.pathname || ''}`;

    // На самом первом рендере не трогаем скролл — даём браузеру самому
    // восстановить позицию при F5/перезагрузке.
    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
    } else if (navigationType === 'POP') {
      // Назад / вперёд по истории — восстанавливаем сохранённую позицию
      const stored = sessionStorage.getItem(storageKey);
      const y = stored !== null ? Number(stored) : 0;
      window.scrollTo(0, Number.isFinite(y) ? y : 0);
    } else {
      // Обычные переходы по ссылкам — скроллим к началу страницы
      window.scrollTo(0, 0);
    }

    const saveScroll = () => {
      try {
        const y = window.scrollY ?? window.pageYOffset ?? 0;
        sessionStorage.setItem(storageKey, String(y));
      } catch {
        // Игнорируем ошибки доступа к sessionStorage (например, в приватном режиме)
      }
    };

    window.addEventListener('beforeunload', saveScroll);
    return () => {
      saveScroll();
      window.removeEventListener('beforeunload', saveScroll);
    };
  }, [location, navigationType]);

  return null;
}

function WithTitle({ title, children }) {
  usePageTitle(title);
  return children;
}

// Protected route wrapper for admin (AdminLayout тоже lazy)
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

  return (
    <Suspense fallback={<LazyFallback />}>
      <AdminLayout>{children}</AdminLayout>
    </Suspense>
  );
}

function AppRoutes() {
  return (
    <Suspense fallback={<LazyFallback />}>
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
    </Suspense>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ScrollRestoration />
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
