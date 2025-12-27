import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Database, Download, Upload, Trash2, Play, Loader2, Copy, Check, AlertTriangle } from 'lucide-react';
import api from '../utils/api';

export default function MongoAdminPage() {
  const [collections, setCollections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Export state
  const [exportCollection, setExportCollection] = useState('');
  const [exportQuery, setExportQuery] = useState('{}');
  const [exportProjection, setExportProjection] = useState('');
  const [exportSort, setExportSort] = useState('');
  const [exportLimit, setExportLimit] = useState('100');
  const [exportResult, setExportResult] = useState('');
  const [exporting, setExporting] = useState(false);
  
  // Import state
  const [importCollection, setImportCollection] = useState('');
  const [importData, setImportData] = useState('');
  const [importMode, setImportMode] = useState('insert');
  const [importUpsertField, setImportUpsertField] = useState('_id');
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  
  // Delete state
  const [deleteCollection, setDeleteCollection] = useState('');
  const [deleteQuery, setDeleteQuery] = useState('');
  const [deleting, setDeleting] = useState(false);
  
  // Aggregate state
  const [aggCollection, setAggCollection] = useState('');
  const [aggPipeline, setAggPipeline] = useState('[\n  { "$match": {} },\n  { "$limit": 10 }\n]');
  const [aggResult, setAggResult] = useState('');
  const [aggregating, setAggregating] = useState(false);
  
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    loadCollections();
  }, []);

  const loadCollections = async () => {
    try {
      const response = await api.get('/mongo/collections');
      setCollections(response.data.collections);
      if (response.data.collections.length > 0) {
        setExportCollection(response.data.collections[0].name);
        setImportCollection(response.data.collections[0].name);
        setDeleteCollection(response.data.collections[0].name);
        setAggCollection(response.data.collections[0].name);
      }
    } catch (err) {
      setError('Ошибка загрузки коллекций');
    } finally {
      setLoading(false);
    }
  };

  const clearMessages = () => {
    setError('');
    setSuccess('');
  };

  const handleExport = async () => {
    clearMessages();
    setExporting(true);
    setExportResult('');
    
    try {
      const response = await api.post('/mongo/export', {
        collection: exportCollection,
        query: exportQuery || '{}',
        projection: exportProjection || null,
        sort: exportSort || null,
        limit: parseInt(exportLimit) || 100
      });
      
      setExportResult(response.data.data);
      setSuccess(`Экспортировано ${response.data.count} документов`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка экспорта');
    } finally {
      setExporting(false);
    }
  };

  const handleImport = async () => {
    clearMessages();
    setImporting(true);
    setImportResult(null);
    
    try {
      const response = await api.post('/mongo/import', {
        collection: importCollection,
        documents: importData,
        mode: importMode,
        upsert_field: importUpsertField
      });
      
      setImportResult(response.data);
      setSuccess(`Импорт завершён: добавлено ${response.data.inserted}, обновлено ${response.data.updated}`);
      loadCollections(); // Refresh counts
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка импорта');
    } finally {
      setImporting(false);
    }
  };

  const handleDelete = async () => {
    clearMessages();
    
    if (!deleteQuery.trim()) {
      setError('Введите запрос для удаления');
      return;
    }
    
    if (!window.confirm('Вы уверены? Это действие нельзя отменить!')) {
      return;
    }
    
    setDeleting(true);
    
    try {
      const response = await api.post('/mongo/delete', {
        collection: deleteCollection,
        query: deleteQuery
      });
      
      setSuccess(`Удалено ${response.data.deleted} документов`);
      loadCollections(); // Refresh counts
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка удаления');
    } finally {
      setDeleting(false);
    }
  };

  const handleAggregate = async () => {
    clearMessages();
    setAggregating(true);
    setAggResult('');
    
    try {
      const response = await api.post('/mongo/aggregate', {
        collection: aggCollection,
        pipeline: aggPipeline
      });
      
      setAggResult(response.data.data);
      setSuccess(`Получено ${response.data.count} результатов`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка агрегации');
    } finally {
      setAggregating(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadJson = (data, filename) => {
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Database className="h-8 w-8" />
          MongoDB Admin
        </h1>
        <p className="text-muted-foreground">Импорт и экспорт данных базы</p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      
      {success && (
        <Alert>
          <Check className="h-4 w-4" />
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      {/* Collections Overview */}
      <Card>
        <CardHeader>
          <CardTitle>Коллекции</CardTitle>
          <CardDescription>Всего документов в базе данных</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {collections.map(col => (
              <Badge key={col.name} variant="secondary" className="text-sm py-1 px-3">
                {col.name}: {col.count.toLocaleString()}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="export" className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="export" className="flex items-center gap-2">
            <Download className="h-4 w-4" /> Экспорт
          </TabsTrigger>
          <TabsTrigger value="import" className="flex items-center gap-2">
            <Upload className="h-4 w-4" /> Импорт
          </TabsTrigger>
          <TabsTrigger value="aggregate" className="flex items-center gap-2">
            <Play className="h-4 w-4" /> Агрегация
          </TabsTrigger>
          <TabsTrigger value="delete" className="flex items-center gap-2">
            <Trash2 className="h-4 w-4" /> Удаление
          </TabsTrigger>
        </TabsList>

        {/* EXPORT TAB */}
        <TabsContent value="export">
          <Card>
            <CardHeader>
              <CardTitle>Экспорт данных</CardTitle>
              <CardDescription>Выгрузка документов из коллекции в JSON</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Коллекция</Label>
                  <Select value={exportCollection} onValueChange={setExportCollection}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {collections.map(col => (
                        <SelectItem key={col.name} value={col.name}>
                          {col.name} ({col.count})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Лимит</Label>
                  <Input 
                    type="number" 
                    value={exportLimit} 
                    onChange={(e) => setExportLimit(e.target.value)}
                    placeholder="100"
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label>Query (JSON)</Label>
                <Textarea
                  value={exportQuery}
                  onChange={(e) => setExportQuery(e.target.value)}
                  placeholder='{"status": "published"}'
                  className="font-mono text-sm"
                  rows={3}
                />
                <p className="text-xs text-muted-foreground">
                  Примеры: {`{}`} — все, {`{"slug": "comedy-club"}`}, {`{"level": 0}`}
                </p>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Projection (опционально)</Label>
                  <Input
                    value={exportProjection}
                    onChange={(e) => setExportProjection(e.target.value)}
                    placeholder='{"title": 1, "slug": 1}'
                    className="font-mono text-sm"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Sort (опционально)</Label>
                  <Input
                    value={exportSort}
                    onChange={(e) => setExportSort(e.target.value)}
                    placeholder='{"created_at": -1}'
                    className="font-mono text-sm"
                  />
                </div>
              </div>

              <Button onClick={handleExport} disabled={exporting}>
                {exporting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                Экспортировать
              </Button>

              {exportResult && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Результат</Label>
                    <div className="flex gap-2">
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => copyToClipboard(exportResult)}
                      >
                        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => downloadJson(exportResult, `${exportCollection}_export.json`)}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <Textarea
                    value={exportResult}
                    readOnly
                    className="font-mono text-sm h-[400px]"
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* IMPORT TAB */}
        <TabsContent value="import">
          <Card>
            <CardHeader>
              <CardTitle>Импорт данных</CardTitle>
              <CardDescription>Загрузка документов в коллекцию из JSON</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Коллекция</Label>
                  <Select value={importCollection} onValueChange={setImportCollection}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {collections.map(col => (
                        <SelectItem key={col.name} value={col.name}>
                          {col.name} ({col.count})
                        </SelectItem>
                      ))}
                      <SelectItem value="__new__">+ Новая коллекция</SelectItem>
                    </SelectContent>
                  </Select>
                  {importCollection === '__new__' && (
                    <Input
                      placeholder="Имя новой коллекции"
                      onChange={(e) => setImportCollection(e.target.value)}
                    />
                  )}
                </div>
                <div className="space-y-2">
                  <Label>Режим</Label>
                  <Select value={importMode} onValueChange={setImportMode}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="insert">Insert (добавить новые)</SelectItem>
                      <SelectItem value="upsert">Upsert (добавить/обновить)</SelectItem>
                      <SelectItem value="replace">Replace (заменить по _id)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {importMode === 'upsert' && (
                  <div className="space-y-2">
                    <Label>Поле для upsert</Label>
                    <Input
                      value={importUpsertField}
                      onChange={(e) => setImportUpsertField(e.target.value)}
                      placeholder="_id"
                    />
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label>Данные (JSON)</Label>
                <Textarea
                  value={importData}
                  onChange={(e) => setImportData(e.target.value)}
                  placeholder='[{"title": "Test", "slug": "test"}]'
                  className="font-mono text-sm h-[300px]"
                />
                <p className="text-xs text-muted-foreground">
                  Массив документов [{`{...}, {...}`}] или один документ {`{...}`}
                </p>
              </div>

              <Button onClick={handleImport} disabled={importing || !importData.trim()}>
                {importing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
                Импортировать
              </Button>

              {importResult && (
                <Alert>
                  <AlertDescription>
                    Добавлено: {importResult.inserted}, Обновлено: {importResult.updated}
                    {importResult.errors?.length > 0 && (
                      <div className="mt-2 text-destructive">
                        Ошибки: {importResult.errors.join(', ')}
                      </div>
                    )}
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* AGGREGATE TAB */}
        <TabsContent value="aggregate">
          <Card>
            <CardHeader>
              <CardTitle>Агрегация</CardTitle>
              <CardDescription>Выполнение aggregation pipeline запросов</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Коллекция</Label>
                <Select value={aggCollection} onValueChange={setAggCollection}>
                  <SelectTrigger className="w-[300px]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {collections.map(col => (
                      <SelectItem key={col.name} value={col.name}>
                        {col.name} ({col.count})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Pipeline (JSON Array)</Label>
                <Textarea
                  value={aggPipeline}
                  onChange={(e) => setAggPipeline(e.target.value)}
                  className="font-mono text-sm h-[200px]"
                />
                <p className="text-xs text-muted-foreground">
                  Пример: {`[{"$match": {"status": "published"}}, {"$group": {"_id": "$level", "count": {"$sum": 1}}}]`}
                </p>
              </div>

              <Button onClick={handleAggregate} disabled={aggregating}>
                {aggregating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                Выполнить
              </Button>

              {aggResult && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Результат</Label>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => copyToClipboard(aggResult)}
                    >
                      {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    </Button>
                  </div>
                  <Textarea
                    value={aggResult}
                    readOnly
                    className="font-mono text-sm h-[300px]"
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* DELETE TAB */}
        <TabsContent value="delete">
          <Card>
            <CardHeader>
              <CardTitle className="text-destructive">Удаление данных</CardTitle>
              <CardDescription>Удаление документов из коллекции (необратимо!)</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  Внимание! Удаление данных необратимо. Убедитесь, что вы экспортировали данные перед удалением.
                </AlertDescription>
              </Alert>

              <div className="space-y-2">
                <Label>Коллекция</Label>
                <Select value={deleteCollection} onValueChange={setDeleteCollection}>
                  <SelectTrigger className="w-[300px]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {collections.map(col => (
                      <SelectItem key={col.name} value={col.name}>
                        {col.name} ({col.count})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Query (JSON)</Label>
                <Textarea
                  value={deleteQuery}
                  onChange={(e) => setDeleteQuery(e.target.value)}
                  placeholder='{"_id": "..."}'
                  className="font-mono text-sm"
                  rows={3}
                />
                <p className="text-xs text-muted-foreground">
                  Пустой запрос запрещён. Примеры: {`{"_id": "abc123"}`}, {`{"status": "draft"}`}
                </p>
              </div>

              <Button 
                variant="destructive" 
                onClick={handleDelete} 
                disabled={deleting || !deleteQuery.trim()}
              >
                {deleting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
                Удалить
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
