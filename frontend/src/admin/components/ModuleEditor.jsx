import { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  DndContext, closestCenter, KeyboardSensor, 
  PointerSensor, useSensor, useSensors
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
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '@/components/ui/select';
import { Card, CardContent } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter
} from '@/components/ui/dialog';
import { 
  Plus, GripVertical, Trash2, Edit,
  FileText, Clock, Users, Tv, Table, Image, Play, Quote,
  HelpCircle, Award, Star, Zap, Shuffle, List, Film, Tag, X, Trophy, Vote, Loader2
} from 'lucide-react';
import { cn } from '@/lib/utils';
import RichTextEditor from './RichTextEditor';
import ModuleDataFields from './ModuleDataFields';
import { moduleNames, getAvailableModuleTypes } from '@/moduleContract';
import { contentApi } from '../utils/api';

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

function PollModuleEditor({ data, updateData }) {
  const [poll, setPoll] = useState({
    question: '',
    status: 'draft',
    show_results_before_vote: false,
    options: [
      { id: crypto.randomUUID(), text: '', historical_votes: 0 },
      { id: crypto.randomUUID(), text: '', historical_votes: 0 }
    ]
  });
  const [loading, setLoading] = useState(Boolean(data.poll_id));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    let active = true;
    if (!data.poll_id) return undefined;
    contentApi.getPollForEdit(data.poll_id)
      .then((response) => active && setPoll({ ...response.data, options: response.data.options || [] }))
      .catch(() => active && setMessage('Не удалось загрузить выбранный опрос'))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [data.poll_id]);

  const setOption = (index, text) => setPoll((current) => ({
    ...current,
    options: current.options.map((option, optionIndex) => optionIndex === index ? { ...option, text } : option)
  }));

  const save = async () => {
    setSaving(true);
    setMessage('');
    try {
      const payload = {
        question: poll.question,
        status: poll.status,
        show_results_before_vote: Boolean(poll.show_results_before_vote),
        options: poll.options.map(({ id, text, historical_votes = 0 }) => ({ id, text, historical_votes }))
      };
      let pollId = data.poll_id;
      if (pollId) {
        await contentApi.updatePoll(pollId, payload);
      } else {
        const response = await contentApi.createPoll(payload);
        pollId = response.data.id;
        updateData({ ...data, poll_id: pollId });
      }
      setMessage('Опрос сохранён');
    } catch (error) {
      setMessage(error.response?.data?.detail || 'Не удалось сохранить опрос');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Загрузка опроса...</div>;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Вопрос</Label>
        <Textarea value={poll.question} onChange={(event) => setPoll((current) => ({ ...current, question: event.target.value }))} rows={2} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label>Статус</Label>
          <Select value={poll.status} onValueChange={(status) => setPoll((current) => ({ ...current, status }))}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="draft">Черновик</SelectItem>
              <SelectItem value="published">Опубликован</SelectItem>
              <SelectItem value="archived">Скрыт</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-end gap-2 pb-2">
          <Switch checked={Boolean(poll.show_results_before_vote)} onCheckedChange={(value) => setPoll((current) => ({ ...current, show_results_before_vote: value }))} />
          <Label>Показывать результаты до голосования</Label>
        </div>
      </div>
      <div className="space-y-2">
        <Label>Варианты ответа</Label>
        {poll.options.map((option, index) => (
          <div key={option.id} className="flex gap-2">
            <Input value={option.text} onChange={(event) => setOption(index, event.target.value)} placeholder={`Вариант ${index + 1}`} />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={poll.options.length <= 2 || Number(option.historical_votes || 0) > 0}
              onClick={() => setPoll((current) => ({ ...current, options: current.options.filter((_, itemIndex) => itemIndex !== index) }))}
              aria-label={`Удалить вариант ${index + 1}`}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
        <Button type="button" variant="outline" onClick={() => setPoll((current) => ({ ...current, options: [...current.options, { id: crypto.randomUUID(), text: '', historical_votes: 0 }] }))}>
          <Plus className="mr-2 h-4 w-4" />Добавить вариант
        </Button>
      </div>
      <div className="flex items-center gap-3">
        <Button type="button" onClick={save} disabled={saving}>
          {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Сохранить опрос
        </Button>
        {data.poll_id && <span className="text-xs text-muted-foreground">ID: {data.poll_id}</span>}
      </div>
      {message && <Alert><AlertDescription>{message}</AlertDescription></Alert>}
    </div>
  );
}

// Separate component for editing module to manage its own state
function ModuleEditDialog({ module, open, onClose, onSave }) {
  const [localModule, setLocalModule] = useState(() => {
    if (!module) return null;
    return { ...module, data: { ...module.data } };
  });

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
    setLocalModule(prev => {
      if (!prev) return null;
      const next = { ...prev, data: newData };

      // Для text_block хотим, чтобы название модуля в списке совпадало с заголовком блока
      // (data.title), чтобы админка была удобнее.
      if (prev.type === 'text_block' && typeof newData?.title === 'string') {
        next.title = newData.title;
      }

      return next;
    });
  }, []);

  if (!localModule) return null;

  const data = localModule.data || {};

  const renderEditor = () => {
    switch (localModule.type) {
      case 'participants': {
        // Карточки участников шоу: имя, страница человека (slug), фото, факты «название — значение»
        const items = data.items || [];
        const setItems = (next) => updateData({ ...data, items: next });
        const setItem = (index, patch) => setItems(items.map((it, i) => (i === index ? { ...it, ...patch } : it)));
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Заголовок блока</Label>
              <Input
                value={data.title || ''}
                onChange={(e) => updateData({ ...data, title: e.target.value })}
                placeholder="Участники"
              />
            </div>
            {items.map((item, index) => (
              <div key={index} className="border rounded-lg p-4 space-y-3 bg-muted/20">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{item.name || `Участник ${index + 1}`}</span>
                  <Button variant="ghost" size="icon" onClick={() => setItems(items.filter((_, i) => i !== index))}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
                <div className="grid sm:grid-cols-3 gap-2">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Имя</Label>
                    <Input value={item.name || ''} onChange={(e) => setItem(index, { name: e.target.value })} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Страница человека (slug)</Label>
                    <Input value={item.person_slug || ''} onChange={(e) => setItem(index, { person_slug: e.target.value || null })} placeholder="anton-shastun" />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Фото (URL)</Label>
                    <Input value={item.photo || ''} onChange={(e) => setItem(index, { photo: e.target.value })} placeholder="/media/imported/images/..." />
                  </div>
                </div>
                {(item.facts || []).map((fact, j) => (
                  <div key={j} className="flex gap-2">
                    <Input
                      className="w-1/3"
                      value={fact.title || ''}
                      placeholder="Название"
                      onChange={(e) => setItem(index, { facts: item.facts.map((f, k) => (k === j ? { ...f, title: e.target.value } : f)) })}
                    />
                    <Input
                      className="flex-1"
                      value={fact.value || ''}
                      placeholder="Значение"
                      onChange={(e) => setItem(index, { facts: item.facts.map((f, k) => (k === j ? { ...f, value: e.target.value } : f)) })}
                    />
                    <Button variant="ghost" size="icon" onClick={() => setItem(index, { facts: item.facts.filter((_, k) => k !== j) })}>
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
                <Button variant="outline" size="sm" onClick={() => setItem(index, { facts: [...(item.facts || []), { title: '', value: '' }] })}>
                  <Plus className="mr-1 h-3 w-3" /> Факт
                </Button>
              </div>
            ))}
            <Button variant="outline" onClick={() => setItems([...items, { name: '', person_slug: null, photo: '', facts: [] }])}>
              <Plus className="mr-2 h-4 w-4" /> Добавить участника
            </Button>
          </div>
        );
      }

      case 'poll':
        return <PollModuleEditor data={data} updateData={updateData} />;

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
            <div className="flex items-center gap-2">
              <Switch
                checked={Boolean(data.collapsed)}
                onCheckedChange={(v) => updateData({ ...data, collapsed: v })}
              />
              <Label>Свёрнут по умолчанию (раскрывается по клику на заголовок)</Label>
            </div>
            <div className="space-y-2">
              <Label>Содержимое</Label>
              <RichTextEditor
                content={data.content || ''}
                onChange={(html) => updateData({ ...data, content: html })}
                placeholder="Начните вводить текст..."
              />
            </div>
          </div>
        );
      
      case 'timeline':
        // В контенте timeline хранится в data.events.
        // Ранее редактор использовал data.items — поддерживаем оба формата.
        const events = data.events || data.items || [];
        const setEvents = (newEvents) => {
          const nextData = { ...data, events: newEvents };
          if (nextData.items) delete nextData.items;
          updateData(nextData);
        };

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
            
            <div className="space-y-4">
              {events.map((item, index) => (
                <div key={index} className="border rounded-lg p-4 space-y-3 bg-muted/20">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Событие {index + 1}</span>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={() => setEvents(events.filter((_, i) => i !== index))}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Год / период</Label>
                      <Input
                        value={item.year || item.date || ''}
                        onChange={(e) => {
                          const newEvents = [...events];
                          newEvents[index] = { ...newEvents[index], year: e.target.value };
                          setEvents(newEvents);
                        }}
                        placeholder="2007-2013"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Заголовок</Label>
                      <Input
                        value={item.title || ''}
                        onChange={(e) => {
                          const newEvents = [...events];
                          newEvents[index] = { ...newEvents[index], title: e.target.value };
                          setEvents(newEvents);
                        }}
                        placeholder="Название события"
                      />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Описание</Label>
                    <RichTextEditor
                      content={item.description || ''}
                      onChange={(html) => {
                        const newEvents = [...events];
                        newEvents[index] = { ...newEvents[index], description: html };
                        setEvents(newEvents);
                      }}
                      placeholder="Описание события..."
                      minHeight={100}
                    />
                  </div>
                </div>
              ))}
            </div>
            
            <Button 
              type="button" 
              variant="outline" 
              onClick={() => setEvents([
                ...events,
                { year: '', title: '', description: '' }
              ])} 
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

      case 'table_of_contents':
        return <Alert><AlertDescription>
          Маркер оглавления. Сейчас оглавление формируется шаблоном страницы там, где оно предусмотрено.
          Сохранённые настройки режима и позиции не управляли отображением и остаются в данных для совместимости.
        </AlertDescription></Alert>;
      case 'table':
        // Table editor
        const rows = data.rows || [['', '']];
        const headers = data.headers || [];
        const hasHeaders = data.hasHeaders !== false;
        
        const addRow = () => {
          const colCount = rows[0]?.length || 2;
          updateData({ ...data, rows: [...rows, Array(colCount).fill('')] });
        };
        
        const removeRow = (rowIdx) => {
          if (rows.length > 1) {
            updateData({ ...data, rows: rows.filter((_, i) => i !== rowIdx) });
          }
        };
        
        const addColumn = () => {
          const newRows = rows.map(row => [...row, '']);
          const newHeaders = hasHeaders ? [...headers, ''] : headers;
          updateData({ ...data, rows: newRows, headers: newHeaders });
        };
        
        const removeColumn = (colIdx) => {
          if ((rows[0]?.length || 0) > 1) {
            const newRows = rows.map(row => row.filter((_, i) => i !== colIdx));
            const newHeaders = hasHeaders ? headers.filter((_, i) => i !== colIdx) : headers;
            updateData({ ...data, rows: newRows, headers: newHeaders });
          }
        };
        
        const updateCell = (rowIdx, colIdx, value) => {
          const newRows = rows.map((row, ri) => 
            ri === rowIdx ? row.map((cell, ci) => ci === colIdx ? value : cell) : row
          );
          updateData({ ...data, rows: newRows });
        };
        
        const updateHeader = (colIdx, value) => {
          const newHeaders = headers.map((h, i) => i === colIdx ? value : h);
          updateData({ ...data, headers: newHeaders });
        };
        
        // Initialize headers if needed
        if (hasHeaders && headers.length === 0 && rows[0]) {
          updateData({ ...data, headers: Array(rows[0].length).fill('') });
        }
        
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Заголовок таблицы</Label>
              <Input
                value={data.title || ''}
                onChange={(e) => updateData({ ...data, title: e.target.value })}
                placeholder="Название таблицы (опционально)"
              />
            </div>
            
            <div className="flex items-center gap-2">
              <Switch
                checked={hasHeaders}
                onCheckedChange={(v) => {
                  if (v && headers.length === 0 && rows[0]) {
                    updateData({ ...data, hasHeaders: v, headers: Array(rows[0].length).fill('') });
                  } else {
                    updateData({ ...data, hasHeaders: v });
                  }
                }}
              />
              <Label>Заголовки столбцов</Label>
            </div>

            <div className="space-y-2">
              <Label>Пояснение над таблицей</Label>
              <Textarea
                value={data.description || ''}
                onChange={(e) => updateData({ ...data, description: e.target.value })}
                placeholder="Легенда: что означают столбцы (опционально)"
                rows={2}
              />
            </div>

            <div className="flex flex-wrap items-center gap-6">
              <div className="flex items-center gap-2">
                <Switch
                  checked={Boolean(data.sortable)}
                  onCheckedChange={(v) => updateData({ ...data, sortable: v })}
                />
                <Label>Сортировка по клику на заголовок</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={Boolean(data.collapsed)}
                  onCheckedChange={(v) => updateData({ ...data, collapsed: v })}
                />
                <Label>Свёрнута по умолчанию</Label>
              </div>
            </div>

            <div className="border rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  {hasHeaders && headers.length > 0 && (
                    <thead className="bg-muted">
                      <tr>
                        {headers.map((header, colIdx) => (
                          <th key={colIdx} className="p-1 border-r last:border-r-0">
                            <Input
                              value={header}
                              onChange={(e) => updateHeader(colIdx, e.target.value)}
                              placeholder={`Колонка ${colIdx + 1}`}
                              className="h-8 text-center font-medium"
                            />
                          </th>
                        ))}
                        <th className="w-10 p-1">
                          <Button 
                            type="button" 
                            variant="ghost" 
                            size="icon" 
                            onClick={addColumn}
                            className="h-8 w-8"
                          >
                            <Plus className="h-4 w-4" />
                          </Button>
                        </th>
                      </tr>
                    </thead>
                  )}
                  <tbody>
                    {rows.map((row, rowIdx) => (
                      <tr key={rowIdx} className="border-t">
                        {row.map((cell, colIdx) => (
                          <td key={colIdx} className="p-1 border-r last:border-r-0">
                            <Input
                              value={cell}
                              onChange={(e) => updateCell(rowIdx, colIdx, e.target.value)}
                              className="h-8"
                            />
                          </td>
                        ))}
                        <td className="w-10 p-1">
                          <div className="flex gap-1">
                            {rows.length > 1 && (
                              <Button 
                                type="button" 
                                variant="ghost" 
                                size="icon" 
                                onClick={() => removeRow(rowIdx)}
                                className="h-8 w-8 text-destructive hover:text-destructive"
                              >
                                <X className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={addRow} className="flex-1">
                <Plus className="mr-2 h-4 w-4" /> Добавить строку
              </Button>
              {!hasHeaders && (
                <Button type="button" variant="outline" onClick={addColumn} className="flex-1">
                  <Plus className="mr-2 h-4 w-4" /> Добавить столбец
                </Button>
              )}
            </div>
            
            {(rows[0]?.length || 0) > 1 && (
              <div className="flex gap-2 flex-wrap">
                <span className="text-sm text-muted-foreground">Удалить столбец:</span>
                {rows[0]?.map((_, colIdx) => (
                  <Button
                    key={colIdx}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => removeColumn(colIdx)}
                    className="h-7 px-2"
                  >
                    {colIdx + 1} <X className="ml-1 h-3 w-3" />
                  </Button>
                ))}
              </div>
            )}
          </div>
        );
      
      // ===== СИСТЕМНЫЕ МОДУЛИ =====
      
      case 'poster_photo':
      case 'facts_table':
      case 'rating_widget':
      case 'tags_cloud':
      case 'social_links':
        return <Alert><AlertDescription>
          Системный блок использует основные поля страницы: фото, факты, рейтинг, теги или социальные ссылки.
          Редактируйте эти данные в соответствующих разделах карточки. Расположение и оформление задаёт шаблон страницы.
          Сохранённые дополнительные настройки остаются в данных для совместимости.
        </AlertDescription></Alert>;
      case 'first_league_champions':
        return (
          <div className="space-y-4">
            <Alert>
              <AlertDescription>
                Таблица чемпионов строится автоматически по данным дочерних сезонов Первой лиги.
                Порядок блока можно менять перетаскиванием в списке модулей. Заголовок блока можно задать ниже.
              </AlertDescription>
            </Alert>
          </div>
        );

      case 'vl_league_champions':
        return (
          <div className="space-y-4">
            <Alert>
              <AlertDescription>
                Таблица чемпионов строится автоматически по данным дочерних сезонов Высшей лиги.
                Порядок блока можно менять перетаскиванием в списке модулей. Заголовок блока можно задать ниже.
              </AlertDescription>
            </Alert>
          </div>
        );
      
      default:
        return <ModuleDataFields type={localModule.type} data={data} onChange={updateData} />;
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleSave()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
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
            <div className="flex items-center gap-2">
              <Switch id="module-visible" checked={localModule.visible !== false}
                onCheckedChange={visible => updateLocalModule({ visible })} />
              <Label htmlFor="module-visible">Показывать модуль</Label>
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
