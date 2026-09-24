import { useState, useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Search, Menu, X, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import publicApi from '../utils/api';

const staticNavigation = [
  { name: 'Новости', href: '/news' },
  { name: 'Статьи', href: '/articles' },
  { name: 'Люди', href: '/people' },
  { name: 'КВН', href: '/kvn' },
  { name: 'Команды', href: '/teams' },
  { name: 'Шоу', href: '/shows' },
  { name: 'География', href: '/city' },
  { name: 'Квизы', href: '/quizzes' },
  { name: 'Контакты', href: '/contacts' },
];

const contentTypeLabels = {
  person: 'Персона',
  team: 'Команда',
  show: 'Шоу',
  article: 'Статья',
  news: 'Новость',
  section: 'Раздел',
  city: 'Город',
  quiz: 'Квиз',
};

export default function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [suggestionError, setSuggestionError] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [menuSections, setMenuSections] = useState([]);
  const searchRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    // Load sections that should appear in main menu
    publicApi.getSections({ in_main_menu: true, status: 'published' })
      .then(res => {
        if (cancelled) {
          return;
        }
        const sections = res.data.items || [];
        const sectionLinks = sections.map(s => ({
          name: s.menu_title || s.title,
          href: s.full_path,
          order: s.order || 0
        }));
        console.log('Loaded menu sections:', sectionLinks);
        setMenuSections(sectionLinks.sort((a, b) => a.order - b.order));
      })
      .catch(err => {
        if (!cancelled) {
          console.error('Error loading menu sections:', err);
          setMenuSections([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    // Load autocomplete suggestions
    const query = searchQuery.trim();
    if (query.length >= 2) {
      setLoadingSuggestions(true);
      setSuggestionError(false);
      let cancelled = false;
      const timer = setTimeout(() => {
        publicApi.searchAutocomplete(query)
          .then(res => {
            if (cancelled) {
              return;
            }
            setSuggestions(res.data);
            setShowSuggestions(true);
          })
          .catch(err => {
            if (!cancelled) {
              console.error('Autocomplete error:', err);
              setSuggestions([]);
              setSuggestionError(true);
              setShowSuggestions(true);
            }
          })
          .finally(() => {
            if (!cancelled) {
              setLoadingSuggestions(false);
            }
          });
      }, 300);
      return () => {
        cancelled = true;
        clearTimeout(timer);
      };
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
      setLoadingSuggestions(false);
      setSuggestionError(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    // Close suggestions when clicking outside
    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const navigation = [...menuSections, ...staticNavigation];

  const openSearchResults = () => {
    const query = searchQuery.trim();
    if (query.length < 2) {
      return;
    }
    setSearchQuery('');
    setSearchOpen(false);
    setShowSuggestions(false);
    navigate(`/search?q=${encodeURIComponent(query)}`);
  };

  const handleSearch = (e) => {
    e.preventDefault();
    openSearchResults();
  };

  const handleSuggestionClick = (suggestion) => {
    setSearchOpen(false);
    setShowSuggestions(false);
    setSearchQuery('');
    navigate(suggestion.path);
  };

  return (
    <header className="sticky top-0 z-50 bg-white border-b shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-xl">H</span>
            </div>
            <span className="text-xl font-bold text-gray-900 hidden sm:block">Humorpedia</span>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden lg:flex items-center gap-1">
            {navigation.map((item) => (
              <Link
                key={item.name}
                to={item.href}
                className={cn(
                  'px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  (location.pathname.startsWith(item.href) || (item.href === '/teams' && location.pathname === '/kvn/teams'))
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                )}
              >
                {item.name}
              </Link>
            ))}
          </nav>

          {/* Search & User Actions */}
          <div className="flex items-center gap-2">
            {/* Search */}
            <div className="relative" ref={searchRef}>
              {searchOpen ? (
                <div className="relative">
                  <form onSubmit={handleSearch} className="flex items-center">
                    <Input
                      type="search"
                      placeholder="Поиск..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-48 sm:w-64 pr-8"
                      autoFocus
                    />
                    {loadingSuggestions && (
                      <Loader2 className="absolute right-10 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-gray-400" />
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label="Закрыть поиск"
                      onClick={() => {
                        setSearchOpen(false);
                        setShowSuggestions(false);
                        setSearchQuery('');
                      }}
                      className="ml-1 min-w-11 min-h-11"
                    >
                      <X className="h-5 w-5" />
                    </Button>
                  </form>
                  
                  {/* Autocomplete suggestions */}
                  {showSuggestions && searchQuery.trim().length >= 2 && (
                    <div className="absolute top-full mt-2 w-full sm:w-96 bg-white rounded-lg shadow-lg border z-50 max-h-96 overflow-y-auto" aria-live="polite">
                      {suggestionError && <p role="alert" className="px-4 py-3 text-sm text-red-700">Не удалось загрузить подсказки. Откройте полную выдачу.</p>}
                      {!suggestionError && !loadingSuggestions && suggestions.length === 0 && (
                        <p className="px-4 py-3 text-sm text-gray-600">Подсказок пока нет. Попробуйте полную выдачу.</p>
                      )}
                      {suggestions.map((item) => (
                        <button
                          key={item.id}
                          onClick={() => handleSuggestionClick(item)}
                          className="w-full min-h-11 text-left px-4 py-3 hover:bg-gray-50 border-b last:border-b-0 transition-colors"
                        >
                          <div className="flex items-start gap-3">
                            {item.image && <img src={item.image} alt="" className="h-12 w-12 rounded object-cover flex-shrink-0" />}
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-gray-900 truncate">
                                {item.title}
                              </p>
                              <p className="text-xs text-gray-500 mt-1">
                                {contentTypeLabels[item.type] || item.type}
                                {item.context && ` · ${item.context}`}
                              </p>
                            </div>
                          </div>
                        </button>
                      ))}
                      <button
                        type="button"
                        onClick={openSearchResults}
                        className="w-full min-h-11 px-4 py-3 text-left text-sm font-medium text-blue-700 hover:bg-blue-50 border-t transition-colors"
                      >
                        Показать все результаты по запросу «{searchQuery.trim()}»
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Открыть поиск"
                  onClick={() => setSearchOpen(true)}
                  className="text-gray-600 min-w-11 min-h-11"
                >
                  <Search className="h-5 w-5" />
                </Button>
              )}
            </div>

            {/* Mobile menu button */}
            <Button
              variant="ghost"
              size="icon"
              aria-label={mobileMenuOpen ? 'Закрыть меню' : 'Открыть меню'}
              aria-expanded={mobileMenuOpen}
              className="lg:hidden text-gray-600 min-w-11 min-h-11"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </Button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {mobileMenuOpen && (
          <div className="lg:hidden py-4 border-t">
            <nav className="flex flex-col gap-1">
              {navigation.map((item) => (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={cn(
                    'min-h-11 flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                    (location.pathname.startsWith(item.href) || (item.href === '/teams' && location.pathname === '/kvn/teams'))
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  )}
                >
                  {item.name}
                </Link>
              ))}
            </nav>
          </div>
        )}
      </div>
    </header>
  );
}
