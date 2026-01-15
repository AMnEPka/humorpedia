import { useState, useEffect, useCallback, useRef } from 'react';
import { mediaApi } from '../utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Upload, Search, Trash2, Loader2, Image as ImageIcon, FileText, Copy, Check, ChevronLeft, ChevronRight, Folder, ArrowUp, Grid3x3, List, Edit2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function MediaPage() {
  const [activeTab, setActiveTab] = useState('uploaded'); // 'uploaded', 'imported', 'images'
  
  // Uploaded media state
  const [media, setMedia] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  
  // Imported/Images media state
  const [browsedMedia, setBrowsedMedia] = useState([]);
  const [browsedFolders, setBrowsedFolders] = useState([]);
  const [browsedTotal, setBrowsedTotal] = useState(0);
  const [currentPath, setCurrentPath] = useState('');
  const [parentPath, setParentPath] = useState(null);
  const [viewMode, setViewMode] = useState('grid'); // 'grid' or 'list'
  
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedMedia, setSelectedMedia] = useState(null);
  const [search, setSearch] = useState('');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const [renamingItem, setRenamingItem] = useState(null);
  const [newFileName, setNewFileName] = useState('');
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

  const fetchBrowsedMedia = useCallback(async () => {
    setLoading(true);
    try {
      const source = activeTab === 'images' ? 'images' : 'imported';
      const prefix = currentPath || '';
      const params = {
        source,
        prefix,
        limit: 1000,
        ...(search && { query: search })
      };
      const response = await mediaApi.browse(params);
      setBrowsedMedia(response.data.items || []);
      setBrowsedFolders(response.data.folders || []);
      setBrowsedTotal(response.data.total || 0);
      setParentPath(response.data.parent_path ?? null);
    } catch (err) {
      console.error('Ошибка загрузки файлов:', err);
      setBrowsedMedia([]);
      setBrowsedFolders([]);
      setBrowsedTotal(0);
    } finally {
      setLoading(false);
    }
  }, [activeTab, currentPath, search]);

  useEffect(() => {
    // Сбрасываем путь при переключении вкладок
    if (activeTab !== 'uploaded') {
      setCurrentPath('');
      setParentPath(null);
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === 'uploaded') {
      fetchMedia();
    } else {
      fetchBrowsedMedia();
    }
  }, [activeTab, fetchMedia, fetchBrowsedMedia]);

  // Навигация по папкам для browsed media
  const handleFolderClick = (folderPath) => {
    setCurrentPath(folderPath);
    setPage(1);
  };

  const handleHomeClick = () => {
    setCurrentPath('');
    setPage(1);
  };

  const handleParentClick = () => {
    if (parentPath !== null) {
      setCurrentPath(parentPath);
      setPage(1);
    }
  };

  const handleUpload = async (e) => {
    const files = e.target.files;
    if (!files?.length) return;
    setUploading(true); setError('');
    try {
      if (activeTab === 'uploaded') {
        // Загрузка в стандартную директорию uploads
        for (const file of files) {
          await mediaApi.upload(file);
        }
        fetchMedia();
      } else {
        // Загрузка в source (imported или images)
        const source = activeTab === 'images' ? 'images' : 'imported';
        for (const file of files) {
          await mediaApi.uploadToSource(file, source, currentPath);
        }
        fetchBrowsedMedia();
      }
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

  const handleDeleteBrowsed = async (item, e) => {
    if (e) e.stopPropagation();
    if (!confirm(`Удалить файл "${item.name}"?`)) return;
    try {
      const source = activeTab === 'images' ? 'images' : 'imported';
      await mediaApi.deleteFromSource(source, item.path);
      setSelectedMedia(null);
      fetchBrowsedMedia();
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка удаления');
      console.error(err);
    }
  };

  const handleRenameClick = (item, e) => {
    if (e) e.stopPropagation();
    setRenamingItem(item);
    setNewFileName(item.name);
  };

  const handleRenameCancel = () => {
    setRenamingItem(null);
    setNewFileName('');
  };

  const handleRenameSave = async () => {
    if (!renamingItem || !newFileName.trim()) return;
    if (newFileName === renamingItem.name) {
      handleRenameCancel();
      return;
    }
    try {
      const source = activeTab === 'images' ? 'images' : 'imported';
      await mediaApi.renameInSource(source, renamingItem.path, newFileName.trim());
      setRenamingItem(null);
      setNewFileName('');
      fetchBrowsedMedia();
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка переименования');
      console.error(err);
    }
  };

  const copyUrl = (url) => {
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isImage = (mime) => mime?.startsWith('image/');

  const displayMedia = activeTab === 'uploaded' ? media : browsedMedia;
  const displayTotal = activeTab === 'uploaded' ? total : browsedTotal;
  const totalPages = Math.ceil(displayTotal / limit);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Медиабиблиотека</h1>
          <p className="text-sm text-muted-foreground">Управление изображениями и файлами</p>
        </div>
        <div>
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleUpload} 
            className="hidden" 
            multiple 
            accept={activeTab === 'uploaded' ? "image/*,.pdf,.doc,.docx" : "image/*"} 
          />
          <Button size="sm" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
            {uploading ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Upload className="mr-2 h-3.5 w-3.5" />} Загрузить
          </Button>
        </div>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="uploaded">Загруженные</TabsTrigger>
          <TabsTrigger value="imported">Импортированные</TabsTrigger>
          <TabsTrigger value="images">Изображения сайта</TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="space-y-2">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input 
                placeholder="Поиск..." 
                className="pl-8 h-8 text-sm" 
                value={search} 
                onChange={(e) => { setSearch(e.target.value); setPage(1); }} 
              />
            </div>
            {activeTab !== 'uploaded' && (
              <>
                {parentPath !== null && (
                  <Button variant="outline" size="sm" onClick={handleParentClick} className="h-8">
                    <ArrowUp className="h-3.5 w-3.5 mr-1" /> Вверх
                  </Button>
                )}
                {currentPath && (
                  <Button variant="outline" size="sm" onClick={handleHomeClick} className="h-8">
                    <Folder className="h-3.5 w-3.5 mr-1" /> Корень
                  </Button>
                )}
                <div className="flex border rounded-md">
                  <Button
                    variant={viewMode === 'grid' ? 'default' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode('grid')}
                    className="h-8 rounded-r-none"
                  >
                    <Grid3x3 className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant={viewMode === 'list' ? 'default' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode('list')}
                    className="h-8 rounded-l-none"
                  >
                    <List className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </>
            )}
          </div>

          {activeTab === 'uploaded' ? (
            // Загруженные файлы - обычный вид
            <>
              {loading ? (
                <div className="flex items-center justify-center h-64">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
              ) : displayMedia.length === 0 ? (
                <Card><CardContent className="py-12 text-center text-muted-foreground"><ImageIcon className="h-12 w-12 mx-auto mb-4 opacity-50" /><p>Нет файлов</p></CardContent></Card>
              ) : (
                <div className="grid grid-cols-3 md:grid-cols-5 lg:grid-cols-8 gap-2">
                  {displayMedia.map((item) => {
                    const itemKey = item._id;
                    const itemUrl = item.url;
                    const itemName = item.alt || item.filename;
                    const isImg = isImage(item.mime_type);
                    
                    return (
                      <div
                        key={itemKey}
                        onClick={() => setSelectedMedia(item)}
                        className={cn(
                          "relative aspect-square rounded border overflow-hidden cursor-pointer transition-all hover:shadow-md",
                          selectedMedia?._id === item._id ? "border-primary ring-1 ring-primary" : "border-border"
                        )}
                      >
                        {isImg ? (
                          <img src={itemUrl} alt={itemName} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex flex-col items-center justify-center bg-muted">
                            <FileText className="h-6 w-6 text-muted-foreground" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          ) : (
            // Импортированные/Изображения - с деревом папок
            <div className="flex gap-2 h-[calc(100vh-280px)]">
              {/* Дерево папок слева */}
              <Card className="w-64 flex-shrink-0">
                <CardContent className="p-2 h-full overflow-y-auto">
                  <div className="space-y-1">
                    <button
                      onClick={handleHomeClick}
                      className={cn(
                        "w-full text-left px-2 py-1.5 text-sm rounded flex items-center gap-1.5 hover:bg-accent",
                        currentPath === '' && "bg-accent font-medium"
                      )}
                    >
                      <Folder className="h-3.5 w-3.5" />
                      <span className="truncate">Корень</span>
                    </button>
                    {browsedFolders.map((folder) => {
                      const isSelected = currentPath === folder.path;
                      return (
                        <button
                          key={folder.path}
                          onClick={() => handleFolderClick(folder.path)}
                          className={cn(
                            "w-full text-left px-2 py-1.5 text-sm rounded flex items-center gap-1.5 hover:bg-accent",
                            isSelected && "bg-accent font-medium"
                          )}
                        >
                          <Folder className="h-3.5 w-3.5 flex-shrink-0" />
                          <span className="truncate">{folder.name}</span>
                        </button>
                      );
                    })}
                    {browsedFolders.length === 0 && !loading && currentPath === '' && (
                      <div className="text-xs text-muted-foreground px-2 py-1.5">Нет папок</div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Файлы справа */}
              <Card className="flex-1">
                <CardContent className="p-2 h-full overflow-y-auto">
                  {loading ? (
                    <div className="flex items-center justify-center h-full">
                      <Loader2 className="h-6 w-6 animate-spin text-primary" />
                    </div>
                  ) : currentPath === '' ? (
                    // В корне показываем сообщение, что нужно выбрать папку
                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                      <Folder className="h-12 w-12 mb-4 opacity-50" />
                      <p className="text-sm">Выберите папку для просмотра файлов</p>
                    </div>
                  ) : displayMedia.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                      <ImageIcon className="h-8 w-8 mb-2 opacity-50" />
                      <p className="text-sm">Нет файлов в этой папке</p>
                    </div>
                  ) : viewMode === 'grid' ? (
                    <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-2">
                      {displayMedia.map((item, idx) => {
                        const itemKey = `${item.path}-${idx}`;
                        return (
                          <div
                            key={itemKey}
                            onClick={() => setSelectedMedia(item)}
                            className={cn(
                              "relative aspect-square rounded border overflow-hidden cursor-pointer transition-all hover:shadow-md group",
                              selectedMedia?.path === item.path ? "border-primary ring-1 ring-primary" : "border-border"
                            )}
                          >
                            <img src={item.url} alt={item.name} className="w-full h-full object-cover" />
                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 bg-background/90 hover:bg-background"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleRenameClick(item, e);
                                }}
                              >
                                <Edit2 className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 bg-background/90 hover:bg-background"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  copyUrl(item.url);
                                }}
                              >
                                <Copy className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 bg-background/90 hover:bg-destructive hover:text-destructive-foreground"
                                onClick={(e) => handleDeleteBrowsed(item, e)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="space-y-1">
                      {displayMedia.map((item, idx) => {
                        const itemKey = `${item.path}-${idx}`;
                        const isSelected = selectedMedia?.path === item.path;
                        const isRenaming = renamingItem?.path === item.path;
                        return (
                          <div
                            key={itemKey}
                            onClick={() => !isRenaming && setSelectedMedia(item)}
                            className={cn(
                              "flex items-center gap-3 p-2 rounded border cursor-pointer transition-all hover:bg-accent",
                              isSelected ? "border-primary bg-accent" : "border-border"
                            )}
                          >
                            <div className="w-12 h-12 flex-shrink-0 rounded overflow-hidden border">
                              <img src={item.url} alt={item.name} className="w-full h-full object-cover" />
                            </div>
                            <div className="flex-1 min-w-0">
                              {isRenaming ? (
                                <div className="flex items-center gap-2">
                                  <Input
                                    value={newFileName}
                                    onChange={(e) => setNewFileName(e.target.value)}
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter') {
                                        handleRenameSave();
                                      } else if (e.key === 'Escape') {
                                        handleRenameCancel();
                                      }
                                    }}
                                    className="h-7 text-sm"
                                    autoFocus
                                    onClick={(e) => e.stopPropagation()}
                                  />
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleRenameSave();
                                    }}
                                    className="h-7"
                                  >
                                    <Check className="h-3.5 w-3.5" />
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleRenameCancel();
                                    }}
                                    className="h-7"
                                  >
                                    ×
                                  </Button>
                                </div>
                              ) : (
                                <>
                                  <p className="text-sm font-medium truncate">{item.name}</p>
                                  <p className="text-xs text-muted-foreground truncate font-mono">{item.path}</p>
                                </>
                              )}
                            </div>
                            {!isRenaming && (
                              <div className="flex-shrink-0 flex items-center gap-1">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleRenameClick(item, e);
                                  }}
                                  className="h-7 w-7"
                                >
                                  <Edit2 className="h-3.5 w-3.5" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    copyUrl(item.url);
                                  }}
                                  className="h-7 w-7"
                                >
                                  {copied && selectedMedia?.path === item.path ? (
                                    <Check className="h-3.5 w-3.5" />
                                  ) : (
                                    <Copy className="h-3.5 w-3.5" />
                                  )}
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => handleDeleteBrowsed(item, e)}
                                  className="h-7 w-7 text-destructive hover:text-destructive hover:bg-destructive/10"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}

          {activeTab === 'uploaded' && totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button variant="outline" size="icon" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm">{page} / {totalPages}</span>
              <Button variant="outline" size="icon" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={!!selectedMedia} onOpenChange={() => setSelectedMedia(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Информация о файле</DialogTitle></DialogHeader>
          {selectedMedia && (
            <div className="grid md:grid-cols-2 gap-4">
              <div className="aspect-square rounded-lg overflow-hidden bg-muted">
                {activeTab === 'uploaded' ? (
                  isImage(selectedMedia.mime_type) ? (
                    <img src={selectedMedia.url} alt="" className="w-full h-full object-contain" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center"><FileText className="h-16 w-16 text-muted-foreground" /></div>
                  )
                ) : (
                  <img src={selectedMedia.url} alt="" className="w-full h-full object-contain" />
                )}
              </div>
              <div className="space-y-4">
                <div>
                  <Label className="text-muted-foreground">Имя файла</Label>
                  <p className="font-medium">{activeTab === 'uploaded' ? selectedMedia.original_name : selectedMedia.name}</p>
                </div>
                {activeTab === 'uploaded' && (
                  <>
                    <div>
                      <Label className="text-muted-foreground">Размер</Label>
                      <p className="font-medium">{(selectedMedia.file_size / 1024).toFixed(1)} KB</p>
                    </div>
                    {selectedMedia.width && (
                      <div>
                        <Label className="text-muted-foreground">Размеры</Label>
                        <p className="font-medium">{selectedMedia.width} x {selectedMedia.height}</p>
                      </div>
                    )}
                  </>
                )}
                {activeTab !== 'uploaded' && (
                  <div>
                    <Label className="text-muted-foreground">Путь</Label>
                    <p className="font-medium font-mono text-xs">{selectedMedia.path}</p>
                  </div>
                )}
                <div>
                  <Label className="text-muted-foreground">URL</Label>
                  <div className="flex gap-2">
                    <Input value={selectedMedia.url} readOnly className="font-mono text-xs" />
                    <Button variant="outline" size="icon" onClick={() => copyUrl(selectedMedia.url)}>
                      {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            {activeTab === 'uploaded' ? (
              <Button variant="destructive" onClick={() => handleDelete(selectedMedia?._id)}>
                <Trash2 className="mr-2 h-4 w-4" /> Удалить
              </Button>
            ) : (
              <Button variant="destructive" onClick={() => handleDeleteBrowsed(selectedMedia)}>
                <Trash2 className="mr-2 h-4 w-4" /> Удалить
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
