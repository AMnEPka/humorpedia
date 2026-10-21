import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Plus, X } from 'lucide-react';
import { useEffect } from 'react';
import { ensureTableHeaders, updateTableCell, updateTableHeader, appendTableRow, removeTableRow, appendTableColumn, removeTableColumn } from './operations';
export default function TableModuleEditor({ data, updateData }) {
  const rows = data.rows || [['', '']];
  const headers = data.headers || [];
  const hasHeaders = data.hasHeaders !== false;
  const addRow = () => updateData(appendTableRow(data));
  const removeRow = row => updateData(removeTableRow(data, row));
  const addColumn = () => updateData(appendTableColumn(data));
  const removeColumn = column => updateData(removeTableColumn(data, column));
  const updateCell = (row, column, value) => updateData(updateTableCell(data, row, column, value));
  const updateHeader = (column, value) => updateData(updateTableHeader(data, column, value));
  useEffect(() => {
    const next = ensureTableHeaders(data);
    if (next !== data) updateData(next);
  }, [data, updateData]);
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
}
