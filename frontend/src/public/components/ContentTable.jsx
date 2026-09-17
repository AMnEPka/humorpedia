import { useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';

// Число из ячейки: «1 224 000», «-162000», «12,5» → number; иначе null
function toNumber(value) {
  const text = String(value ?? '').replace(/[\s ₽%]/g, '').replace(',', '.');
  return /^-?\d+(\.\d+)?$/.test(text) ? Number(text) : null;
}

function formatCell(value) {
  const n = toNumber(value);
  // крупные целые — с разрядами, как на старом сайте в текстах («2 798 500»)
  return n !== null && Number.isInteger(n) && Math.abs(n) >= 10000 ? n.toLocaleString('ru-RU') : value;
}

function CellValue({ value }) {
  const formatted = formatCell(value);
  if (typeof formatted === 'string' && formatted.includes('<')) {
    return <span dangerouslySetInnerHTML={{ __html: formatted }} />;
  }
  return formatted;
}

/**
 * Таблица модуля `table` ({headers, rows, hasHeaders, sortable, description}).
 * При sortable — сортировка по клику на заголовок (числа сравниваются как числа).
 */
export default function ContentTable({ data }) {
  const rows = data?.rows || [];
  const headers = data?.headers || [];
  const hasHeaders = data?.hasHeaders !== false && headers.length > 0;
  const sortable = Boolean(data?.sortable) && hasHeaders;
  const [sort, setSort] = useState({ column: null, direction: 'asc' });

  const sortedRows = useMemo(() => {
    if (!sortable || sort.column === null) return rows;
    const column = sort.column;
    const numeric = rows.every((row) => row[column] === '' || row[column] == null || toNumber(row[column]) !== null);
    const factor = sort.direction === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      if (numeric) return ((toNumber(a[column]) ?? -Infinity) - (toNumber(b[column]) ?? -Infinity)) * factor;
      return String(a[column] ?? '').localeCompare(String(b[column] ?? ''), 'ru') * factor;
    });
  }, [rows, sortable, sort]);

  if (rows.length === 0) return null;

  const toggleSort = (column) => {
    setSort((prev) => (prev.column === column
      ? { column, direction: prev.direction === 'asc' ? 'desc' : 'asc' }
      : { column, direction: 'desc' }));
  };

  return (
    <div>
      {data?.description && <p className="text-sm text-gray-600 mb-3">{data.description}</p>}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse border border-gray-200 text-sm">
          {hasHeaders && (
            <thead className="bg-gray-100">
              <tr>
                {headers.map((header, i) => (
                  <th key={i} className="border border-gray-200 px-3 py-2 text-left font-medium align-bottom">
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(i)}
                        className="inline-flex items-center gap-1 hover:text-blue-600 text-left"
                        title="Сортировать"
                      >
                        {header}
                        {sort.column === i
                          ? (sort.direction === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)
                          : <ArrowUpDown className="h-3 w-3 opacity-40" />}
                      </button>
                    ) : header}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {sortedRows.map((row, rowIdx) => (
              <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                {row.map((cell, cellIdx) => (
                  <td key={cellIdx} className={`border border-gray-200 px-3 py-2 ${toNumber(cell) !== null ? 'whitespace-nowrap text-right' : ''}`}>
                    <CellValue value={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
