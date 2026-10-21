import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';


export default function VideoModuleEditor({ data, updateData }) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>URL видео (YouTube, VK)</Label>
        <Input
          value={data.url || ''}
          onChange={(e) => updateData({ ...data, url: e.target.value })}
          placeholder="https://www.youtube.com/watch?v=..."
        />
      </div>
      <div className="space-y-2">
        <Label>Заголовок</Label>
        <Input
          value={data.title || ''}
          onChange={(e) => updateData({ ...data, title: e.target.value })}
          placeholder="Название видео"
        />
      </div>
    </div>
  );
}
