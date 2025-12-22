import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, Users, MapPin, Trophy, Share2, Calendar } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import publicApi from '../utils/api';

export default function TeamDetailPage() {
  const { category = 'kvn', slug } = useParams();
  const [team, setTeam] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchTeam = async () => {
      setLoading(true);
      try {
        const res = await publicApi.getTeam(slug);
        setTeam(res.data);
      } catch (err) {
        setError('Команда не найдена');
      } finally {
        setLoading(false);
      }
    };
    fetchTeam();
  }, [slug]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !team) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
        <p className="text-gray-500 mb-4">{error || 'Команда не найдена'}</p>
        <Button asChild>
          <Link to={`/teams/${category}`}>Вернуться к списку</Link>
        </Button>
      </div>
    );
  }

  const categoryNames = { kvn: 'КВН', lg: 'Лига смеха', improv: 'Импровизация' };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm text-gray-500">
          <li><Link to="/" className="hover:text-blue-600">Главная</Link></li>
          <li>/</li>
          <li><Link to={`/teams/${category}`} className="hover:text-blue-600">{categoryNames[category] || 'Команды'}</Link></li>
          <li>/</li>
          <li className="text-gray-900 truncate max-w-[200px]">{team.title}</li>
        </ol>
      </nav>

      {/* Hero */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-800 rounded-2xl p-8 md:p-12 text-white mb-8">
        <div className="flex flex-col md:flex-row items-center gap-8">
          <div className="w-32 h-32 bg-white/10 rounded-xl overflow-hidden flex-shrink-0">
            {team.logo ? (
              <img src={team.logo} alt={team.title} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-4xl font-bold">
                {team.title?.charAt(0)?.toUpperCase()}
              </div>
            )}
          </div>
          <div className="text-center md:text-left">
            <h1 className="text-3xl md:text-4xl font-bold mb-2">{team.title}</h1>
            {team.city && (
              <div className="flex items-center justify-center md:justify-start gap-2 text-blue-100">
                <MapPin className="h-4 w-4" />
                <span>{team.city}</span>
              </div>
            )}
            {team.tags?.length > 0 && (
              <div className="flex flex-wrap justify-center md:justify-start gap-2 mt-4">
                {team.tags.map((tag, i) => (
                  <Badge key={i} variant="secondary" className="bg-white/20 text-white">{tag}</Badge>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Sidebar */}
        <div className="lg:col-span-1 space-y-6">
          {/* Team Members */}
          {team.members?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" /> Состав
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="space-y-3">
                  {team.members.map((member, i) => (
                    <Link 
                      key={i} 
                      to={`/people/${member.slug}`}
                      className="flex items-center gap-3 p-2 rounded hover:bg-gray-100 transition-colors"
                    >
                      <div className="w-10 h-10 bg-gray-100 rounded-full overflow-hidden">
                        {member.photo ? (
                          <img src={member.photo} alt={member.name} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm font-bold">
                            {member.name?.charAt(0)}
                          </div>
                        )}
                      </div>
                      <div>
                        <div className="font-medium text-sm">{member.name}</div>
                        {member.role && <div className="text-xs text-gray-500">{member.role}</div>}
                      </div>
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Achievements */}
          {team.achievements?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Trophy className="h-5 w-5" /> Достижения
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <ul className="space-y-2">
                  {team.achievements.map((ach, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <Trophy className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
                      <span>{ach}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <Button variant="outline" className="w-full" onClick={() => navigator.share?.({ url: window.location.href, title: team.title })}>
            <Share2 className="mr-2 h-4 w-4" /> Поделиться
          </Button>
        </div>

        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* History/Bio */}
          {team.history && (
            <Card>
              <CardHeader>
                <CardTitle>История</CardTitle>
              </CardHeader>
              <CardContent>
                <div 
                  className="prose prose-blue max-w-none"
                  dangerouslySetInnerHTML={{ __html: team.history }}
                />
              </CardContent>
            </Card>
          )}

          {/* Modules */}
          {team.modules?.map((module, i) => (
            <ModuleRenderer key={i} module={module} />
          ))}
        </div>
      </div>
    </div>
  );
}

// Module renderer component (same as PersonDetailPage)
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

    case 'tv_appearances':
      return (
        <Card>
          <CardHeader>
            <CardTitle>{module.data?.title || 'ТВ эфиры'}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {module.data?.items?.map((item, i) => (
                <div key={i} className="p-3 bg-gray-50 rounded-lg">
                  <div className="font-medium">{item.show}</div>
                  {item.date && <div className="text-sm text-gray-500">{item.date}</div>}
                  {item.description && <p className="text-sm text-gray-600 mt-1">{item.description}</p>}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      );
    
    default:
      return null;
  }
}
