import { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, Calendar, Users, MapPin, Share2, ArrowLeft, List } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import publicApi from '../utils/api';

// Table of Contents component
function TableOfContents({ modules, mode = 'auto', contentType = 'person' }) {
  const items = useMemo(() => {
    if (!modules || modules.length === 0) return [];
    
    // For person pages, extract from timeline modules
    if (contentType === 'person') {
      return modules
        .filter(m => m.type === 'timeline')
        .map((m, idx) => ({
          id: `timeline-${idx}`,
          label: m.data?.period || `Период ${idx + 1}`,
          title: m.data?.title || 'Без названия'
        }));
    }
    
    // For other content, extract from text_block modules with titles
    return modules
      .filter(m => m.type === 'text_block' && m.data?.title)
      .map((m, idx) => ({
        id: `section-${idx}`,
        label: m.data.title,
        title: m.data.title
      }));
  }, [modules, contentType]);

  if (items.length === 0) return null;

  const scrollToSection = (id) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <Card className="mt-6">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <List className="h-5 w-5" /> Оглавление
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <nav className="space-y-1">
          {items.map((item, i) => (
            <button
              key={i}
              onClick={() => scrollToSection(item.id)}
              className="w-full text-left px-2 py-1.5 text-sm rounded hover:bg-gray-100 transition-colors flex items-start gap-2"
            >
              <span className="text-blue-600 font-medium whitespace-nowrap">{item.label}</span>
              {item.title !== item.label && (
                <span className="text-gray-600 truncate">{item.title}</span>
              )}
            </button>
          ))}
        </nav>
      </CardContent>
    </Card>
  );
}

