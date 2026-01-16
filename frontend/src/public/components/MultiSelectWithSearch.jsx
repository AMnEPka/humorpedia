import { useState, useMemo } from 'react';
import { X, Search } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';

export default function MultiSelectWithSearch({
  value = [],
  onChange,
  options = [],
  placeholder = "Выберите...",
  searchPlaceholder = "Поиск...",
  getOptionLabel = (option) => String(option),
  getOptionValue = (option) => String(option),
  filterOptions = (options, search) => {
    const query = search.toLowerCase();
    return options.filter(option => {
      const label = getOptionLabel(option).toLowerCase();
      return label.includes(query);
    });
  },
  renderOption = (option) => getOptionLabel(option),
  renderSelected = (option) => getOptionLabel(option),
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  // Filter options based on search
  const filteredOptions = useMemo(() => {
    if (!search.trim()) {
      return options;
    }
    return filterOptions(options, search);
  }, [options, search, filterOptions]);

  // Get selected options
  const selectedOptions = useMemo(() => {
    return value.map(val => {
      const found = options.find(opt => getOptionValue(opt) === val);
      // If found, return the option object, otherwise create a simple wrapper
      if (found) {
        return found;
      }
      // For values not in current options (e.g., when options are filtered), create a wrapper
      return { __value: val, __label: String(val) };
    });
  }, [value, options, getOptionValue]);

  // Available options (not selected)
  const availableOptions = useMemo(() => {
    return filteredOptions.filter(option => {
      const optionValue = getOptionValue(option);
      return !value.includes(optionValue);
    });
  }, [filteredOptions, value, getOptionValue]);

  const addOption = (option) => {
    const optionValue = getOptionValue(option);
    if (!value.includes(optionValue)) {
      onChange([...value, optionValue]);
    }
    setSearch('');
    setOpen(false);
  };

  const removeOption = (optionValue) => {
    onChange(value.filter(v => v !== optionValue));
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (availableOptions.length > 0) {
        addOption(availableOptions[0]);
      }
    }
  };

  return (
    <div className="space-y-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between font-normal"
          >
            <span className="text-muted-foreground">{placeholder}</span>
            <Search className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[400px] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput 
              placeholder={searchPlaceholder}
              value={search}
              onValueChange={setSearch}
              onKeyDown={handleKeyDown}
            />
            <CommandList>
              {availableOptions.length === 0 ? (
                <CommandEmpty>
                  {search.trim() ? 'Ничего не найдено' : 'Нет доступных вариантов'}
                </CommandEmpty>
              ) : (
                <CommandGroup heading="Результаты">
                  {availableOptions.map((option, index) => (
                    <CommandItem
                      key={index}
                      onSelect={() => addOption(option)}
                      className="cursor-pointer"
                    >
                      {renderOption(option)}
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {/* Selected items */}
      {selectedOptions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selectedOptions.map((option, index) => {
            // Handle both object options and simple values
            const optionValue = option.__value !== undefined 
              ? option.__value 
              : getOptionValue(option);
            const displayLabel = option.__label !== undefined
              ? option.__label
              : renderSelected(option);
            return (
              <Badge key={index} variant="secondary" className="pr-1">
                {displayLabel}
                <button
                  type="button"
                  onClick={() => removeOption(optionValue)}
                  className="ml-1 hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            );
          })}
        </div>
      )}
    </div>
  );
}
