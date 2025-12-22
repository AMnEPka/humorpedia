import { useState, useMemo, useCallback, useEffect } from 'react';
import { 
  DndContext, closestCenter, KeyboardSensor, 
  PointerSensor, useSensor, useSensors, DragOverlay
} from '@dnd-kit/core';
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates,
  verticalListSortingStrategy, useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select, SelectContent, SelectItem, 
  SelectTrigger, SelectValue
} from '@/components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter
} from '@/components/ui/dialog';
import { 
  Plus, GripVertical, Trash2, Edit, ChevronDown, ChevronUp,
  FileText, Clock, Users, Tv, Table, Image, Play, Quote,
  HelpCircle, Award, Star, Zap, Shuffle, List, Film, Tag
} from 'lucide-react';
import { cn } from '@/lib/utils';

const moduleIcons = {
  hero_card: Users,
  text_block: FileText,
  timeline: Clock,
  tags: Tag,
  table: Table,
  gallery: Image,
  video: Play,
  quote: Quote,
  team_members: Users,
  tv_appearances: Tv,
  games_list: List,
  episodes_list: Film,
  participants: Users,
  quiz_questions: HelpCircle,
  quiz_results: Award,
  best_articles: Star,
  interesting: Zap,
  random_page: Shuffle,
  table_of_contents: List
};

const moduleNames = {
  hero_card: 'Карточка с фото',
  text_block: 'Текстовый блок',
  timeline: 'Хронология',
  tags: 'Теги',
  table: 'Таблица',
  gallery: 'Галерея',
  video: 'Видео',
  quote: 'Цитата',
  team_members: 'Состав команды',
  tv_appearances: 'ТВ эфиры',
  games_list: 'Список игр',
  episodes_list: 'Список выпусков',
  participants: 'Участники',
  quiz_questions: 'Вопросы квиза',
  quiz_results: 'Результаты квиза',
  best_articles: 'Лучшие статьи',
  interesting: 'Интересное',
  random_page: 'Случайная страница',
  table_of_contents: 'Оглавление'
};

const modulesByType = {
  person: ['table_of_contents', 'hero_card', 'text_block', 'timeline', 'tags', 'table', 'gallery', 'video', 'quote'],
  team: ['table_of_contents', 'hero_card', 'text_block', 'timeline', 'team_members', 'tv_appearances', 'games_list', 'tags', 'table', 'gallery', 'video'],
  show: ['hero_card', 'text_block', 'timeline', 'episodes_list', 'participants', 'tags', 'table', 'gallery', 'video'],
  article: ['table_of_contents', 'text_block', 'table', 'gallery', 'video', 'quote', 'tags'],
  news: ['text_block', 'gallery', 'video', 'tags'],
  quiz: ['quiz_questions', 'quiz_results', 'text_block'],
  wiki: ['table_of_contents', 'text_block', 'table', 'gallery', 'video', 'tags'],
  page: ['text_block', 'best_articles', 'interesting', 'random_page', 'table', 'gallery']
};

