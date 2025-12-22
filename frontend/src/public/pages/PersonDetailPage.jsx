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
    const effectiveMode = mode === 'auto' 
      ? (contentType === 'person' ? 'timeline' : 'sections')
      : mode;
    
    if (effectiveMode === 'timeline') {
      // Get items from timeline module
      const timelineModule = modules?.find(m => m.type === 'timeline');
      return timelineModule?.data?.items?.map(item => ({
        id: `timeline-${item.year}`,
        label: item.year,
        title: item.title
      })) || [];
    } else {
      // Get titles from text_block modules
      return modules?.filter(m => m.type === 'text_block' && m.data?.title)
        .map(m => ({
          id: `section-${m.id}`,
          label: m.data.title,
          title: m.data.title
        })) || [];
    }
  }, [modules, mode, contentType]);

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
                {person.photo ? (
                  <img 
                    src={person.photo} 
                    alt={person.title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-400">
                    <span className="text-6xl font-bold">
                      {person.title?.charAt(0)?.toUpperCase()}
                    </span>
                  </div>
                )}
              </div>
              
              <h1 className="text-2xl font-bold text-gray-900 mb-4">{person.title}</h1>
              
              {/* Biography info */}
              <div className="space-y-3 text-sm">
                {person.bio?.birth_date && (
                  <div className="flex items-center gap-2 text-gray-600">
                    <Calendar className="h-4 w-4 flex-shrink-0" />
                    <span>
                      {new Date(person.bio.birth_date).toLocaleDateString('ru-RU')}
                      {person.bio?.death_date && ` — ${new Date(person.bio.death_date).toLocaleDateString('ru-RU')}`}
                    </span>
                  </div>
                )}
                {person.bio?.birth_place && (
                  <div className="flex items-center gap-2 text-gray-600">
                    <MapPin className="h-4 w-4 flex-shrink-0" />
                    <span>{person.bio.birth_place}</span>
                  </div>
                )}
                {person.bio?.occupation?.length > 0 && (
                  <div className="text-gray-600">
                    <span className="font-medium">Род деятельности:</span>
                    <div className="mt-1">{person.bio.occupation.join(', ')}</div>
                  </div>
                )}
                {person.bio?.achievements?.length > 0 && (
                  <div className="text-gray-600">
                    <span className="font-medium">Достижения:</span>
                    <ul className="mt-1 list-disc list-inside">
                      {person.bio.achievements.map((a, i) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ul>
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
        </div>

        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Tags */}
          {person.tags?.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {person.tags.map((tag, i) => (
                <Badge key={i} variant="secondary" className="text-sm px-3 py-1">{tag}</Badge>
              ))}
            </div>
          )}

          {/* Modules */}
          {person.modules?.map((module, i) => (
            <ModuleRenderer key={i} module={module} />
          ))}
        </div>
      </div>
    </div>
  );
}

// Module renderer component
function ModuleRenderer({ module }) {
  switch (module.type) {
    case 'text_block':
      return (
        <Card>
          {module.data?.title && (
            <CardHeader>
              <CardTitle>{module.data.title}</CardTitle>
            </CardHeader>
          )}
          <CardContent>
            <div 
              className="prose prose-blue max-w-none"
              dangerouslySetInnerHTML={{ __html: module.data?.content || '' }}
            />
          </CardContent>
        </Card>
      );
    
    case 'timeline':
      return (
        <Card>
          <CardHeader>
            <CardTitle>{module.data?.title || 'Хронология'}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="relative pl-6 border-l-2 border-blue-200 space-y-6">
              {module.data?.items?.map((item, i) => (
                <div key={i} className="relative">
                  <div className="absolute -left-[25px] w-4 h-4 bg-blue-600 rounded-full border-4 border-white" />
                  <div className="text-sm text-blue-600 font-semibold">{item.year}</div>
                  <div className="font-medium">{item.title}</div>
                  {item.description && (
                    <p className="text-gray-600 text-sm mt-1">{item.description}</p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      );
    
    case 'gallery':
      return (
        <Card>
          <CardHeader>
            <CardTitle>{module.data?.title || 'Галерея'}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {module.data?.images?.map((img, i) => (
                <img 
                  key={i} 
                  src={img.url} 
                  alt={img.caption || ''}
                  className="rounded-lg aspect-square object-cover"
                />
              ))}
            </div>
          </CardContent>
        </Card>
      );
    
    case 'quote':
      return (
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="p-6">
            <blockquote className="text-lg italic text-gray-700">
              «{module.data?.text}»
            </blockquote>
            {module.data?.author && (
              <cite className="block mt-2 text-sm text-gray-500 not-italic">
                — {module.data.author}
              </cite>
            )}
          </CardContent>
        </Card>
      );
    
    default:
      return null;
  }
}
