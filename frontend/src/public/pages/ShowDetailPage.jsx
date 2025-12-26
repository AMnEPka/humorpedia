import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { publicApi } from '../utils/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Loader2, Calendar, Tv, Users, ExternalLink, Trophy } from 'lucide-react';
import RatingWidget from '../components/RatingWidget';

// Module renderer component
function ModuleRenderer({ module }) {
  if (!module?.visible) return null;
  
  switch (module.type) {
    case 'text_block':
      return (
        <div className="prose prose-lg max-w-none">
          {module.data?.title && <h2 className="text-xl font-bold mb-3">{module.data.title}</h2>}
          <div dangerouslySetInnerHTML={{ __html: module.data?.content || '' }} />
        </div>
      );
    
    case 'image_gallery':
      return (
        <div>
          {module.data?.title && <h3 className="text-lg font-bold mb-3">{module.data.title}</h3>}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {module.data?.images?.map((img, i) => (
              <div key={i} className="aspect-video rounded-lg overflow-hidden bg-muted">
                <img src={img.url} alt={img.caption || ''} className="w-full h-full object-cover" />
              </div>
            ))}
          </div>
        </div>
      );
    
    case 'video_embed':
      return (
        <div>
          {module.data?.title && <h3 className="text-lg font-bold mb-3">{module.data.title}</h3>}
          <div className="aspect-video rounded-lg overflow-hidden bg-black">
            <iframe
              src={module.data?.url}
              className="w-full h-full"
              allowFullScreen
              title={module.data?.title || 'Video'}
            />
          </div>
        </div>
      );
    
    case 'cast_list':
      return (
        <div>
          <h3 className="text-lg font-bold mb-3">{module.data?.title || 'Участники'}</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {module.data?.cast?.map((person, i) => (
              <Link
                key={i}
                to={`/people/${person.slug || person.id}`}
                className="text-center group"
              >
                <div className="aspect-square rounded-full overflow-hidden bg-muted mb-2 mx-auto w-20 h-20">
                  {person.photo ? (
                    <img src={person.photo} alt={person.name} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-2xl font-bold text-muted-foreground">
                      {person.name?.[0]}
                    </div>
                  )}
                </div>
                <div className="font-medium text-sm group-hover:text-primary transition-colors">
                  {person.name}
                </div>
                {person.role && (
                  <div className="text-xs text-muted-foreground">{person.role}</div>
                )}
              </Link>
            ))}
          </div>
        </div>
      );
    
    case 'seasons_list':
      return (
        <div>
          <h3 className="text-lg font-bold mb-3">{module.data?.title || 'Сезоны'}</h3>
          <div className="space-y-2">
            {module.data?.seasons?.map((season, i) => (
              <Card key={i}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{season.title || `Сезон ${i + 1}`}</div>
                      {season.year && (
                        <div className="text-sm text-muted-foreground">{season.year}</div>
                      )}
                    </div>
                    {season.episodes_count && (
                      <Badge variant="secondary">{season.episodes_count} серий</Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      );
    
    default:
      return null;
  }
}

export default function ShowDetailPage() {
  const { slug } = useParams();
  const [show, setShow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    publicApi.getShow(slug)
      .then(res => setShow(res.data))
      .catch(() => setError('Шоу не найдено'))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !show) {
    return (
      <div className="container max-w-4xl mx-auto py-12 px-4 text-center">
        <h1 className="text-2xl font-bold mb-4">Шоу не найдено</h1>
        <Button asChild>
          <Link to="/shows">← К списку шоу</Link>
        </Button>
      </div>
    );
  }

  const facts = show.facts || {};

  return (
    <div className="container max-w-6xl mx-auto py-8 px-4">
      {/* Hero section */}
      <div className="grid md:grid-cols-3 gap-8 mb-8">
        {/* Poster */}
        <div className="md:col-span-1">
          <div className="aspect-[2/3] rounded-xl overflow-hidden bg-muted shadow-lg">
            {show.poster?.url ? (
              <img
                src={show.poster.url}
                alt={show.title}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <Tv className="h-16 w-16 text-muted-foreground" />
              </div>
            )}
          </div>
        </div>
        
        {/* Info */}
        <div className="md:col-span-2 space-y-6">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold mb-2">{show.name || show.title}</h1>
            {show.title !== show.name && (
              <p className="text-xl text-muted-foreground">{show.title}</p>
            )}
          </div>
          
          {/* Tags */}
          {show.tags?.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {show.tags.map(tag => (
                <Badge key={tag} variant="secondary">{tag}</Badge>
              ))}
            </div>
          )}
          
          {/* Description */}
          {show.description && (
            <p className="text-lg text-muted-foreground leading-relaxed">
              {show.description}
            </p>
          )}
          
          {/* Facts */}
          <Card>
            <CardContent className="p-4">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {facts.channel && (
                  <div>
                    <div className="text-sm text-muted-foreground">Канал</div>
                    <div className="font-medium">{facts.channel}</div>
                  </div>
                )}
                {facts.years && (
                  <div>
                    <div className="text-sm text-muted-foreground flex items-center gap-1">
                      <Calendar className="h-3 w-3" /> Годы выхода
                    </div>
                    <div className="font-medium">{facts.years}</div>
                  </div>
                )}
                {facts.genre && (
                  <div>
                    <div className="text-sm text-muted-foreground">Жанр</div>
                    <div className="font-medium">{facts.genre}</div>
                  </div>
                )}
                {facts.seasons_count && (
                  <div>
                    <div className="text-sm text-muted-foreground">Сезонов</div>
                    <div className="font-medium">{facts.seasons_count}</div>
                  </div>
                )}
                {facts.episodes_count && (
                  <div>
                    <div className="text-sm text-muted-foreground">Серий</div>
                    <div className="font-medium">{facts.episodes_count}</div>
                  </div>
                )}
                {facts.rating && (
                  <div>
                    <div className="text-sm text-muted-foreground">Рейтинг</div>
                    <div className="font-medium">⭐ {facts.rating}</div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
          
          {/* External links */}
          {show.social_links && Object.keys(show.social_links).length > 0 && (
            <div className="flex flex-wrap gap-2">
              {show.social_links.website && (
                <Button variant="outline" size="sm" asChild>
                  <a href={show.social_links.website} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="mr-2 h-4 w-4" /> Официальный сайт
                  </a>
                </Button>
              )}
              {show.social_links.youtube && (
                <Button variant="outline" size="sm" asChild>
                  <a href={show.social_links.youtube} target="_blank" rel="noopener noreferrer">
                    YouTube
                  </a>
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* Modules / Content blocks */}
      {show.modules?.length > 0 && (
        <div className="space-y-8">
          {show.modules
            .filter(m => m.visible !== false)
            .sort((a, b) => (a.order || 0) - (b.order || 0))
            .map((module, idx) => (
              <Card key={module.id || idx}>
                <CardContent className="p-6">
                  <ModuleRenderer module={module} />
                </CardContent>
              </Card>
            ))}
        </div>
      )}
      
      {/* Related content */}
      <div className="mt-12">
        <Button variant="outline" asChild>
          <Link to="/shows">← Все шоу</Link>
        </Button>
      </div>
    </div>
  );
}
