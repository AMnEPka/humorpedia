import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

// Domain renderers supply their existing anchors, typography and normalized HTML.
export default function TextModuleCard({
  id, title, className, content = '', styles, bodyClassName = 'prose prose-sm max-w-none',
}) {
  return (
    <Card id={id} className={className}>
      {title && <CardHeader><CardTitle>{title}</CardTitle></CardHeader>}
      <CardContent>
        {styles && <style>{styles}</style>}
        <div className={bodyClassName} dangerouslySetInnerHTML={{ __html: content }} />
      </CardContent>
    </Card>
  );
}
