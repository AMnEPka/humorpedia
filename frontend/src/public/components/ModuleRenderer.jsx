import { Card, CardContent } from '@/components/ui/card';
import { Link } from 'react-router-dom';

/**
 * Renders a single content module based on its type
 */
export default function ModuleRenderer({ module }) {
  if (!module || module.visible === false) return null;

  const { type, data } = module;

  switch (type) {
    case 'text_block':
      return (
        <div className="prose prose-lg max-w-none">
          {data?.title && (
            <h2 className="text-xl font-bold mb-3" id={data.title.toLowerCase().replace(/\s+/g, '-')}>
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
              alt={data.caption || ''}
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

    case 'image_gallery':
      return (
        <div className="my-6">
          {data?.title && <h3 className="text-lg font-bold mb-3">{data.title}</h3>}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {data?.images?.map((img, i) => (
              <div key={i} className="aspect-video rounded-lg overflow-hidden bg-gray-100">
                <img
                  src={img.url}
                  alt={img.caption || ''}
                  className="w-full h-full object-cover"
                />
              </div>
            ))}
          </div>
        </div>
      );

    case 'video_embed':
      return (
        <div className="my-6">
          {data?.title && <h3 className="text-lg font-bold mb-3">{data.title}</h3>}
          <div className="aspect-video rounded-lg overflow-hidden bg-black">
            <iframe
              src={data?.url}
              className="w-full h-full"
              allowFullScreen
              title={data?.title || 'Video'}
            />
          </div>
        </div>
      );

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
                    <p className="text-gray-600 text-sm mt-1">{event.description}</p>
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

    case 'html':
      return (
        <div
          className="prose prose-lg max-w-none my-6"
          dangerouslySetInnerHTML={{ __html: data?.content || '' }}
        />
      );

    case 'divider':
      return <hr className="my-8 border-gray-200" />;

    default:
      // For unknown module types, try to render content if available
      if (data?.content) {
        return (
          <div className="prose prose-lg max-w-none my-6">
            {data?.title && <h3 className="text-lg font-bold mb-3">{data.title}</h3>}
            <div dangerouslySetInnerHTML={{ __html: data.content }} />
          </div>
        );
      }
      return null;
  }
}

/**
 * Renders a list of modules
 */
export function ModuleList({ modules }) {
  if (!modules || modules.length === 0) return null;

  const sortedModules = [...modules]
    .filter(m => m.visible !== false)
    .sort((a, b) => (a.order || 0) - (b.order || 0));

  return (
    <div className="space-y-6">
      {sortedModules.map((module, idx) => (
        <ModuleRenderer key={module.id || idx} module={module} />
      ))}
    </div>
  );
}
