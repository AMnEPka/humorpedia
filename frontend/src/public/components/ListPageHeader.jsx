import { Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export default function ListPageHeader({
  title,
  description,
  search,
  onSearchChange,
  onSearch,
  placeholder,
  searchId,
  children,
}) {
  return (
    <div className="mb-8 space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{title}</h1>
          {description && <p className="mt-2 text-lg text-gray-600">{description}</p>}
        </div>
        {onSearch && <form onSubmit={onSearch} className="flex w-full gap-2 sm:w-80">
          <label htmlFor={searchId} className="sr-only">{placeholder}</label>
          <Input
            id={searchId}
            type="search"
            placeholder={placeholder}
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            className="min-w-0 min-h-11 flex-1"
          />
          <Button type="submit" size="icon" aria-label="Найти" className="min-w-11 min-h-11">
            <Search className="h-4 w-4" />
          </Button>
        </form>}
      </div>
      {children}
    </div>
  );
}
