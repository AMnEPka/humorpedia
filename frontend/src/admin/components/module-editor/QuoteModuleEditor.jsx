import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';


export default function QuoteModuleEditor({ data, updateData }) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Текст цитаты</Label>
        <Textarea
          value={data.text || ''}
          onChange={(e) => updateData({ ...data, text: e.target.value })}
          placeholder="Цитата..."
          rows={4}
        />
      </div>
      <div className="space-y-2">
        <Label>Автор</Label>
        <Input
          value={data.author || ''}
          onChange={(e) => updateData({ ...data, author: e.target.value })}
          placeholder="Имя автора"
        />
      </div>
    </div>
  );
}
