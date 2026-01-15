import { useState, useEffect, useCallback, useRef } from 'react';
import { mediaApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Image as ImageIcon, X, Loader2, Search, ChevronLeft, ChevronRight, Upload, Folder, FolderOpen, Home } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function MediaSelector({ value, onChange, label = 'Изображение' }) {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('uploaded'); // 'uploaded' or 'imported'
  
  // Uploaded media state
  const [uploadedMedia, setUploadedMedia] = useState([]);
  const [uploadedTotal, setUploadedTotal] = useState(0);
  const [uploadedPage, setUploadedPage] = useState(1);
  
  // Imported media state
  const [importedMedia, setImportedMedia] = useState([]);
  const [importedTotal, setImportedTotal] = useState(0);
  const [currentPath, setCurrentPath] = useState(''); // Текущий путь для импортированных (пустой = корень images)
  const [pathHistory, setPathHistory] = useState(['']); // История путей для навигации
  
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [uploading, setUploading] = useState(false);
  const [selectedMedia, setSelectedMedia] = useState(null);
  const fileInputRef = useRef(null);
  const limit = 30;

  // Получить полный URL изображения
  const getImageUrl = (url) => {
    if (!url) return '';
    // Если URL уже абсолютный (начинается с http:// или https://)
    if (url.startsWith('http://') || url.startsWith('https://')) {
      return url;
    }
    // Если URL начинается с /, используем как есть
    if (url.startsWith('/')) {
      return url;
    }
    // Иначе добавляем / в начало
    return `/${url}`;
  };

  // Получить URL из value (может быть строкой или объектом)
  const getValueUrl = () => {
    if (!value) return null;
    if (typeof value === 'string') return value;
    return value.url || null;
  };

  // Загрузка загруженных медиа
  const fetchUploadedMedia = useCallback(async () => {
    setLoading(true);
    try {
      const params = { 
        skip: (uploadedPage - 1) * limit, 
        limit, 
        mime_type: 'image/*',
        ...(search && { search }) 
      };
      const response = await mediaApi.list(params);
      setUploadedMedia(response.data.items || []);
      setUploadedTotal(response.data.total || 0);
    } catch (err) {
      console.error('Ошибка загрузки медиа:', err);
      setUploadedMedia([]);
      setUploadedTotal(0);
    } finally {
      setLoading(false);
    }
  }, [uploadedPage, search, limit]);

  // Загрузка импортированных медиа
  const fetchImportedMedia = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        source: 'imported',
        prefix: currentPath || '',
        limit: 1000, // Больше для импортированных, так как они локальные
        ...(search && { query: search })
      };
      const response = await mediaApi.browse(params);
      setImportedMedia(response.data.items || []);
      setImportedTotal(response.data.total || 0);
    } catch (err) {
      console.error('Ошибка загрузки импортированных медиа:', err);
      setImportedMedia([]);
      setImportedTotal(0);
    } finally {
      setLoading(false);
    }
  }, [currentPath, search]);

  useEffect(() => {
    if (open) {
      // Сбрасываем выбранное изображение при открытии
      setSelectedMedia(null);
      // Сбрасываем поиск при открытии
      setSearch('');
      setUploadedPage(1);
      
      if (activeTab === 'uploaded') {
        fetchUploadedMedia();
      } else {
        fetchImportedMedia();
      }
    }
  }, [open, activeTab, fetchUploadedMedia, fetchImportedMedia]);

  const handleSelect = (item) => {
    setSelectedMedia(item);
  };

  const handleConfirm = () => {
    if (selectedMedia) {
      // Для импортированных файлов структура другая
      if (activeTab === 'imported') {
        onChange({
          url: selectedMedia.url,
          alt: selectedMedia.name || '',
          caption: '',
          thumbnail: selectedMedia.url
        });
      } else {
        onChange({
          url: selectedMedia.url,
          alt: selectedMedia.alt || '',
          caption: selectedMedia.caption || '',
          thumbnail: selectedMedia.variants?.thumbnail || selectedMedia.url
        });
      }
      setOpen(false);
      setSelectedMedia(null);
      setSearch('');
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
      const file = files[0];
      const uploadResponse = await mediaApi.upload(file);
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
        setSearch('');
        if (activeTab === 'uploaded') {
          fetchUploadedMedia();
        }
      } else {
        const newMedia = uploadResponse.data;
        onChange({
          url: newMedia.url,
          alt: newMedia.alt || '',
          caption: newMedia.caption || '',
          thumbnail: newMedia.url
        });
        setOpen(false);
        setSearch('');
        if (activeTab === 'uploaded') {
          fetchUploadedMedia();
        }
      }
    } catch (err) {
      console.error('Ошибка загрузки:', err);
    } finally {
      setUploading(false);
      if (fileInputRef?.current) fileInputRef.current.value = '';
    }
  };

  // Навигация по папкам для импортированных
  const handleFolderClick = (folderPath) => {
    setPathHistory(prev => [...prev, folderPath]);
    setCurrentPath(folderPath);
    setSelectedMedia(null);
  };

  const handlePathBack = () => {
    if (pathHistory.length > 1) {
      const newHistory = [...pathHistory];
      newHistory.pop();
      setPathHistory(newHistory);
      setCurrentPath(newHistory[newHistory.length - 1]);
      setSelectedMedia(null);
    }
  };

  const handlePathHome = () => {
    setPathHistory(['']);
    setCurrentPath('');
    setSelectedMedia(null);
  };

  // Группировка импортированных файлов по папкам
  const getFoldersAndFiles = () => {
    const folders = new Set();
    const files = [];
    
    importedMedia.forEach(item => {
      const pathParts = item.path.split('/');
      
      if (currentPath === '') {
        // В корне - показываем только первую папку или файлы в корне
        if (pathParts.length === 1) {
          // Файл в корне
          files.push(item);
        } else {
          // Есть подпапка
          folders.add(pathParts[0]);
        }
      } else {
        // В подпапке - проверяем, начинается ли путь с currentPath
        const currentPathParts = currentPath.split('/');
        if (pathParts.length <= currentPathParts.length) {
          return; // Файл не в этой папке или глубже
        }
        
        // Проверяем, что путь соответствует currentPath
        let matches = true;
        for (let i = 0; i < currentPathParts.length; i++) {
          if (pathParts[i] !== currentPathParts[i]) {
            matches = false;
            break;
          }
        }
        
        if (!matches) {
          return; // Файл не в этой папке
        }
        
        // Относительный путь от currentPath
        const relativeParts = pathParts.slice(currentPathParts.length);
        
        if (relativeParts.length > 1) {
          // Есть подпапка
          folders.add(relativeParts[0]);
        } else {
          // Файл в текущей папке
          files.push(item);
        }
      }
    });

    return { folders: Array.from(folders).sort(), files };
  };

  const { folders, files } = activeTab === 'imported' ? getFoldersAndFiles() : { folders: [], files: [] };
  const uploadedTotalPages = Math.ceil(uploadedTotal / limit);
  const isImage = (mime) => !mime || mime?.startsWith('image/');

  // Получить имя файла из пути
  const getFileName = (path) => {
    return path.split('/').pop();
  };

  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex items-center gap-2">
        {getValueUrl() ? (
          <div className="relative group">
            <img 
              src={getImageUrl(getValueUrl())} 
              alt={typeof value === 'string' ? '' : (value?.alt || '')} 
              className="w-32 h-32 object-cover rounded-lg border"
              onError={(e) => {
                // Если изображение не загрузилось, показываем placeholder
                e.target.style.display = 'none';
                const placeholder = e.target.nextElementSibling;
                if (placeholder) {
                  placeholder.style.display = 'flex';
                }
              }}
            />
            <div className="w-32 h-32 border-2 border-dashed rounded-lg items-center justify-center bg-muted hidden">
              <ImageIcon className="h-8 w-8 text-muted-foreground" />
            </div>
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
            {getValueUrl() ? 'Изменить' : 'Выбрать изображение'}
          </Button>
          {getValueUrl() && (
            <Button type="button" variant="ghost" size="sm" onClick={handleRemove}>
              Удалить
            </Button>
          )}
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Выберите изображение</DialogTitle>
          </DialogHeader>
          
          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="uploaded">Загруженные</TabsTrigger>
              <TabsTrigger value="imported">Импортированные</TabsTrigger>
            </TabsList>

            <TabsContent value="uploaded" className="flex-1 flex flex-col overflow-hidden mt-4">
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
                        setUploadedPage(1);
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
                  ) : uploadedMedia.length === 0 ? (
                    <Card>
                      <CardContent className="py-12 text-center text-muted-foreground">
                        <ImageIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
                        <p>Нет изображений</p>
                      </CardContent>
                    </Card>
                  ) : (
                    <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                      {uploadedMedia.map((item) => (
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
                              src={getImageUrl(item.url)}
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
                {uploadedTotalPages > 1 && (
                  <div className="flex items-center justify-center gap-2">
                    <Button
                      variant="outline"
                      size="icon"
                      disabled={uploadedPage <= 1}
                      onClick={() => setUploadedPage((p) => p - 1)}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm">
                      {uploadedPage} / {uploadedTotalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="icon"
                      disabled={uploadedPage >= uploadedTotalPages}
                      onClick={() => setUploadedPage((p) => p + 1)}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="imported" className="flex-1 flex flex-col overflow-hidden mt-4">
              <div className="flex-1 overflow-hidden flex flex-col gap-4">
                {/* Path Navigation */}
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handlePathHome}
                    title="В корень"
                  >
                    <Home className="h-4 w-4" />
                  </Button>
                  {pathHistory.length > 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={handlePathBack}
                      title="Назад"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                  )}
                  <div className="flex-1 text-sm text-muted-foreground truncate">
                    images{currentPath ? '/' + currentPath : ''}
                  </div>
                </div>

                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Поиск по имени файла..."
                    className="pl-9"
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                    }}
                  />
                </div>

                {/* Folders and Files Grid */}
                <div className="flex-1 overflow-y-auto">
                  {loading ? (
                    <div className="flex items-center justify-center h-64">
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    </div>
                  ) : folders.length === 0 && files.length === 0 ? (
                    <Card>
                      <CardContent className="py-12 text-center text-muted-foreground">
                        <ImageIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
                        <p>Нет изображений в этой папке</p>
                      </CardContent>
                    </Card>
                  ) : (
                    <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                      {/* Папки */}
                      {folders.map((folder) => {
                        const folderPath = currentPath === '' ? folder : `${currentPath}/${folder}`;
                        return (
                          <div
                            key={folder}
                            onClick={() => handleFolderClick(folderPath)}
                            className="relative aspect-square rounded-lg border-2 border-dashed border-muted-foreground/30 overflow-hidden cursor-pointer transition-all hover:shadow-md hover:border-primary"
                          >
                            <div className="w-full h-full flex flex-col items-center justify-center bg-muted/50">
                              <FolderOpen className="h-12 w-12 text-muted-foreground mb-2" />
                              <span className="text-xs text-center px-2 truncate w-full">{folder}</span>
                            </div>
                          </div>
                        );
                      })}
                      
                      {/* Файлы */}
                      {files.map((item) => (
                        <div
                          key={item.path}
                          onClick={() => handleSelect(item)}
                          className={cn(
                            "relative aspect-square rounded-lg border-2 overflow-hidden cursor-pointer transition-all hover:shadow-md",
                            selectedMedia?.path === item.path
                              ? "border-primary ring-2 ring-primary"
                              : "border-transparent"
                          )}
                        >
                          <img
                            src={getImageUrl(item.url)}
                            alt={item.name}
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              e.target.style.display = 'none';
                              if (!e.target.nextSibling) {
                                const placeholder = document.createElement('div');
                                placeholder.className = 'w-full h-full flex items-center justify-center bg-muted';
                                placeholder.innerHTML = '<svg class="h-8 w-8 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>';
                                e.target.parentElement.appendChild(placeholder);
                              }
                            }}
                          />
                          {selectedMedia?.path === item.path && (
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

                {importedTotal > 0 && (
                  <div className="text-sm text-muted-foreground text-center">
                    Найдено: {importedTotal} {importedTotal === 1 ? 'файл' : 'файлов'}
                  </div>
                )}
              </div>
            </TabsContent>
          </Tabs>

          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setOpen(false);
              setSelectedMedia(null);
              setSearch('');
            }}>
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
