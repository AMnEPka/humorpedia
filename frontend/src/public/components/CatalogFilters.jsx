import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const valuesFromUrl = (fields, searchParams) => Object.fromEntries(
  fields.map(({ name }) => [name, searchParams.get(name) || ''])
);

export default function CatalogFilters({ fields, searchParams, setSearchParams }) {
  const [values, setValues] = useState(() => valuesFromUrl(fields, searchParams));
  const visibleFields = fields.filter(({ name, type, options }) =>
    type === 'text' || (options?.length || searchParams.has(name))
  );
  if (visibleFields.length === 0) return null;

  const updateValue = (name, value) => setValues(current => ({ ...current, [name]: value }));
  const apply = event => {
    event.preventDefault();
    const params = new URLSearchParams(searchParams);
    fields.forEach(({ name }) => {
      const value = (values[name] || '').trim();
      if (value) params.set(name, value);
      else params.delete(name);
    });
    params.delete('page');
    setSearchParams(params);
  };
  const reset = () => {
    const params = new URLSearchParams(searchParams);
    fields.forEach(({ name }) => params.delete(name));
    params.delete('page');
    setValues(valuesFromUrl(fields, params));
    setSearchParams(params);
  };

  return (
    <form onSubmit={apply} className="mb-6 rounded-xl border border-gray-200 bg-gray-50 p-4" aria-label="Фильтры каталога">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {visibleFields.map(({ name, label, type, options = [], placeholder, defaultLabel = 'Все' }) => {
          const id = `catalog-filter-${name}`;
          return (
            <div key={name} className="space-y-1">
              <label htmlFor={id} className="block text-sm font-medium text-gray-700">{label}</label>
              {type === 'text' ? (
                <Input id={id} value={values[name] || ''} onChange={event => updateValue(name, event.target.value)}
                  placeholder={placeholder} className="min-h-11 bg-white" />
              ) : (
                <select id={id} value={values[name] || ''} onChange={event => updateValue(name, event.target.value)}
                  className="flex min-h-11 w-full rounded-md border border-input bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <option value="">{defaultLabel}</option>
                  {values[name] && !options.some(option => option.value === values[name]) && (
                    <option value={values[name]}>{values[name]}</option>
                  )}
                  {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button type="submit" className="min-h-11">Применить</Button>
        {fields.some(({ name }) => searchParams.has(name)) && (
          <Button type="button" variant="outline" onClick={reset} className="min-h-11">Сбросить фильтры</Button>
        )}
      </div>
    </form>
  );
}
