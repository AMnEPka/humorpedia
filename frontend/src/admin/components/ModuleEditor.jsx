import { useState, useMemo } from 'react';
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
  random_page: Shuffle
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
  random_page: 'Случайная страница'
};

const modulesByType = {
  person: ['hero_card', 'text_block', 'timeline', 'tags', 'table', 'gallery', 'video', 'quote'],
  team: ['hero_card', 'text_block', 'timeline', 'team_members', 'tv_appearances', 'games_list', 'tags', 'table', 'gallery', 'video'],
  show: ['hero_card', 'text_block', 'timeline', 'episodes_list', 'participants', 'tags', 'table', 'gallery', 'video'],
  article: ['text_block', 'table', 'gallery', 'video', 'quote', 'tags'],
  news: ['text_block', 'gallery', 'video', 'tags'],
  quiz: ['quiz_questions', 'quiz_results', 'text_block'],
  wiki: ['text_block', 'table', 'gallery', 'video', 'tags'],
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

function TextBlockEditor({ data, onChange }) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Заголовок</Label>
        <Input
          value={data.title || ''}
          onChange={(e) => onChange({ ...data, title: e.target.value })}
          placeholder="Биография"
        />
      </div>
      <div className="space-y-2">
        <Label>Содержимое (HTML)</Label>
        <Textarea
          value={data.content || ''}
          onChange={(e) => onChange({ ...data, content: e.target.value })}
          placeholder="<p>Текст...</p>"
          rows={10}
          className="font-mono text-sm"
        />
      </div>
    </div>
  );
}

function TimelineEditor({ data, onChange }) {
  const items = data.items || [];

  const addItem = () => {
    onChange({
      ...data,
      items: [...items, { year: new Date().getFullYear(), title: '', description: '' }]
    });
  };

  const updateItem = (index, field, value) => {
    const newItems = [...items];
    newItems[index] = { ...newItems[index], [field]: value };
    onChange({ ...data, items: newItems });
  };

  const removeItem = (index) => {
    onChange({ ...data, items: items.filter((_, i) => i !== index) });
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Заголовок блока</Label>
        <Input
          value={data.title || ''}
          onChange={(e) => onChange({ ...data, title: e.target.value })}
          placeholder="Хронология"
        />
      </div>
      
      <div className="space-y-3">
        {items.map((item, index) => (
          <div key={index} className="border rounded-lg p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Событие {index + 1}</span>
              <Button variant="ghost" size="icon" onClick={() => removeItem(index)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Input
                type="number"
                value={item.year || ''}
                onChange={(e) => updateItem(index, 'year', parseInt(e.target.value))}
                placeholder="Год"
              />
              <Input
                value={item.title || ''}
                onChange={(e) => updateItem(index, 'title', e.target.value)}
                placeholder="Заголовок"
              />
            </div>
            <Textarea
              value={item.description || ''}
              onChange={(e) => updateItem(index, 'description', e.target.value)}
              placeholder="Описание"
              rows={2}
            />
          </div>
        ))}
      </div>
      
      <Button type="button" variant="outline" onClick={addItem} className="w-full">
        <Plus className="mr-2 h-4 w-4" /> Добавить событие
      </Button>
    </div>
  );
}

function GenericEditor({ data, onChange }) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Данные модуля (JSON)</Label>
        <Textarea
          value={JSON.stringify(data, null, 2)}
          onChange={(e) => {
            try {
              onChange(JSON.parse(e.target.value));
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

export default function ModuleEditor({ modules = [], onChange, contentType = 'page' }) {
  const [editingModule, setEditingModule] = useState(null);
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  );

  const availableModules = modulesByType[contentType] || modulesByType.page;

  const handleDragEnd = (event) => {
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
  };

  const addModule = (type) => {
    const newModule = {
      id: crypto.randomUUID(),
      type,
      order: modules.length,
      visible: true,
      data: {}
    };
    onChange([...modules, newModule]);
    setAddDialogOpen(false);
    setEditingModule(newModule);
  };

  const updateModule = (moduleData) => {
    onChange(modules.map((m) => 
      m.id === editingModule.id ? { ...m, ...moduleData } : m
    ));
  };

  const deleteModule = (id) => {
    onChange(modules.filter((m) => m.id !== id));
  };

  const renderEditor = () => {
    if (!editingModule) return null;

    const data = editingModule.data || {};
    const setData = (newData) => updateModule({ data: newData });

    switch (editingModule.type) {
      case 'text_block':
        return <TextBlockEditor data={data} onChange={setData} />;
      case 'timeline':
        return <TimelineEditor data={data} onChange={setData} />;
      default:
        return <GenericEditor data={data} onChange={setData} />;
    }
  };

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
                  onEdit={setEditingModule}
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
            })}          </div>
        </DialogContent>
      </Dialog>

      {/* Edit module dialog */}
      <Dialog open={!!editingModule} onOpenChange={() => setEditingModule(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Редактирование: {editingModule && moduleNames[editingModule.type]}
            </DialogTitle>
          </DialogHeader>
          <div className="py-4">
            {editingModule && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Название блока (опционально)</Label>
                  <Input
                    value={editingModule.title || ''}
                    onChange={(e) => updateModule({ title: e.target.value })}
                    placeholder={moduleNames[editingModule.type]}
                  />
                </div>
                {renderEditor()}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button onClick={() => setEditingModule(null)}>Готово</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
