import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import RichTextEditor from '../RichTextEditor';


export default function TextModuleEditor({ data, updateData }) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Заголовок</Label>
        <Input
          value={data.title || ''}
          onChange={(e) => updateData({ ...data, title: e.target.value })}
          placeholder="Биография"
        />
      </div>
      <div className="flex items-center gap-2">
        <Switch
          checked={Boolean(data.collapsed)}
          onCheckedChange={(v) => updateData({ ...data, collapsed: v })}
        />
        <Label>Свёрнут по умолчанию (раскрывается по клику на заголовок)</Label>
      </div>
      <div className="space-y-2">
        <Label>Содержимое</Label>
        <RichTextEditor
          content={data.content || ''}
          onChange={(html) => updateData({ ...data, content: html })}
          placeholder="Начните вводить текст..."
        />
      </div>
    </div>
  );
}
