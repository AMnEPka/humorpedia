import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
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

import { Loader2 } from 'lucide-react';
import '@/App.css';

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
        <Route path="/" element={<HomePage />} />
        
        {/* News */}
        <Route path="/news" element={<NewsListPage />} />
        <Route path="/news/:slug" element={<NewsDetailPage />} />
        
        {/* Articles */}
        <Route path="/articles" element={<ArticlesListPage />} />
        <Route path="/articles/:slug" element={<ArticleDetailPage />} />
        
        {/* People */}
        <Route path="/people" element={<PeopleListPage />} />
        <Route path="/people/:slug" element={<PersonDetailPage />} />
        
        {/* Teams with categories */}
        <Route path="/teams" element={<Navigate to="/kvn/teams" replace />} />
        <Route path="/teams/:category" element={<Navigate to="/kvn/teams" replace />} />
        <Route path="/kvn/teams" element={<TeamsListPage />} />
        <Route path="/kvn/teams/:slug" element={<TeamDetailPage />} />
        
        {/* Shows */}
        <Route path="/shows" element={<ShowsListPage />} />
        <Route path="/shows/:slug" element={<ShowDetailPage />} />
        <Route path="/shows/:parentSlug/:childSlug" element={<ShowDetailPage />} />
        <Route path="/shows/:parentSlug/:childSlug/:grandchildSlug" element={<ShowDetailPage />} />
        <Route path="/shows/:parentSlug/:childSlug/:grandchildSlug/:greatGrandchildSlug" element={<ShowDetailPage />} />
        
        {/* Quizzes */}
        <Route path="/quizzes" element={<QuizzesListPage />} />
        <Route path="/quizzes/:slug" element={<QuizDetailPage />} />
        
        {/* Static pages */}
        <Route path="/contacts" element={<ContactsPage />} />
        <Route path="/policy" element={<PolicyPage />} />
        
        {/* Search */}
        <Route path="/search" element={<SearchPage />} />
        <Route path="/tags/:tag" element={<TagSearchPage />} />
        
        {/* Dynamic sections - catch-all for hierarchical URLs */}
        <Route path="/*" element={<SectionDetailPage />} />
      </Route>
      
      {/* Admin routes */}
      <Route path="/admin/login" element={<LoginPage />} />
      
      <Route path="/admin" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      
      {/* Admin - People */}
      <Route path="/admin/people" element={<ProtectedRoute><AdminPeopleListPage /></ProtectedRoute>} />
      <Route path="/admin/people/:id" element={<ProtectedRoute><PersonEditPage /></ProtectedRoute>} />
      
      {/* Admin - Teams */}
      <Route path="/admin/teams" element={<ProtectedRoute><AdminTeamsListPage /></ProtectedRoute>} />
      <Route path="/admin/teams/:id" element={<ProtectedRoute><TeamEditPage /></ProtectedRoute>} />
      
      {/* Admin - Shows */}
      <Route path="/admin/shows" element={<ProtectedRoute><AdminShowsListPage /></ProtectedRoute>} />
      <Route path="/admin/shows/:id" element={<ProtectedRoute><ShowEditPage /></ProtectedRoute>} />
      
      {/* Admin - Articles */}
      <Route path="/admin/articles" element={<ProtectedRoute><AdminArticlesListPage /></ProtectedRoute>} />
      <Route path="/admin/articles/:id" element={<ProtectedRoute><ArticleEditPage /></ProtectedRoute>} />
      
      {/* Admin - News */}
      <Route path="/admin/news" element={<ProtectedRoute><AdminNewsListPage /></ProtectedRoute>} />
      <Route path="/admin/news/:id" element={<ProtectedRoute><NewsEditPage /></ProtectedRoute>} />
      
      {/* Admin - Quizzes */}
      <Route path="/admin/quizzes" element={<ProtectedRoute><AdminQuizzesListPage /></ProtectedRoute>} />
      <Route path="/admin/quizzes/:id" element={<ProtectedRoute><QuizEditPage /></ProtectedRoute>} />
      
      {/* Admin - Wiki */}
      <Route path="/admin/wiki" element={<ProtectedRoute><WikiListPage /></ProtectedRoute>} />
      <Route path="/admin/wiki/:id" element={<ProtectedRoute><WikiEditPage /></ProtectedRoute>} />
      
      {/* Admin - Sections */}
      <Route path="/admin/sections" element={<ProtectedRoute><SectionsListPage /></ProtectedRoute>} />
      <Route path="/admin/sections/:id" element={<ProtectedRoute><SectionEditPage /></ProtectedRoute>} />
      
      {/* Admin - Media */}
      <Route path="/admin/media" element={<ProtectedRoute><MediaPage /></ProtectedRoute>} />
      
      {/* Admin - Tags */}
      <Route path="/admin/tags" element={<ProtectedRoute><TagsPage /></ProtectedRoute>} />
      
      {/* Admin - Comments */}
      <Route path="/admin/comments" element={<ProtectedRoute><CommentsPage /></ProtectedRoute>} />
      
      {/* Admin - Users */}
      <Route path="/admin/users" element={<ProtectedRoute><UsersPage /></ProtectedRoute>} />
      
      {/* Admin - Templates */}
      <Route path="/admin/templates" element={<ProtectedRoute><TemplatesPage /></ProtectedRoute>} />
      <Route path="/admin/templates/:id" element={<ProtectedRoute><TemplateEditPage /></ProtectedRoute>} />
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
