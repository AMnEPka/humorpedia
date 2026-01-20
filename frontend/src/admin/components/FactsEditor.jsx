import { useMemo, useCallback } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

function buildEffectiveOrder(facts = {}, factsOrder = []) {
  const keys = Object.keys(facts || {});
  const order = Array.isArray(factsOrder) ? factsOrder : [];
  const filtered = order.filter((k) => keys.includes(k));
  const rest = keys.filter((k) => !filtered.includes(k));
  return [...filtered, ...rest];
}

function SortableFactRow({ factKey, value, onRenameKey, onChangeValue, onDelete }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: factKey });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn("flex items-center gap-2 p-2 bg-muted rounded", isDragging && "shadow")}
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="cursor-grab text-muted-foreground hover:text-foreground px-1"
        aria-label="Переместить"
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <Input
        value={factKey}
        className="w-1/3 bg-background"
        onChange={(e) => onRenameKey(factKey, e.target.value)}
      />
      <Input
        value={value}
        className="flex-1 bg-background"
        onChange={(e) => onChangeValue(factKey, e.target.value)}
      />
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={() => onDelete(factKey)}
        aria-label="Удалить"
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  );
}

export default function FactsEditor({ facts, factsOrder, onChange }) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const effectiveOrder = useMemo(
    () => buildEffectiveOrder(facts, factsOrder),
    [facts, factsOrder]
  );

  const emit = useCallback(
    (nextFacts, nextOrder) => {
      const order = buildEffectiveOrder(nextFacts, nextOrder);
      onChange?.({ facts: nextFacts, facts_order: order });
    },
    [onChange]
  );

  const handleDragEnd = useCallback(
    (event) => {
      const { active, over } = event;
      if (!over || active.id === over.id) return;
      const oldIndex = effectiveOrder.findIndex((k) => k === active.id);
      const newIndex = effectiveOrder.findIndex((k) => k === over.id);
      if (oldIndex < 0 || newIndex < 0) return;
      emit({ ...(facts || {}) }, arrayMove(effectiveOrder, oldIndex, newIndex));
    },
    [effectiveOrder, facts, emit]
  );

  const renameKey = useCallback(
    (oldKey, newKeyRaw) => {
      const newKey = (newKeyRaw || '').trim();
      if (!newKey || newKey === oldKey) return;
      const currentFacts = facts || {};
      if (Object.prototype.hasOwnProperty.call(currentFacts, newKey)) return; // avoid collisions
      const nextFacts = { ...currentFacts };
      const value = nextFacts[oldKey];
      delete nextFacts[oldKey];
      nextFacts[newKey] = value;

      const nextOrder = effectiveOrder.map((k) => (k === oldKey ? newKey : k));
      emit(nextFacts, nextOrder);
    },
    [facts, effectiveOrder, emit]
  );

  const changeValue = useCallback(
    (key, newValue) => {
      emit({ ...(facts || {}), [key]: newValue }, effectiveOrder);
    },
    [facts, effectiveOrder, emit]
  );

  const deleteRow = useCallback(
    (key) => {
      const nextFacts = { ...(facts || {}) };
      delete nextFacts[key];
      const nextOrder = effectiveOrder.filter((k) => k !== key);
      emit(nextFacts, nextOrder);
    },
    [facts, effectiveOrder, emit]
  );

  if (!effectiveOrder.length) return null;

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={effectiveOrder} strategy={verticalListSortingStrategy}>
        <div className="space-y-2">
          {effectiveOrder.map((key) => (
            <SortableFactRow
              key={key}
              factKey={key}
              value={(facts || {})[key] ?? ''}
              onRenameKey={renameKey}
              onChangeValue={changeValue}
              onDelete={deleteRow}
            />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}

