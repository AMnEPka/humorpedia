import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { publicApi } from '../utils/api';
import ContentTable from './ContentTable';
import { moduleContract } from '@/moduleContract';
import { ModuleFrame, StructuredListModule, ContentWidget, VideoModule } from './AdditionalModules';

/**
 * Renders a single content module based on its type
 */
export default function ModuleRenderer({ module, personId }) {
  if (!module || module.visible === false) return null;

  const { type, data } = module;
  // Эти модули принадлежат sidebar, квизу, лиге или специализированной странице.
  // Их отсутствие в общем потоке — явный контракт, а не неизвестный тип.
  if (['system', 'special'].includes(moduleContract[type]?.kind)) return null;

  switch (type) {
    case 'hero_card':
      return <ModuleFrame module={module}>
        {(data?.image || data?.photo) && <img src={data.image || data.photo} alt={data?.photo_alt || data?.caption || ''} className="max-w-full rounded-lg" />}
        {data?.caption && <p>{data.caption}</p>}
        {data?.facts?.map((fact, i) => <p key={i}><strong>{fact.label || fact.title}: </strong>{fact.value}</p>)}
      </ModuleFrame>;
    case 'tags':
      return <ModuleFrame module={module}><div className="flex flex-wrap gap-2">
        {(data?.tags || []).map((tag, i) => <Link key={i} to={`/tags/${encodeURIComponent(tag)}`} className="rounded bg-gray-100 px-2 py-1">{tag}</Link>)}
      </div></ModuleFrame>;
    case 'team_members':
    case 'tv_appearances':
    case 'games_list':
    case 'episodes_list':
      return <StructuredListModule module={module} />;
    case 'best_articles':
    case 'interesting':
    case 'random_page':
      return <ContentWidget module={module} />;
    case 'text_block':
      // Allow explicit anchor id (for custom TOC / SEO pages)
      // Falls back to a simple slug from title.
      const anchorId = data?.anchor_id || (data?.title ? data.title.toLowerCase().replace(/\s+/g, '-') : null);
      if (data?.collapsed) {
        return (
          <details className="my-6 border rounded-lg">
            <summary className="cursor-pointer select-none px-4 py-3 text-xl font-bold" id={anchorId}>
              {data.title || 'Подробнее'}
            </summary>
            <div className="prose prose-lg max-w-none px-4 pb-4 overflow-x-auto" dangerouslySetInnerHTML={{ __html: data?.content || '' }} />
          </details>
        );
      }
      return (
        <div className="prose prose-lg max-w-none">
          {data?.title && (
            <h2 className="text-xl font-bold mb-3" id={anchorId}>
              {data.title}
            </h2>
          )}
          <div dangerouslySetInnerHTML={{ __html: data?.content || '' }} />
        </div>
      );

    case 'image':
      return (
        <figure className="my-6">
          {data?.url && (
            <img
              src={data.url}
              alt={data.alt || data.caption || ''}
              className="w-full rounded-lg"
            />
          )}
          {data?.caption && (
            <figcaption className="text-sm text-gray-500 mt-2 text-center">
              {data.caption}
            </figcaption>
          )}
        </figure>
      );

    case 'gallery':
      return (
        <div className="my-6">
          {data?.title && <h3 className="text-lg font-bold mb-3">{data.title}</h3>}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {data?.images?.map((img, i) => (
              <div key={i} className="aspect-video rounded-lg overflow-hidden bg-gray-100">
                <img
                  src={img.url}
                  alt={img.alt || img.caption || ''}
                  className="w-full h-full object-cover"
                />
              </div>
            ))}
          </div>
        </div>
      );

    case 'video':
      return <VideoModule module={module} />;

    case 'quote':
      return (
        <blockquote className="my-6 border-l-4 border-blue-500 pl-4 italic text-gray-700">
          <p className="text-lg">{data?.text}</p>
          {data?.author && (
            <cite className="block mt-2 text-sm text-gray-500 not-italic">
              — {data.author}
            </cite>
          )}
        </blockquote>
      );

    case 'timeline':
      return (
        <div className="my-6">
          {data?.title && <h3 className="text-lg font-bold mb-4">{data.title}</h3>}
          <div className="space-y-4">
            {data?.events?.map((event, i) => (
              <div key={i} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <div className="w-3 h-3 rounded-full bg-blue-500" />
                  {i < (data.events.length - 1) && (
                    <div className="w-0.5 h-full bg-gray-200 mt-1" />
                  )}
                </div>
                <div className="flex-1 pb-4">
                  <div className="text-sm font-medium text-blue-600">{event.date || event.year}</div>
                  <div className="font-medium">{event.title}</div>
                  {event.description && (
                    /<\s*\/?\s*[a-zA-Z][^>]*>/.test(event.description) ? (
                      <div
                        className="prose prose-sm max-w-none text-gray-600 mt-1"
                        dangerouslySetInnerHTML={{ __html: event.description }}
                      />
                    ) : (
                      <p className="text-gray-600 text-sm mt-1">{event.description}</p>
                    )
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      );

    case 'person_card':
      return (
        <Card className="my-6">
          <CardContent className="p-4 flex gap-4">
            {data?.photo && (
              <img
                src={data.photo}
                alt={data.name}
                className="w-20 h-20 rounded-full object-cover"
              />
            )}
            <div>
              <h4 className="font-bold">{data?.name}</h4>
              {data?.role && <p className="text-sm text-gray-500">{data.role}</p>}
              {data?.description && <p className="text-sm mt-2">{data.description}</p>}
            </div>
          </CardContent>
        </Card>
      );

    case 'related_links':
      return (
        <div className="my-6 p-4 bg-gray-50 rounded-lg">
          {data?.title && <h3 className="font-bold mb-3">{data.title}</h3>}
          <ul className="space-y-2">
            {data?.links?.map((link, i) => (
              <li key={i}>
                {link.url?.startsWith('/') ? (
                  <Link to={link.url} className="text-blue-600 hover:underline">
                    {link.title}
                  </Link>
                ) : (
                  <a
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    {link.title}
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      );

    case 'table_of_contents':
      // This is usually auto-generated from other modules
      return null;

    case 'table':
      return (
        <div className="my-6">
          {data?.title && <h3 className="text-lg font-bold mb-3">{data.title}</h3>}
          {data?.rows?.length ? <ContentTable data={data} /> : <p className="text-muted-foreground">Пока нет строк таблицы.</p>}
        </div>
      );

    case 'html':
      return (
        <div
          className="prose prose-lg max-w-none my-6"
          dangerouslySetInnerHTML={{ __html: data?.content || '' }}
        />
      );

    case 'divider':
      return <hr className="my-8 border-gray-200" />;

    case 'poll':
      return <PollModule module={module} />;

    default:
      return (
        <div role="alert" className="my-6 rounded border p-4 text-sm">
          Не удалось отобразить блок «{type}». Сообщите редактору страницы.
        </div>
      );
  }
}

function PollModule({ module }) {
  const pollId = module?.data?.poll_id;
  const [poll, setPoll] = useState(null);
  const [selected, setSelected] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    if (!pollId) {
      setLoading(false);
      return undefined;
    }
    publicApi.getPoll(pollId)
      .then((response) => {
        if (!active) return;
        setPoll(response.data);
        setSelected(response.data.selected_option_id || '');
      })
      .catch((requestError) => {
        if (active && requestError.response?.status !== 404) setError('Не удалось загрузить опрос');
      })
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [pollId]);

  const submit = async () => {
    if (!selected || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      const response = await publicApi.votePoll(pollId, selected);
      setPoll(response.data);
    } catch (requestError) {
      const status = requestError.response?.status;
      setError(status === 401
        ? 'Чтобы проголосовать, войдите в личный кабинет.'
        : (requestError.response?.data?.detail || 'Не удалось сохранить голос'));
    } finally {
      setSubmitting(false);
    }
  };

  if (!pollId || (!loading && !poll && !error)) return null;
  if (loading) return <div className="my-6 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-gray-400" /></div>;

  return (
    <Card className="my-8">
      <CardContent className="p-5 sm:p-6">
        {poll && (
          <fieldset>
            <legend className="text-xl font-bold text-gray-900">{poll.question}</legend>
            <div className="mt-4 space-y-3">
              {poll.options.map((option) => {
                const checked = selected === option.id;
                return (
                  <label key={option.id} className={`block rounded-lg border p-3 ${checked ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}>
                    {!poll.selected_option_id && (
                      <input
                        type="radio"
                        name={`poll-${poll.id}`}
                        value={option.id}
                        checked={checked}
                        onChange={() => setSelected(option.id)}
                        className="mr-3"
                      />
                    )}
                    <span className="font-medium">{option.text}</span>
                    {poll.results_visible && (
                      <div className="mt-2" aria-live="polite" aria-label={`${option.percent}% (${option.votes} голосов)`}>
                        <div className="h-2 overflow-hidden rounded-full bg-gray-100">
                          <div className="h-full rounded-full bg-blue-600" style={{ width: `${option.percent}%` }} />
                        </div>
                        <div className="mt-1 text-xs text-gray-600">{option.percent}% · {option.votes}</div>
                      </div>
                    )}
                  </label>
                );
              })}
            </div>
            {!poll.selected_option_id && (
              <Button type="button" className="mt-4" disabled={!selected || submitting} onClick={submit}>
                {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Проголосовать
              </Button>
            )}
            {poll.results_visible && <p className="mt-4 text-sm text-gray-600">Всего голосов: {poll.total_votes}</p>}
          </fieldset>
        )}
        {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
      </CardContent>
    </Card>
  );
}

/**
 * Renders a list of modules
 */
export function ModuleList({ modules, personId }) {
  if (!modules || modules.length === 0) return null;

  const sortedModules = [...modules]
    .filter(m => m.visible !== false)
    .sort((a, b) => (a.order || 0) - (b.order || 0));

  return (
    <div className="space-y-6">
      {sortedModules.map((module, idx) => (
        <ModuleRenderer key={module.id || idx} module={module} personId={personId} />
      ))}
    </div>
  );
}
