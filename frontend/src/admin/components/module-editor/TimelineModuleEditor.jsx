import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Trash2, Plus } from 'lucide-react';
import RichTextEditor from '../RichTextEditor';
import { withTimelineEvents } from './operations';

export default function TimelineModuleEditor({ data, updateData }) {
  // В контенте timeline хранится в data.events.
  // Ранее редактор использовал data.items — поддерживаем оба формата.
  const events = data.events || data.items || [];
  const setEvents = (events) => updateData(withTimelineEvents(data, events));

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Заголовок блока</Label>
        <Input
          value={data.title || ''}
          onChange={(e) => updateData({ ...data, title: e.target.value })}
          placeholder="Хронология"
        />
      </div>

      <div className="space-y-4">
        {events.map((item, index) => (
          <div key={index} className="border rounded-lg p-4 space-y-3 bg-muted/20">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Событие {index + 1}</span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setEvents(events.filter((_, i) => i !== index))}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Год / период</Label>
                <Input
                  value={item.year || item.date || ''}
                  onChange={(e) => {
                    const newEvents = [...events];
                    newEvents[index] = { ...newEvents[index], year: e.target.value };
                    setEvents(newEvents);
                  }}
                  placeholder="2007-2013"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Заголовок</Label>
                <Input
                  value={item.title || ''}
                  onChange={(e) => {
                    const newEvents = [...events];
                    newEvents[index] = { ...newEvents[index], title: e.target.value };
                    setEvents(newEvents);
                  }}
                  placeholder="Название события"
                />
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Описание</Label>
              <RichTextEditor
                content={item.description || ''}
                onChange={(html) => {
                  const newEvents = [...events];
                  newEvents[index] = { ...newEvents[index], description: html };
                  setEvents(newEvents);
                }}
                placeholder="Описание события..."
                minHeight={100}
              />
            </div>
          </div>
        ))}
      </div>

      <Button
        type="button"
        variant="outline"
        onClick={() => setEvents([
          ...events,
          { year: '', title: '', description: '' }
        ])}
        className="w-full"
      >
        <Plus className="mr-2 h-4 w-4" /> Добавить событие
      </Button>
    </div>
  );
}
