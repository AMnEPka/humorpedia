import { arrayMove } from '@dnd-kit/sortable';

export function createModule(type, order, id = crypto.randomUUID()) {
  return { id, type, order, visible: true, data: {} };
}

export function createModuleDraft(module) {
  return module ? JSON.parse(JSON.stringify({ ...module, data: { ...module.data } })) : null;
}

export function updateModuleData(module, data) {
  if (!module) return null;
  return { ...module, data, ...(module.type === 'text_block' && typeof data?.title === 'string' ? { title: data.title } : {}) };
}

export function replaceModule(modules, updated) {
  return modules.map(module => module.id === updated.id ? updated : module);
}

export function reorderModules(modules, activeId, overId) {
  const from = modules.findIndex(module => module.id === activeId);
  const to = modules.findIndex(module => module.id === overId);
  if (from < 0 || to < 0 || from === to) return modules;
  return arrayMove(modules, from, to).map((module, order) => ({ ...module, order }));
}

export function withTimelineEvents(data, events) {
  const next = { ...data, events };
  if (next.items) delete next.items;
  return next;
}

const rowsOf = data => data.rows || [['', '']];
export function ensureTableHeaders(data) {
  const rows = rowsOf(data);
  return data.hasHeaders !== false && !(data.headers || []).length && rows[0]
    ? { ...data, headers: Array(rows[0].length).fill('') } : data;
}
export function updateTableCell(data, row, column, value) {
  return { ...data, rows: rowsOf(data).map((items, r) => r === row ? items.map((cell, c) => c === column ? value : cell) : items) };
}
export function updateTableHeader(data, column, value) {
  return { ...data, headers: (data.headers || []).map((header, index) => index === column ? value : header) };
}
export function appendTableRow(data) {
  const rows = rowsOf(data);
  return { ...data, rows: [...rows, Array(rows[0]?.length || 2).fill('')] };
}
export function removeTableRow(data, row) {
  const rows = rowsOf(data);
  return rows.length > 1 ? { ...data, rows: rows.filter((_, index) => index !== row) } : data;
}
export function appendTableColumn(data) {
  return { ...data, rows: rowsOf(data).map(row => [...row, '']),
    headers: data.hasHeaders !== false ? [...(data.headers || []), ''] : (data.headers || []) };
}
export function removeTableColumn(data, column) {
  const rows = rowsOf(data);
  if ((rows[0]?.length || 0) <= 1) return data;
  return { ...data, rows: rows.map(row => row.filter((_, index) => index !== column)),
    headers: data.hasHeaders !== false ? (data.headers || []).filter((_, index) => index !== column) : (data.headers || []) };
}
