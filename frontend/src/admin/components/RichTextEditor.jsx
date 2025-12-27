import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Underline } from '@tiptap/extension-underline';
import { TextAlign } from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import { Highlight } from '@tiptap/extension-highlight';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';
import { useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { 
  Bold, Italic, Underline as UnderlineIcon, Strikethrough,
  List, ListOrdered, AlignLeft, AlignCenter, AlignRight, AlignJustify,
  Heading1, Heading2, Heading3, Quote, Minus, Undo, Redo,
  Table as TableIcon, Palette, Highlighter, RemoveFormatting
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';

const colors = [
  { name: 'Чёрный', value: '#000000' },
  { name: 'Серый', value: '#6b7280' },
  { name: 'Красный', value: '#dc2626' },
  { name: 'Оранжевый', value: '#ea580c' },
  { name: 'Жёлтый', value: '#ca8a04' },
  { name: 'Зелёный', value: '#16a34a' },
  { name: 'Синий', value: '#2563eb' },
  { name: 'Фиолетовый', value: '#9333ea' },
];

const highlightColors = [
  { name: 'Жёлтый', value: '#fef08a' },
  { name: 'Зелёный', value: '#bbf7d0' },
  { name: 'Голубой', value: '#bfdbfe' },
  { name: 'Розовый', value: '#fbcfe8' },
  { name: 'Оранжевый', value: '#fed7aa' },
];

function MenuBar({ editor }) {
  if (!editor) return null;

  const ToolButton = ({ onClick, isActive, disabled, children, title }) => (
    <Button
      type="button"
      variant={isActive ? "secondary" : "ghost"}
      size="icon"
      className="h-8 w-8"
      onClick={onClick}
      disabled={disabled}
      title={title}
    >
      {children}
    </Button>
  );

  return (
    <div className="flex flex-wrap items-center gap-0.5 p-2 border-b bg-muted/30 rounded-t-md">
      {/* Undo/Redo */}
      <ToolButton onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()} title="Отменить">
        <Undo className="h-4 w-4" />
      </ToolButton>
      <ToolButton onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()} title="Повторить">
        <Redo className="h-4 w-4" />
      </ToolButton>

      <div className="w-px h-6 bg-border mx-1" />

      {/* Headings */}
      <ToolButton 
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        isActive={editor.isActive('heading', { level: 1 })}
        title="Заголовок 1"
      >
        <Heading1 className="h-4 w-4" />
      </ToolButton>
      <ToolButton 
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        isActive={editor.isActive('heading', { level: 2 })}
        title="Заголовок 2"
      >
        <Heading2 className="h-4 w-4" />
      </ToolButton>
      <ToolButton 
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        isActive={editor.isActive('heading', { level: 3 })}
        title="Заголовок 3"
      >
        <Heading3 className="h-4 w-4" />
      </ToolButton>

      <div className="w-px h-6 bg-border mx-1" />

      {/* Basic formatting */}
      <ToolButton 
        onClick={() => editor.chain().focus().toggleBold().run()}
        isActive={editor.isActive('bold')}
        title="Жирный"
      >
        <Bold className="h-4 w-4" />
      </ToolButton>
      <ToolButton 
        onClick={() => editor.chain().focus().toggleItalic().run()}
        isActive={editor.isActive('italic')}
        title="Курсив"
      >
        <Italic className="h-4 w-4" />
      </ToolButton>
      <ToolButton 
        onClick={() => editor.chain().focus().toggleUnderline().run()}
        isActive={editor.isActive('underline')}
        title="Подчёркнутый"
      >
        <UnderlineIcon className="h-4 w-4" />
      </ToolButton>
      <ToolButton 
        onClick={() => editor.chain().focus().toggleStrike().run()}
        isActive={editor.isActive('strike')}
        title="Зачёркнутый"
      >
        <Strikethrough className="h-4 w-4" />
      </ToolButton>

      <div className="w-px h-6 bg-border mx-1" />

      {/* Text color */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="h-8 w-8" title="Цвет текста">
            <Palette className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          {colors.map(color => (
            <DropdownMenuItem 
              key={color.value} 
              onClick={() => editor.chain().focus().setColor(color.value).run()}
            >
              <span className="w-4 h-4 rounded mr-2" style={{ backgroundColor: color.value }} />
              {color.name}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => editor.chain().focus().unsetColor().run()}>
            <RemoveFormatting className="h-4 w-4 mr-2" />
            Сбросить цвет
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Highlight */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="h-8 w-8" title="Выделение">
            <Highlighter className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          {highlightColors.map(color => (
            <DropdownMenuItem 
              key={color.value} 
              onClick={() => editor.chain().focus().toggleHighlight({ color: color.value }).run()}
            >
              <span className="w-4 h-4 rounded mr-2" style={{ backgroundColor: color.value }} />
              {color.name}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => editor.chain().focus().unsetHighlight().run()}>
            <RemoveFormatting className="h-4 w-4 mr-2" />
            Убрать выделение
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <div className="w-px h-6 bg-border mx-1" />

      {/* Lists */}
      <ToolButton 
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        isActive={editor.isActive('bulletList')}
        title="Маркированный список"
      >
        <List className="h-4 w-4" />
      </ToolButton>
      <ToolButton 
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        isActive={editor.isActive('orderedList')}
        title="Нумерованный список"
      >
        <ListOrdered className="h-4 w-4" />
      </ToolButton>

      <div className="w-px h-6 bg-border mx-1" />

      {/* Alignment */}
      <ToolButton 
        onClick={() => editor.chain().focus().setTextAlign('left').run()}
        isActive={editor.isActive({ textAlign: 'left' })}
        title="По левому краю"
      >
        <AlignLeft className="h-4 w-4" />
      </ToolButton>
      <ToolButton 
        onClick={() => editor.chain().focus().setTextAlign('center').run()}
        isActive={editor.isActive({ textAlign: 'center' })}
        title="По центру"
      >
        <AlignCenter className="h-4 w-4" />
      </ToolButton>
      <ToolButton 
        onClick={() => editor.chain().focus().setTextAlign('right').run()}
        isActive={editor.isActive({ textAlign: 'right' })}
        title="По правому краю"
      >
        <AlignRight className="h-4 w-4" />
      </ToolButton>
      <ToolButton 
        onClick={() => editor.chain().focus().setTextAlign('justify').run()}
        isActive={editor.isActive({ textAlign: 'justify' })}
        title="По ширине"
      >
        <AlignJustify className="h-4 w-4" />
      </ToolButton>

      <div className="w-px h-6 bg-border mx-1" />

      {/* Block elements */}
      <ToolButton 
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
        isActive={editor.isActive('blockquote')}
        title="Цитата"
      >
        <Quote className="h-4 w-4" />
      </ToolButton>
      <ToolButton 
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
        title="Горизонтальная линия"
      >
        <Minus className="h-4 w-4" />
      </ToolButton>

      <div className="w-px h-6 bg-border mx-1" />

      {/* Table */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button 
            variant={editor.isActive('table') ? "secondary" : "ghost"} 
            size="icon" 
            className="h-8 w-8" 
            title="Таблица"
          >
            <TableIcon className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}>
            Вставить таблицу 3×3
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => editor.chain().focus().insertTable({ rows: 4, cols: 4, withHeaderRow: true }).run()}>
            Вставить таблицу 4×4
          </DropdownMenuItem>
          {editor.isActive('table') && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => editor.chain().focus().addColumnBefore().run()}>
                Добавить столбец слева
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => editor.chain().focus().addColumnAfter().run()}>
                Добавить столбец справа
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => editor.chain().focus().addRowBefore().run()}>
                Добавить строку сверху
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => editor.chain().focus().addRowAfter().run()}>
                Добавить строку снизу
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => editor.chain().focus().deleteColumn().run()}>
                Удалить столбец
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => editor.chain().focus().deleteRow().run()}>
                Удалить строку
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => editor.chain().focus().deleteTable().run()} className="text-destructive">
                Удалить таблицу
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      <div className="w-px h-6 bg-border mx-1" />

      {/* Clear formatting */}
      <ToolButton 
        onClick={() => editor.chain().focus().clearNodes().unsetAllMarks().run()}
        title="Очистить форматирование"
      >
        <RemoveFormatting className="h-4 w-4" />
      </ToolButton>
    </div>
  );
}

