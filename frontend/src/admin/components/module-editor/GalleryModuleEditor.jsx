import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Trash2, Plus } from 'lucide-react';


export default function GalleryModuleEditor({ data, updateData }) {
  const galleryItems = data.images || [];
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Заголовок галереи</Label>
        <Input
          value={data.title || ''}
          onChange={(e) => updateData({ ...data, title: e.target.value })}
          placeholder="Фотогалерея"
        />
      </div>
      <div className="space-y-3">
        {galleryItems.map((img, index) => (
          <div key={index} className="border rounded-lg p-3 space-y-2">
            <Input
              aria-label={`Изображение ${index + 1}: URL`}
              value={img.url || ''}
              onChange={(e) => {
                const newImages = [...galleryItems];
                newImages[index] = { ...newImages[index], url: e.target.value };
                updateData({ ...data, images: newImages });
              }}
              placeholder="URL изображения"
              className="flex-1"
            />
            <Input
              aria-label={`Изображение ${index + 1}: подпись`}
              value={img.caption || ''}
              onChange={event => updateData({ ...data, images: galleryItems.map((item, i) =>
                i === index ? { ...item, caption: event.target.value } : item) })}
              placeholder="Подпись"
            />
            <Input
              aria-label={`Изображение ${index + 1}: описание`}
              value={img.alt || ''}
              onChange={event => updateData({ ...data, images: galleryItems.map((item, i) =>
                i === index ? { ...item, alt: event.target.value } : item) })}
              placeholder="Описание изображения (alt)"
            />
            <Button
              type="button"
              aria-label={`Удалить изображение ${index + 1}`}
              variant="ghost"
              size="icon"
              onClick={() => updateData({ ...data, images: galleryItems.filter((_, i) => i !== index) })}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </div>
      <Button
        type="button"
        variant="outline"
        onClick={() => updateData({
          ...data,
          images: [...galleryItems, { url: '', caption: '' }]
        })}
        className="w-full"
      >
        <Plus className="mr-2 h-4 w-4" /> Добавить изображение
      </Button>
    </div>
  );
}
