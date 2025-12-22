import { useState, useEffect, useCallback, useRef } from 'react';
import { mediaApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Upload, Search, Trash2, Loader2, Image as ImageIcon, FileText, Copy, Check, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function MediaPage() {
  const [media, setMedia] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedMedia, setSelectedMedia] = useState(null);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);
  const limit = 30;

  const fetchMedia = useCallback(async () => {
    setLoading(true);
    try {
      const params = { skip: (page - 1) * limit, limit, ...(search && { search }) };
      const response = await mediaApi.list(params);
      setMedia(response.data.items);
      setTotal(response.data.total);
    } catch (err) { console.error(err); } finally { setLoading(false); }
  }, [page, search]);

  useEffect(() => { fetchMedia(); }, [fetchMedia]);

  const handleUpload = async (e) => {
    const files = e.target.files;
    if (!files?.length) return;
    setUploading(true); setError('');
    try {
      for (const file of files) {
        await mediaApi.upload(file);
      }
      fetchMedia();
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка загрузки');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Удалить файл?')) return;
    try {
      await mediaApi.delete(id);
      setSelectedMedia(null);
      fetchMedia();
    } catch (err) { console.error(err); }
  };

  const copyUrl = (url) => {
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const totalPages = Math.ceil(total / limit);
  const isImage = (mime) => mime?.startsWith('image/');

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-3xl font-bold">Медиабиблиотека</h1><p className="text-muted-foreground">Управление изображениями и файлами</p></div>
        <div>
          <input type="file" ref={fileInputRef} onChange={handleUpload} className="hidden" multiple accept="image/*,.pdf,.doc,.docx" />
          <Button onClick={() => fileInputRef.current?.click()} disabled={uploading}>
            {uploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />} Загрузить
          </Button>
        </div>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      <Card><CardContent className="pt-6">
        <div className="relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" /><Input placeholder="Поиск файлов..." className="pl-9" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} /></div>
      </CardContent></Card>

      {loading ? <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div> : media.length === 0 ? (
        <Card><CardContent className="py-12 text-center text-muted-foreground"><ImageIcon className="h-12 w-12 mx-auto mb-4 opacity-50" /><p>Нет файлов</p></CardContent></Card>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {media.map((item) => (
            <div key={item._id} onClick={() => setSelectedMedia(item)} className={cn("relative aspect-square rounded-lg border-2 overflow-hidden cursor-pointer transition-all hover:shadow-md", selectedMedia?._id === item._id ? "border-primary" : "border-transparent")}>
              {isImage(item.mime_type) ? <img src={item.url} alt={item.alt || item.filename} className="w-full h-full object-cover" /> : <div className="w-full h-full flex flex-col items-center justify-center bg-muted"><FileText className="h-8 w-8 text-muted-foreground" /><span className="text-xs mt-2 text-muted-foreground truncate max-w-full px-2">{item.filename}</span></div>}
            </div>
          ))}
        </div>
      )}

      {totalPages > 1 && <div className="flex items-center justify-center gap-2"><Button variant="outline" size="icon" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="h-4 w-4" /></Button><span className="text-sm">{page} / {totalPages}</span><Button variant="outline" size="icon" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}><ChevronRight className="h-4 w-4" /></Button></div>}

      <Dialog open={!!selectedMedia} onOpenChange={() => setSelectedMedia(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Информация о файле</DialogTitle></DialogHeader>
          {selectedMedia && (
            <div className="grid md:grid-cols-2 gap-4">
              <div className="aspect-square rounded-lg overflow-hidden bg-muted">
                {isImage(selectedMedia.mime_type) ? <img src={selectedMedia.url} alt="" className="w-full h-full object-contain" /> : <div className="w-full h-full flex items-center justify-center"><FileText className="h-16 w-16 text-muted-foreground" /></div>}
              </div>
              <div className="space-y-4">
                <div><Label className="text-muted-foreground">Имя файла</Label><p className="font-medium">{selectedMedia.original_name}</p></div>
                <div><Label className="text-muted-foreground">Размер</Label><p className="font-medium">{(selectedMedia.file_size / 1024).toFixed(1)} KB</p></div>
                {selectedMedia.width && <div><Label className="text-muted-foreground">Размеры</Label><p className="font-medium">{selectedMedia.width} x {selectedMedia.height}</p></div>}
                <div><Label className="text-muted-foreground">URL</Label><div className="flex gap-2"><Input value={selectedMedia.url} readOnly className="font-mono text-xs" /><Button variant="outline" size="icon" onClick={() => copyUrl(selectedMedia.url)}>{copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}</Button></div></div>
              </div>
            </div>
          )}
          <DialogFooter><Button variant="destructive" onClick={() => handleDelete(selectedMedia?._id)}><Trash2 className="mr-2 h-4 w-4" /> Удалить</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
