import { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, Calendar, Users, MapPin, Share2, ArrowLeft, List } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import EmojiRating from '@/components/EmojiRating';
import publicApi from '../utils/api';

// Table of Contents component
function TableOfContents({ modules, mode = 'auto', contentType = 'person' }) {
  const items = useMemo(() => {
    if (!modules || modules.length === 0) return [];
    
    // For person pages, extract events from timeline modules
    if (contentType === 'person') {
      const timelineItems = [];
      modules.forEach((m, moduleIdx) => {
        if (m.type === 'timeline' && m.data?.events) {
          m.data.events.forEach((event, eventIdx) => {
            timelineItems.push({
              id: `timeline-${moduleIdx}-event-${eventIdx}`,
              label: event.year || event.date || `Событие ${eventIdx + 1}`,
              title: event.title || 'Без названия'
            });
          });
        }
      });
      return timelineItems;
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
                {(person.cover_image?.url || person.image) ? (
                  <img 
                    src={person.cover_image?.url || person.image} 
                    alt={person.cover_image?.alt || person.full_name || person.title}
                    className="w-full h-full object-cover object-top"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-400">
                    <span className="text-6xl font-bold">
                      {person.full_name?.charAt(0)?.toUpperCase() || person.title?.charAt(0)?.toUpperCase()}
                    </span>
                  </div>
                )}
              </div>
              
              {/* Short name without patronymic */}
              <h1 className="text-2xl font-bold text-gray-900 mb-3">{person.title}</h1>
              
              {/* Social links as icons */}
              {person.social_links && Object.keys(person.social_links).length > 0 && (
                <div className="flex gap-3 mb-4">
                  {person.social_links.vk && (
                    <a 
                      href={person.social_links.vk} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="w-8 h-8 flex items-center justify-center rounded-full bg-[#0077FF] hover:bg-[#0066DD] transition-colors"
                      title="VKontakte"
                    >
                      <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12.785 16.241s.288-.032.436-.194c.136-.148.132-.427.132-.427s-.02-1.304.587-1.496c.596-.19 1.365 1.26 2.18 1.817.616.422 1.084.33 1.084.33l2.177-.03s1.137-.07.598-.964c-.044-.073-.314-.661-1.618-1.869-1.366-1.264-1.183-1.06.462-3.246.998-1.328 1.398-2.139 1.273-2.485-.12-.33-.856-.243-.856-.243l-2.453.015s-.182-.025-.317.056c-.132.078-.217.26-.217.26s-.39 1.04-.91 1.924c-1.097 1.867-1.536 1.966-1.716 1.85-.42-.271-.315-1.087-.315-1.666 0-1.812.275-2.568-.533-2.764-.27-.065-.467-.108-1.154-.115-.882-.009-1.628.003-2.05.209-.28.138-.497.443-.365.46.163.022.532.099.728.365.253.343.244 1.114.244 1.114s.145 2.132-.34 2.397c-.333.181-.788-.189-1.767-1.884-.502-.867-.88-1.826-.88-1.826s-.073-.179-.203-.275c-.158-.118-.378-.155-.378-.155l-2.334.015s-.35.01-.478.162c-.115.136-.009.417-.009.417s1.838 4.302 3.92 6.47c1.907 1.987 4.073 1.857 4.073 1.857l.988-.001z"/>
                      </svg>
                    </a>
                  )}
                  {person.social_links.telegram && (
                    <a 
                      href={person.social_links.telegram} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="w-8 h-8 flex items-center justify-center rounded-full bg-[#26A5E4] hover:bg-[#1E96D1] transition-colors"
                      title="Telegram"
                    >
                      <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                      </svg>
                    </a>
                  )}
                  {person.social_links.instagram && (
                    <a 
                      href={person.social_links.instagram} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="w-8 h-8 flex items-center justify-center rounded-full bg-gradient-to-tr from-[#FFDC80] via-[#F56040] to-[#C13584] hover:opacity-90 transition-opacity"
                      title="Instagram"
                    >
                      <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                      </svg>
                    </a>
                  )}
                  {person.social_links.youtube && (
                    <a 
                      href={person.social_links.youtube} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="w-8 h-8 flex items-center justify-center rounded-full bg-[#FF0000] hover:bg-[#CC0000] transition-colors"
                      title="YouTube"
                    >
                      <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                      </svg>
                    </a>
                  )}
                  {person.social_links.twitter && (
                    <a 
                      href={person.social_links.twitter} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="w-8 h-8 flex items-center justify-center rounded-full bg-black hover:bg-gray-800 transition-colors"
                      title="X (Twitter)"
                    >
                      <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                      </svg>
                    </a>
                  )}
                </div>
              )}
              
              {/* Rating display with EmojiRating component */}
              {person.rating && (
                <div className="mb-4">
                  <EmojiRating
                    value={person.rating.average}
                    readOnly
                    count={person.rating.count}
                    size={24}
                    emojis={['😡', '😠', '😟', '😕', '😐', '🙂', '😊', '😃', '😄', '🤩']}
                    showValue={true}
                    valueFormat="fraction"
                  />
                </div>
              )}

              {/* Share */}
              <Button variant="outline" className="w-full mb-4" onClick={() => navigator.share?.({ url: window.location.href, title: person.title })}>
                <Share2 className="mr-2 h-4 w-4" /> Поделиться
              </Button>

              {/* Info table */}
              <div className="border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <tbody className="divide-y">
                    {person.full_name && (
                      <tr>
                        <td className="px-3 py-2 bg-gray-50 text-gray-600 font-medium w-1/3">Полное имя</td>
                        <td className="px-3 py-2">{person.full_name}</td>
                      </tr>
                    )}
                    {(person.birth_date || person.bio?.birth_date) && (
                      <tr>
                        <td className="px-3 py-2 bg-gray-50 text-gray-600 font-medium">Дата рождения</td>
                        <td className="px-3 py-2">
                          {(() => {
                            const dateStr = person.birth_date || person.bio?.birth_date;
                            const birthDate = new Date(dateStr);
                            const today = new Date();
                            let age = today.getFullYear() - birthDate.getFullYear();
                            const monthDiff = today.getMonth() - birthDate.getMonth();
                            if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
                              age--;
                            }
                            const ageText = `${age} ${age % 10 === 1 && age % 100 !== 11 ? 'год' : age % 10 >= 2 && age % 10 <= 4 && (age % 100 < 10 || age % 100 >= 20) ? 'года' : 'лет'}`;
                            const dateText = birthDate.toLocaleDateString('ru-RU', { 
                              year: 'numeric', 
                              month: 'long', 
                              day: 'numeric' 
                            });
                            return `${dateText} (${ageText})`;
                          })()}
                        </td>
                      </tr>
                    )}
                    {(person.birth_place || person.bio?.birth_place) && (
                      <tr>
                        <td className="px-3 py-2 bg-gray-50 text-gray-600 font-medium">Место рождения</td>
                        <td className="px-3 py-2">г. {person.birth_place || person.bio?.birth_place}</td>
                      </tr>
                    )}
                    {/* Custom fields from bio.extra_fields */}
                    {person.bio?.extra_fields && Object.entries(person.bio.extra_fields).map(([key, value]) => (
                      <tr key={key}>
                        <td className="px-3 py-2 bg-gray-50 text-gray-600 font-medium">{key}</td>
                        <td className="px-3 py-2">{value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
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
  const normalizeRichText = (value) => {
    if (typeof value !== 'string') return value || '';
    let v = value;

    // Common SQL/JSON escape artifacts
    v = v.replace(/\\r\\n/g, '\n').replace(/\\r/g, '\n').replace(/\\n/g, '\n');

    // Расэкраниваем кавычки и слеши
    v = v.replace(/\\"/g, '"').replace(/\\'/g, "'");
    v = v.replace(/\\\//g, '/'); // "\/" -> "/"

    // Иногда попадается "<\/p>" вместо "</p>" и т.п.
    v = v.replace(/<\\\//g, '</');

    // Иногда лишние слэши перед угловыми скобками
    v = v.replace(/\\</g, '<').replace(/\\>/g, '>');

    return v;
  };

  const hasHtmlTags = (value) => {
    const v = normalizeRichText(value);
    return typeof v === 'string' && /<[^>]+>/.test(v);
  };

  switch (module.type) {
    case 'timeline':
      return (
        <Card id={`timeline-${index}`} className="scroll-mt-4">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                {module.data?.period && (
                  <div className="text-sm font-medium text-blue-600 mb-1">
                    {module.data.period}
                  </div>
                )}
                <CardTitle className="text-xl">{module.data?.title || 'Хронология'}</CardTitle>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {/* Render events array if present */}
            {module.data?.events && module.data.events.length > 0 ? (
              <div className="space-y-4">
                {module.data.events.map((event, i) => (
                  <div 
                    key={i} 
                    id={`timeline-${index}-event-${i}`}
                    className="flex gap-4 scroll-mt-4"
                  >
                    <div className="flex flex-col items-center">
                      <div className="w-3 h-3 rounded-full bg-blue-500 flex-shrink-0" />
                      {i < module.data.events.length - 1 && (
                        <div className="w-0.5 flex-1 bg-gray-200 mt-1" />
                      )}
                    </div>
                    <div className="flex-1 pb-4">
                      <div className="text-sm font-medium text-blue-600">
                        {event.date || event.year}
                      </div>
                      <div className="font-medium">{event.title}</div>
                      {event.description && (
                        hasHtmlTags(event.description) ? (
                          <div
                            className="prose prose-sm max-w-none text-gray-600 mt-1"
                            dangerouslySetInnerHTML={{ __html: normalizeRichText(event.description) }}
                          />
                        ) : (
                          <p className="text-gray-600 text-sm mt-1 whitespace-pre-line">{normalizeRichText(event.description)}</p>
                        )
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : module.data?.content_html ? (
              <div 
                className="prose prose-sm max-w-none text-gray-700"
                dangerouslySetInnerHTML={{ __html: module.data.content_html }}
              />
            ) : module.data?.content ? (
              hasHtmlTags(module.data.content) ? (
                <div
                  className="prose prose-sm max-w-none text-gray-700"
                  dangerouslySetInnerHTML={{ __html: normalizeRichText(module.data.content) }}
                />
              ) : (
                <p className="text-gray-700 leading-relaxed whitespace-pre-line">
                  {normalizeRichText(module.data.content)}
                </p>
              )
            ) : null}
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
            ) : hasHtmlTags(module.data?.content) ? (
              <div
                className="prose prose-sm max-w-none text-gray-700"
                dangerouslySetInnerHTML={{ __html: normalizeRichText(module.data.content) }}
              />
            ) : (
              <p className="text-gray-700 leading-relaxed whitespace-pre-line">
                {normalizeRichText(module.data?.content)}
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
              dangerouslySetInnerHTML={{ __html: normalizeRichText(module.data?.content || '') }}
            />
          </CardContent>
        </Card>
      );
    
    default:
      return null;
  }
}
