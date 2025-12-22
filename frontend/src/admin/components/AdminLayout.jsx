import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import {
  Users, FileText, Newspaper, HelpCircle, BookOpen, Tv, 
  UsersRound, Tags, MessageSquare, Image, LayoutTemplate,
  Home, Menu, X, LogOut, ChevronDown, Settings
} from 'lucide-react';
import { cn } from '@/lib/utils';

const menuItems = [
  { path: '/admin', icon: Home, label: 'Главная', exact: true },
  { path: '/admin/people', icon: Users, label: 'Люди' },
  { path: '/admin/teams', icon: UsersRound, label: 'Команды' },
  { path: '/admin/shows', icon: Tv, label: 'Шоу' },
  { path: '/admin/articles', icon: FileText, label: 'Статьи' },
  { path: '/admin/news', icon: Newspaper, label: 'Новости' },
  { path: '/admin/quizzes', icon: HelpCircle, label: 'Квизы' },
  { path: '/admin/wiki', icon: BookOpen, label: 'Вики' },
  { divider: true },
  { path: '/admin/media', icon: Image, label: 'Медиа' },
  { path: '/admin/tags', icon: Tags, label: 'Теги' },
  { path: '/admin/comments', icon: MessageSquare, label: 'Комментарии' },
  { divider: true },
  { path: '/admin/users', icon: Users, label: 'Пользователи', adminOnly: true },
  { path: '/admin/templates', icon: LayoutTemplate, label: 'Шаблоны' },
];

export default function AdminLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, isAdmin } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/admin/login');
  };

  const isActive = (item) => {
    if (item.exact) {
      return location.pathname === item.path;
    }
    return location.pathname.startsWith(item.path);
  };

  const filteredMenuItems = menuItems.filter(item => {
    if (item.divider) return true;
    if (item.adminOnly && !isAdmin) return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Mobile header */}
      <div className="lg:hidden bg-white border-b px-4 py-3 flex items-center justify-between">
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-2 rounded-md hover:bg-gray-100"
        >
          {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
        <span className="font-bold text-lg">Humorpedia Admin</span>
        <div className="w-10" />
      </div>

      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <div 
          className="lg:hidden fixed inset-0 bg-black/50 z-40"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed top-0 left-0 z-50 h-full bg-white border-r transition-all duration-300",
          "lg:translate-x-0",
          sidebarOpen ? "w-64" : "w-16",
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-4 border-b">
          {sidebarOpen && (
            <Link to="/admin" className="font-bold text-xl text-primary">
              Humorpedia
            </Link>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="hidden lg:block p-2 rounded-md hover:bg-gray-100"
          >
            <Menu size={20} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="p-2 space-y-1 overflow-y-auto h-[calc(100%-8rem)]">
          {filteredMenuItems.map((item, index) => {
            if (item.divider) {
              return <div key={index} className="my-2 border-t" />;
            }

            const Icon = item.icon;
            const active = isActive(item);

            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setMobileMenuOpen(false)}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-gray-100 text-gray-700"
                )}
              >
                <Icon size={20} />
                {sidebarOpen && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* User section */}
        <div className="absolute bottom-0 left-0 right-0 p-2 border-t bg-white">
          <div className={cn(
            "flex items-center gap-3 px-3 py-2",
            sidebarOpen ? "" : "justify-center"
          )}>
            <div className="w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-medium">
              {user?.username?.[0]?.toUpperCase() || 'A'}
            </div>
            {sidebarOpen && (
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{user?.username}</div>
                <div className="text-xs text-gray-500">{user?.role}</div>
              </div>
            )}
            <button
              onClick={handleLogout}
              className="p-2 rounded-md hover:bg-gray-100 text-gray-500"
              title="Выйти"
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main
        className={cn(
          "min-h-screen transition-all duration-300 pt-0 lg:pt-0",
          sidebarOpen ? "lg:ml-64" : "lg:ml-16"
        )}
      >
        <div className="p-4 lg:p-6">
          {children}
        </div>
      </main>
    </div>
  );
}
