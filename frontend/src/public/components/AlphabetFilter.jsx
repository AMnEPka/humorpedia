import { cn } from '@/lib/utils';

export const RUSSIAN_ALPHABET = 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'.split('');
export const OTHER_ALPHABET_FILTER = 'other';

export default function AlphabetFilter({ selectedLetter, onLetterClick }) {
  return (
    <div className="flex flex-wrap gap-1" aria-label="Фильтр по первой букве">
      {RUSSIAN_ALPHABET.map((letter) => (
        <button
          key={letter}
          type="button"
          aria-pressed={selectedLetter === letter}
          onClick={() => onLetterClick(selectedLetter === letter ? '' : letter)}
          className={cn(
            'w-8 h-8 text-sm font-medium rounded transition-colors',
            selectedLetter === letter
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
          )}
        >
          {letter}
        </button>
      ))}
      <button
        type="button"
        aria-label="Латиница, цифры и символы"
        aria-pressed={selectedLetter === OTHER_ALPHABET_FILTER}
        onClick={() => onLetterClick(
          selectedLetter === OTHER_ALPHABET_FILTER ? '' : OTHER_ALPHABET_FILTER
        )}
        className={cn(
          'px-2 h-8 text-sm font-medium rounded transition-colors whitespace-nowrap',
          selectedLetter === OTHER_ALPHABET_FILTER
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
        )}
      >
        A–Z 0–9 #
      </button>
      {selectedLetter && (
        <button
          type="button"
          onClick={() => onLetterClick('')}
          className="px-3 h-8 text-sm font-medium rounded bg-red-100 text-red-600 hover:bg-red-200"
        >
          Сбросить
        </button>
      )}
    </div>
  );
}
