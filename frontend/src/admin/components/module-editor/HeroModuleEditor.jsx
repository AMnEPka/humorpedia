import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';


export default function HeroModuleEditor({ data, updateData }) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>URL изображения</Label>
        <Input
          value={data.image || ''}
          onChange={(e) => updateData({ ...data, image: e.target.value })}
          placeholder="https://..."
        />
      </div>
      <div className="space-y-2">
        <Label>Подпись</Label>
        <Input
          value={data.caption || ''}
          onChange={(e) => updateData({ ...data, caption: e.target.value })}
          placeholder="Описание фото"
        />
      </div>
    </div>
  );
}