export default function RichTextEditor({ content, onChange, placeholder = "Начните вводить текст...", minHeight = 200 }) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
      }),
      Underline,
      TextStyle,
      Color,
      Highlight.configure({
        multicolor: true,
      }),
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      Table.configure({
        resizable: true,
      }),
      TableRow,
      TableCell,
      TableHeader,
    ],
    content: content || '',
    editorProps: {
      attributes: {
        class: 'prose prose-sm max-w-none p-4 focus:outline-none',
      },
    },
    onUpdate: ({ editor }) => {
      onChange?.(editor.getHTML());
    },
  });

  // Update content when prop changes externally
  useEffect(() => {
    if (editor && content !== editor.getHTML()) {
      editor.commands.setContent(content || '');
    }
  }, [content, editor]);

  return (
    <div className="border rounded-md overflow-hidden">
      <MenuBar editor={editor} />
      <EditorContent editor={editor} />
      <style>{`
        .ProseMirror {
          min-height: ${minHeight}px;
          padding: 1rem;
        }
        .ProseMirror:focus {
          outline: none;
        }
        .ProseMirror > * + * {
          margin-top: 0.75em;
        }
        .ProseMirror h1 {
          font-size: 1.5rem;
          font-weight: 700;
          line-height: 1.2;
        }
        .ProseMirror h2 {
          font-size: 1.25rem;
          font-weight: 600;
          line-height: 1.3;
        }
        .ProseMirror h3 {
          font-size: 1.1rem;
          font-weight: 600;
          line-height: 1.4;
        }
        .ProseMirror ul, .ProseMirror ol {
          padding-left: 1.5rem;
        }
        .ProseMirror ul {
          list-style-type: disc;
        }
        .ProseMirror ol {
          list-style-type: decimal;
        }
        .ProseMirror blockquote {
          border-left: 3px solid #e5e7eb;
          padding-left: 1rem;
          color: #6b7280;
          font-style: italic;
        }
        .ProseMirror hr {
          border: none;
          border-top: 2px solid #e5e7eb;
          margin: 1rem 0;
        }
        .ProseMirror table {
          border-collapse: collapse;
          width: 100%;
          margin: 1rem 0;
        }
        .ProseMirror th, .ProseMirror td {
          border: 1px solid #d1d5db;
          padding: 0.5rem;
          text-align: left;
        }
        .ProseMirror th {
          background-color: #f3f4f6;
          font-weight: 600;
        }
        .ProseMirror mark {
          border-radius: 0.25rem;
          padding: 0.125rem 0.25rem;
        }
        .ProseMirror p.is-editor-empty:first-child::before {
          color: #adb5bd;
          content: attr(data-placeholder);
          float: left;
          height: 0;
          pointer-events: none;
        }
      `}</style>
    </div>
  );
}