function SortableModule({ module, onEdit, onDelete }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: module.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1
  };

  const Icon = moduleIcons[module.type] || FileText;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "bg-white border rounded-lg p-4 flex items-center gap-3",
        isDragging && "shadow-lg"
      )}
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab text-muted-foreground hover:text-foreground"
      >
        <GripVertical className="h-5 w-5" />
      </button>
      
      <div className="p-2 bg-muted rounded">
        <Icon className="h-5 w-5" />
      </div>
      
      <div className="flex-1 min-w-0">
        <div className="font-medium">
          {module.title || moduleNames[module.type] || module.type}
        </div>
        <div className="text-sm text-muted-foreground truncate">
          {moduleNames[module.type]}
        </div>
      </div>
      
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon" onClick={() => onEdit(module)}>
          <Edit className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={() => onDelete(module.id)} className="text-destructive">
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// Separate component for editing module to manage its own state
function ModuleEditDialog({ module, open, onClose, onSave }) {
  const [localModule, setLocalModule] = useState(null);

  // Initialize local state when module changes
  useEffect(() => {
    if (module) {
      setLocalModule({ ...module, data: { ...module.data } });
    } else {
      setLocalModule(null);
    }
  }, [module]);

  const handleSave = useCallback(() => {
    if (localModule) {
      onSave(localModule);
    }
    onClose();
  }, [localModule, onSave, onClose]);

  const updateLocalModule = useCallback((updates) => {
    setLocalModule(prev => prev ? { ...prev, ...updates } : null);
  }, []);

  const updateData = useCallback((newData) => {
    setLocalModule(prev => prev ? { ...prev, data: newData } : null);
  }, []);

  if (!localModule) return null;

  const data = localModule.data || {};

  const renderEditor = () => {
    switch (localModule.type) {
      case 'text_block':
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
            <div className="space-y-2">
              <Label>Содержимое (HTML)</Label>
              <Textarea
                value={data.content || ''}
                onChange={(e) => updateData({ ...data, content: e.target.value })}
                placeholder="<p>Текст...</p>"
                rows={10}
                className="font-mono text-sm"
              />
            </div>
          </div>
        );
      
      case 'timeline':
        const items = data.items || [];
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Заголовок блока</Label>
              <Input
                value={data.title || ''}
                onChange={(e) => updateData({ ...data, title: e.target.value })}
                placeholder="Хронология"
              />
            </div>
            
            <div className="space-y-3">
              {items.map((item, index) => (
                <div key={index} className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Событие {index + 1}</span>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={() => updateData({ ...data, items: items.filter((_, i) => i !== index) })}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Input
                      type="number"
                      value={item.year || ''}
                      onChange={(e) => {
                        const newItems = [...items];
                        newItems[index] = { ...newItems[index], year: parseInt(e.target.value) || '' };
                        updateData({ ...data, items: newItems });
                      }}
                      placeholder="Год"
                    />
                    <Input
                      value={item.title || ''}
                      onChange={(e) => {
                        const newItems = [...items];
                        newItems[index] = { ...newItems[index], title: e.target.value };
                        updateData({ ...data, items: newItems });
                      }}
                      placeholder="Заголовок"
                    />
                  </div>
                  <Textarea
                    value={item.description || ''}
                    onChange={(e) => {
                      const newItems = [...items];
                      newItems[index] = { ...newItems[index], description: e.target.value };
                      updateData({ ...data, items: newItems });
                    }}
                    placeholder="Описание"
                    rows={2}
                  />
                </div>
              ))}
            </div>
            
            <Button 
              type="button" 
              variant="outline" 
              onClick={() => updateData({ 
                ...data, 
                items: [...items, { year: new Date().getFullYear(), title: '', description: '' }] 
              })} 
              className="w-full"
            >
              <Plus className="mr-2 h-4 w-4" /> Добавить событие
            </Button>
          </div>
        );
      
      case 'hero_card':
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

      case 'gallery':
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
                <div key={index} className="flex gap-2 items-center">
                  <Input
                    value={img.url || ''}
                    onChange={(e) => {
                      const newImages = [...galleryItems];
                      newImages[index] = { ...newImages[index], url: e.target.value };
                      updateData({ ...data, images: newImages });
                    }}
                    placeholder="URL изображения"
                    className="flex-1"
                  />
                  <Button 
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

      case 'video':
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

      case 'quote':
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

      case 'team_members':
        const members = data.members || [];
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Заголовок</Label>
              <Input
                value={data.title || ''}
                onChange={(e) => updateData({ ...data, title: e.target.value })}
                placeholder="Состав команды"
              />
            </div>
            <div className="space-y-3">
              {members.map((member, index) => (
                <div key={index} className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Участник {index + 1}</span>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={() => updateData({ ...data, members: members.filter((_, i) => i !== index) })}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <Input
                    value={member.name || ''}
                    onChange={(e) => {
                      const newMembers = [...members];
                      newMembers[index] = { ...newMembers[index], name: e.target.value };
                      updateData({ ...data, members: newMembers });
                    }}
                    placeholder="Имя"
                  />
                  <Input
                    value={member.role || ''}
                    onChange={(e) => {
                      const newMembers = [...members];
                      newMembers[index] = { ...newMembers[index], role: e.target.value };
                      updateData({ ...data, members: newMembers });
                    }}
                    placeholder="Роль в команде"
                  />
                </div>
              ))}
            </div>
            <Button 
              type="button" 
              variant="outline" 
              onClick={() => updateData({ 
                ...data, 
                members: [...members, { name: '', role: '' }] 
              })} 
              className="w-full"
            >
              <Plus className="mr-2 h-4 w-4" /> Добавить участника
            </Button>
          </div>
        );
      
      default:
        // Generic JSON editor for other types
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Данные модуля (JSON)</Label>
              <Textarea
                value={JSON.stringify(data, null, 2)}
                onChange={(e) => {
                  try {
                    updateData(JSON.parse(e.target.value));
                  } catch (err) {
                    // Invalid JSON, ignore
                  }
                }}
                rows={15}
                className="font-mono text-sm"
              />
            </div>
          </div>
        );
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleSave()}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            Редактирование: {moduleNames[localModule.type]}
          </DialogTitle>
        </DialogHeader>
        <div className="py-4">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Название блока (опционально)</Label>
              <Input
                value={localModule.title || ''}
                onChange={(e) => updateLocalModule({ title: e.target.value })}
                placeholder={moduleNames[localModule.type]}
              />
            </div>
            {renderEditor()}
          </div>
        </div>
        <DialogFooter>
          <Button onClick={handleSave}>Сохранить</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ModuleEditor({ modules = [], onChange, contentType = 'page' }) {
  const [editingModuleId, setEditingModuleId] = useState(null);
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  );

  const availableModules = modulesByType[contentType] || modulesByType.page;
  
  const editingModule = useMemo(() => {
    return modules.find(m => m.id === editingModuleId) || null;
  }, [modules, editingModuleId]);

  const handleDragEnd = useCallback((event) => {
    const { active, over } = event;
    if (active.id !== over?.id) {
      const oldIndex = modules.findIndex((m) => m.id === active.id);
      const newIndex = modules.findIndex((m) => m.id === over.id);
      const newModules = arrayMove(modules, oldIndex, newIndex).map((m, i) => ({
        ...m,
        order: i
      }));
      onChange(newModules);
    }
  }, [modules, onChange]);

  const addModule = useCallback((type) => {
    const newModule = {
      id: crypto.randomUUID(),
      type,
      order: modules.length,
      visible: true,
      data: {}
    };
    onChange([...modules, newModule]);
    setAddDialogOpen(false);
    // Open edit dialog for the new module
    setEditingModuleId(newModule.id);
  }, [modules, onChange]);

  const saveModule = useCallback((updatedModule) => {
    onChange(modules.map((m) => 
      m.id === updatedModule.id ? updatedModule : m
    ));
  }, [modules, onChange]);

  const deleteModule = useCallback((id) => {
    onChange(modules.filter((m) => m.id !== id));
  }, [onChange]);

  const openEditDialog = useCallback((module) => {
    setEditingModuleId(module.id);
  }, []);

  const closeEditDialog = useCallback(() => {
    setEditingModuleId(null);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Модули страницы</h3>
        <Button onClick={() => setAddDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" /> Добавить модуль
        </Button>
      </div>

      {modules.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Нет модулей</p>
            <p className="text-sm">Добавьте первый модуль для создания страницы</p>
          </CardContent>
        </Card>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={modules.map((m) => m.id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="space-y-2">
              {modules.map((module) => (
                <SortableModule
                  key={module.id}
                  module={module}
                  onEdit={openEditDialog}
                  onDelete={deleteModule}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      {/* Add module dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Добавить модуль</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 py-4">
            {availableModules.map((type) => {
              const Icon = moduleIcons[type] || FileText;
              return (
                <button
                  key={type}
                  onClick={() => addModule(type)}
                  className="flex items-center gap-3 p-3 border rounded-lg hover:bg-muted transition-colors text-left"
                >
                  <div className="p-2 bg-muted rounded">
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className="text-sm font-medium">{moduleNames[type]}</span>
                </button>
              );
            })}
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit module dialog - separate component with own state */}
      <ModuleEditDialog
        module={editingModule}
        open={!!editingModuleId}
        onClose={closeEditDialog}
        onSave={saveModule}
      />
    </div>
  );
}
