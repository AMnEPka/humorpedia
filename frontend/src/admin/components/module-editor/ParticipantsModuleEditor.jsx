import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Trash2, X, Plus } from 'lucide-react';


export default function ParticipantsModuleEditor({ data, updateData }) {
  // Карточки участников шоу: имя, страница человека (slug), фото, факты «название — значение»
  const items = data.items || [];
  const setItems = (next) => updateData({ ...data, items: next });
  const setItem = (index, patch) => setItems(items.map((it, i) => (i === index ? { ...it, ...patch } : it)));
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Заголовок блока</Label>
        <Input
          value={data.title || ''}
          onChange={(e) => updateData({ ...data, title: e.target.value })}
          placeholder="Участники"
        />
      </div>
      {items.map((item, index) => (
        <div key={index} className="border rounded-lg p-4 space-y-3 bg-muted/20">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{item.name || `Участник ${index + 1}`}</span>
            <Button variant="ghost" size="icon" onClick={() => setItems(items.filter((_, i) => i !== index))}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
          <div className="grid sm:grid-cols-3 gap-2">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Имя</Label>
              <Input value={item.name || ''} onChange={(e) => setItem(index, { name: e.target.value })} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Страница человека (slug)</Label>
              <Input value={item.person_slug || ''} onChange={(e) => setItem(index, { person_slug: e.target.value || null })} placeholder="anton-shastun" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Фото (URL)</Label>
              <Input value={item.photo || ''} onChange={(e) => setItem(index, { photo: e.target.value })} placeholder="/media/imported/images/..." />
            </div>
          </div>
          {(item.facts || []).map((fact, j) => (
            <div key={j} className="flex gap-2">
              <Input
                className="w-1/3"
                value={fact.title || ''}
                placeholder="Название"
                onChange={(e) => setItem(index, { facts: item.facts.map((f, k) => (k === j ? { ...f, title: e.target.value } : f)) })}
              />
              <Input
                className="flex-1"
                value={fact.value || ''}
                placeholder="Значение"
                onChange={(e) => setItem(index, { facts: item.facts.map((f, k) => (k === j ? { ...f, value: e.target.value } : f)) })}
              />
              <Button variant="ghost" size="icon" onClick={() => setItem(index, { facts: item.facts.filter((_, k) => k !== j) })}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={() => setItem(index, { facts: [...(item.facts || []), { title: '', value: '' }] })}>
            <Plus className="mr-1 h-3 w-3" /> Факт
          </Button>
        </div>
      ))}
      <Button variant="outline" onClick={() => setItems([...items, { name: '', person_slug: null, photo: '', facts: [] }])}>
        <Plus className="mr-2 h-4 w-4" /> Добавить участника
      </Button>
    </div>
  );

}
