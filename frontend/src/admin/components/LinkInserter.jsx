import { useState, useEffect } from 'react';
import { Search, X, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { contentApi } from '../utils/api';

export default function LinkInserter({ editor, onInsert }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedTypes, setSelectedTypes] = useState(['person', 'team', 'show', 'kvn']);

  const searchContent = async (searchQuery) => {
    if (!searchQuery || searchQuery.length < 2) {
      setResults([]);
      return;
    }

    setLoading(true);
    try {
      const response = await contentApi.searchContent(searchQuery, selectedTypes.join(','));
      setResults(response.data.results || []);
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      searchContent(query);
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [query, selectedTypes]);

  const handleInsert = (item) => {
    if (editor) {
      // Для TipTap редактора
      const url = item.url;
      const title = item.title;
      
      // Вставляем ссылку в редактор
      editor.chain().focus().insertContent(
        `<a href="${url}">${title}</a>`
      ).run();
    } else if (onInsert) {
      // Альтернативный способ - через callback
      onInsert(`<a href="${item.url}">${item.title}</a>`);
    }
    
    setOpen(false);
    setQuery('');
    setResults([]);
  };

  const handleInsertExternal = () => {
    const url = prompt('Введите URL внешней ссылки:');
    if (!url) return;
    
    const text = prompt('Введите текст ссылки (или оставьте пустым для URL):') || url;
    
    if (editor) {
      editor.chain().focus().insertContent(
        `<a href="${url}" target="_blank" rel="noopener noreferrer">${text}</a>`
      ).run();
    } else if (onInsert) {
      onInsert(`<a href="${url}" target="_blank" rel="noopener noreferrer">${text}</a>`);
    }
    
    setOpen(false);
  };

  const typeLabels = {
    person: 'Люди',
    team: 'Команды',
    show: 'Шоу',
    kvn: 'КВН',
  };

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
      >
        <ExternalLink className="h-4 w-4 mr-2" />
        Вставить ссылку
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Вставка ссылки</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Фильтр типов */}
            <div className="flex flex-wrap gap-2">
              {Object.entries(typeLabels).map(([type, label]) => (
                <Button
                  key={type}
                  type="button"
                  variant={selectedTypes.includes(type) ? "default" : "outline"}
                  size="sm"
                  onClick={() => {
                    if (selectedTypes.includes(type)) {
                      setSelectedTypes(selectedTypes.filter(t => t !== type));
                    } else {
                      setSelectedTypes([...selectedTypes, type]);
                    }
                  }}
                >
                  {label}
                </Button>
              ))}
            </div>

            {/* Поиск */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Поиск страниц..."
                className="pl-10"
              />
            </div>

            {/* Кнопка для внешних ссылок */}
            <Button
              type="button"
              variant="outline"
              onClick={handleInsertExternal}
              className="w-full"
            >
              <ExternalLink className="h-4 w-4 mr-2" />
              Вставить внешнюю ссылку
            </Button>

            {/* Результаты поиска */}
            {loading && <div className="text-center py-4">Поиск...</div>}
            
            {!loading && query.length >= 2 && results.length === 0 && (
              <div className="text-center py-4 text-gray-500">
                Ничего не найдено
              </div>
            )}

            {results.length > 0 && (
              <div className="border rounded-md max-h-60 overflow-y-auto">
                {results.map((item, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => handleInsert(item)}
                    className="w-full text-left px-4 py-2 hover:bg-gray-100 border-b last:border-b-0"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium">{item.title}</div>
                        <div className="text-sm text-gray-500">
                          {typeLabels[item.type]} • {item.url}
                        </div>
                      </div>
                      <ExternalLink className="h-4 w-4 text-gray-400" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
