import { useState, useEffect, useCallback, useRef } from 'react';
import { mediaApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Card, CardContent } from '@/components/ui/card';
import { Image as ImageIcon, X, Loader2, Search, ChevronLeft, ChevronRight, Upload } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function MediaSelector({ value, onChange, label = 'Изображение' }) {
  const [open, setOpen] = useState(false);
  const [media, setMedia] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [uploading, setUploading] = useState(false);
  const [selectedMedia, setSelectedMedia] = useState(null);
  const fileInputRef = useRef(null);
  const limit = 30;

  const fetchMedia = useCallback(async () => {
    setLoading(true);
    try {
      const params = { 
        skip: (page - 1) * limit, 
        limit, 
        mime_type: 'image/*',
        ...(search && { search }) 
      };
      const response = await mediaApi.list(params);
      setMedia(response.data.items);
      setTotal(response.data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    if (open) {
      fetchMedia();
    }
  }, [open, fetchMedia]);

  const handleSelect = (item) => {
    setSelectedMedia(item);
  };

  const handleConfirm = () => {
    if (selectedMedia) {
      onChange({
        url: selectedMedia.url,
        alt: selectedMedia.alt || '',
        caption: selectedMedia.caption || '',
        thumbnail: selectedMedia.variants?.thumbnail || selectedMedia.url
      });
      setOpen(false);
      setSelectedMedia(null);
    }
  };

  const handleRemove = () => {
    onChange(null);
  };

  const handleUpload = async (e) => {
    const files = e.target.files;
    if (!files?.length) return;
    setUploading(true);
    try {
      const file = files[0]; // Берем только первый файл
      const uploadResponse = await mediaApi.upload(file);
      // Получаем полный объект Media после загрузки
      const mediaId = uploadResponse.data.id || uploadResponse.data._id;
      if (mediaId) {
        const fullMedia = await mediaApi.get(mediaId);
        const newMedia = fullMedia.data;
        onChange({
          url: newMedia.url,
          alt: newMedia.alt || '',
          caption: newMedia.caption || '',
          thumbnail: newMedia.variants?.thumbnail || newMedia.url
        });
        setOpen(false);
        fetchMedia();
      } else {
        // Если нет ID, используем данные из ответа загрузки
        const newMedia = uploadResponse.data;
        onChange({
          url: newMedia.url,
          alt: newMedia.alt || '',
          caption: newMedia.caption || '',
          thumbnail: newMedia.url
        });
        setOpen(false);
        fetchMedia();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setUploading(false);
      if (fileInputRef?.current) fileInputRef.current.value = '';
    }
  };

  const totalPages = Math.ceil(total / limit);
  const isImage = (mime) => mime?.startsWith('image/');

  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex items-center gap-2">
        {value?.url ? (
          <div className="relative group">
            <img 
              src={value.url} 
              alt={value.alt || ''} 
              className="w-32 h-32 object-cover rounded-lg border"
            />
            <Button
              type="button"
              variant="destructive"
              size="icon"
              className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={handleRemove}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <div className="w-32 h-32 border-2 border-dashed rounded-lg flex items-center justify-center bg-muted">
            <ImageIcon className="h-8 w-8 text-muted-foreground" />
          </div>
        )}
        <div className="flex flex-col gap-2">
          <Button type="button" variant="outline" onClick={() => setOpen(true)}>
            {value?.url ? 'Изменить' : 'Выбрать изображение'}
          </Button>
          {value?.url && (
            <Button type="button" variant="ghost" size="sm" onClick={handleRemove}>
              Удалить
            </Button>
          )}
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Выберите изображение</DialogTitle>
          </DialogHeader>
          
          <div className="flex-1 overflow-hidden flex flex-col gap-4">
            {/* Search and Upload */}
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Поиск файлов..."
                  className="pl-9"
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(1);
                  }}
                />
              </div>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleUpload}
                className="hidden"
                accept="image/*"
                multiple={false}
              />
              <Button
                variant="outline"
                onClick={() => fileInputRef?.current?.click()}
                disabled={uploading}
              >
                {uploading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="mr-2 h-4 w-4" />
                )}
                Загрузить
              </Button>
            </div>

            {/* Media Grid */}
            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="flex items-center justify-center h-64">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
              ) : media.length === 0 ? (
                <Card>
                  <CardContent className="py-12 text-center text-muted-foreground">
                    <ImageIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>Нет изображений</p>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                  {media.map((item) => (
                    <div
                      key={item._id}
                      onClick={() => handleSelect(item)}
                      className={cn(
                        "relative aspect-square rounded-lg border-2 overflow-hidden cursor-pointer transition-all hover:shadow-md",
                        selectedMedia?._id === item._id
                          ? "border-primary ring-2 ring-primary"
                          : "border-transparent"
                      )}
                    >
                      {isImage(item.mime_type) ? (
                        <img
                          src={item.url}
                          alt={item.alt || item.filename}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center bg-muted">
                          <ImageIcon className="h-8 w-8 text-muted-foreground" />
                        </div>
                      )}
                      {selectedMedia?._id === item._id && (
                        <div className="absolute inset-0 bg-primary/20 flex items-center justify-center">
                          <div className="bg-primary text-primary-foreground rounded-full p-2">
                            <ImageIcon className="h-6 w-6" />
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2">
                <Button
                  variant="outline"
                  size="icon"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Отмена
            </Button>
            <Button onClick={handleConfirm} disabled={!selectedMedia}>
              Выбрать
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