export default function PersonDetailPage() {
  const { slug } = useParams();
  const [person, setPerson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchPerson = async () => {
      setLoading(true);
      try {
        const res = await publicApi.getPerson(slug);
        setPerson(res.data);
      } catch (err) {
        setError('Человек не найден');
      } finally {
        setLoading(false);
      }
    };
    fetchPerson();
  }, [slug]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !person) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
        <p className="text-gray-500 mb-4">{error || 'Человек не найден'}</p>
        <Button asChild>
          <Link to="/people">Вернуться к списку</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm text-gray-500">
          <li><Link to="/" className="hover:text-blue-600">Главная</Link></li>
          <li>/</li>
          <li><Link to="/people" className="hover:text-blue-600">Люди</Link></li>
          <li>/</li>
          <li className="text-gray-900 truncate max-w-[200px]">{person.title}</li>
        </ol>
      </nav>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Sidebar with photo and bio */}
        <div className="lg:col-span-1">
          <Card>
            <CardContent className="p-6">
              <div className="aspect-square bg-gray-100 rounded-lg overflow-hidden mb-4">
                {person.cover_image?.url ? (
                  <img 
                    src={person.cover_image.url} 
                    alt={person.cover_image.alt || person.full_name || person.title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-400">
                    <span className="text-6xl font-bold">
                      {person.full_name?.charAt(0)?.toUpperCase() || person.title?.charAt(0)?.toUpperCase()}
                    </span>
                  </div>
                )}
              </div>
              
              <h1 className="text-2xl font-bold text-gray-900 mb-4">{person.full_name || person.title}</h1>
              
              {/* Biography info */}
              <div className="space-y-3 text-sm">
                {person.birth_date && (
                  <div className="flex items-center gap-2 text-gray-600">
                    <Calendar className="h-4 w-4 flex-shrink-0" />
                    <span>
                      {new Date(person.birth_date).toLocaleDateString('ru-RU', { 
                        year: 'numeric', 
                        month: 'long', 
                        day: 'numeric' 
                      })}
                      {' '}
                      ({(() => {
                        const birthDate = new Date(person.birth_date);
                        const today = new Date();
                        let age = today.getFullYear() - birthDate.getFullYear();
                        const monthDiff = today.getMonth() - birthDate.getMonth();
                        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
                          age--;
                        }
                        return `${age} ${age % 10 === 1 && age % 100 !== 11 ? 'год' : age % 10 >= 2 && age % 10 <= 4 && (age % 100 < 10 || age % 100 >= 20) ? 'года' : 'лет'}`;
                      })()})
                    </span>
                  </div>
                )}
                {person.birth_place && (
                  <div className="flex items-center gap-2 text-gray-600">
                    <MapPin className="h-4 w-4 flex-shrink-0" />
                    <span>{person.birth_place}</span>
                  </div>
                )}
                {person.social_links && Object.keys(person.social_links).length > 0 && (
                  <div className="pt-2 border-t">
                    <div className="flex gap-2">
                      {person.social_links.vk && (
                        <a 
                          href={person.social_links.vk} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-700 text-sm"
                        >
                          VK
                        </a>
                      )}
                      {person.social_links.instagram && (
                        <a 
                          href={person.social_links.instagram} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-pink-600 hover:text-pink-700 text-sm"
                        >
                          Instagram
                        </a>
                      )}
                      {person.social_links.youtube && (
                        <a 
                          href={person.social_links.youtube} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-red-600 hover:text-red-700 text-sm"
                        >
                          YouTube
                        </a>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Share */}
              <Button variant="outline" className="w-full mt-4" onClick={() => navigator.share?.({ url: window.location.href, title: person.title })}>
                <Share2 className="mr-2 h-4 w-4" /> Поделиться
              </Button>
            </CardContent>
          </Card>

          {/* Teams */}
          {person.teams?.length > 0 && (
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Users className="h-5 w-5" /> Команды
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="space-y-2">
                  {person.teams.map((team, i) => (
                    <Link 
                      key={i} 
                      to={`/teams/kvn/${team.slug}`}
                      className="block p-2 rounded hover:bg-gray-100 transition-colors"
                    >
                      {team.title || team.name}
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Table of Contents */}
          <TableOfContents modules={person.modules} contentType="person" />
        </div>

        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Tags */}
          {person.tags?.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {person.tags.map((tag, i) => (
                <Link key={i} to={`/tags/${encodeURIComponent(tag)}`}>
                  <Badge variant="secondary" className="text-sm px-3 py-1 cursor-pointer hover:bg-blue-100">
                    {tag}
                  </Badge>
                </Link>
              ))}
            </div>
          )}

          {/* Modules */}
          {person.modules?.map((module, i) => (
            <ModuleRenderer key={i} module={module} index={i} />
          ))}
        </div>
      </div>
    </div>
  );
}

// Module renderer component
function ModuleRenderer({ module, index }) {
  switch (module.type) {
    case 'timeline':
      return (
        <Card id={`timeline-${index}`} className="scroll-mt-4">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="text-sm font-medium text-blue-600 mb-1">
                  {module.data?.period}
                </div>
                <CardTitle className="text-xl">{module.data?.title}</CardTitle>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {module.data?.content_html ? (
              <div 
                className="prose prose-sm max-w-none text-gray-700"
                dangerouslySetInnerHTML={{ __html: module.data.content_html }}
              />
            ) : (
              <p className="text-gray-700 leading-relaxed whitespace-pre-line">
                {module.data?.content}
              </p>
            )}
          </CardContent>
        </Card>
      );
    
    case 'text':
      return (
        <Card id={`text-${index}`}>
          <CardContent className="p-6">
            {module.data?.content_html ? (
              <div 
                className="prose prose-sm max-w-none text-gray-700"
                dangerouslySetInnerHTML={{ __html: module.data.content_html }}
              />
            ) : (
              <p className="text-gray-700 leading-relaxed whitespace-pre-line">
                {module.data?.content}
              </p>
            )}
          </CardContent>
        </Card>
      );
    
    case 'text_block':
      return (
        <Card id={`section-${index}`}>
          {module.data?.title && (
            <CardHeader>
              <CardTitle>{module.data.title}</CardTitle>
            </CardHeader>
          )}
          <CardContent>
            <div 
              className="prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{ __html: module.data?.content || '' }}
            />
          </CardContent>
        </Card>
      );
    
    default:
      return null;
  }
}
