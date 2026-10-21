import { useState, useMemo, useCallback } from 'react';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Plus, GripVertical, Trash2, Edit, FileText, Clock, Users, Tv, Table, Image, Play, Quote,
  HelpCircle, Award, Star, Zap, Shuffle, List, Film, Tag, Trophy, Vote } from 'lucide-react';
import { cn } from '@/lib/utils';
import { moduleNames, getAvailableModuleTypes } from '@/moduleContract';
import ModuleEditDialog from './module-editor/ModuleEditDialog';
import { createModule, replaceModule, reorderModules } from './module-editor/operations';

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
  table_of_contents: List,
  // Новые системные модули
  poster_photo: Image,
  facts_table: Table,
  rating_widget: Star,
  tags_cloud: Tag,
  social_links: Users,
  first_league_champions: Trophy,
  vl_league_champions: Trophy,
  poll: Vote
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
        aria-label={'Переместить блок ' + (module.title || moduleNames[module.type] || module.type)}
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
        <Button variant="ghost" size="icon" aria-label={'Редактировать блок ' + (module.title || moduleNames[module.type] || module.type)} onClick={() => onEdit(module)}>
          <Edit className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" aria-label={'Удалить блок ' + (module.title || moduleNames[module.type] || module.type)} onClick={() => onDelete(module.id)} className="text-destructive">
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

export default function ModuleEditor({ modules = [], onChange, contentType = 'page', excludedTypes = [] }) {
  const [editingModuleId, setEditingModuleId] = useState(null);
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  );

  const availableModules = getAvailableModuleTypes(contentType).filter(type => !excludedTypes.includes(type));
  
  const editingModule = useMemo(() => {
    return modules.find(m => m.id === editingModuleId) || null;
  }, [modules, editingModuleId]);

  const handleDragEnd = useCallback((event) => {
    const { active, over } = event;
    const next = reorderModules(modules, active?.id, over?.id);
    if (next !== modules) onChange(next);
  }, [modules, onChange]);

  const addModule = useCallback((type) => {
    const newModule = createModule(type, modules.length);
    onChange([...modules, newModule]);
    setAddDialogOpen(false);
    // Open edit dialog for the new module
    setEditingModuleId(newModule.id);
  }, [modules, onChange]);

  const saveModule = useCallback((updatedModule) => {
    onChange(replaceModule(modules, updatedModule));
  }, [modules, onChange]);

  const deleteModule = useCallback((id) => {
    onChange(modules.filter((m) => m.id !== id));
  }, [modules, onChange]);

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
        key={editingModuleId || 'no-module'}
        module={editingModule}
        open={!!editingModuleId}
        onClose={closeEditDialog}
        onSave={saveModule}
      />
    </div>
  );
}
