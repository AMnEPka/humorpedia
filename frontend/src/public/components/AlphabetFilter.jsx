import { cn } from '@/lib/utils';

export const RUSSIAN_ALPHABET = 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'.split('');
export const OTHER_ALPHABET_FILTER = 'other';

export default function AlphabetFilter({ selectedLetter, onLetterClick, availableLetters = null }) {
  const hasAvailability = Array.isArray(availableLetters);
  const visibleLetters = hasAvailability
    ? RUSSIAN_ALPHABET.filter((letter) => availableLetters.includes(letter))
    : RUSSIAN_ALPHABET;
  const showOther = !hasAvailability || availableLetters.includes(OTHER_ALPHABET_FILTER);

  return (
    <div className="flex flex-wrap gap-1" aria-label="Фильтр по первой букве">
      {visibleLetters.map((letter) => (
        <button
          key={letter}
          type="button"
          aria-pressed={selectedLetter === letter}
          onClick={() => onLetterClick(selectedLetter === letter ? '' : letter)}
          className={cn(
            'min-w-11 min-h-11 text-sm font-medium rounded transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600',
            selectedLetter === letter
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
          )}
        >
          {letter}
        </button>
      ))}
      {showOther && (
        <button
          type="button"
          aria-label="Латиница, цифры и символы"
          aria-pressed={selectedLetter === OTHER_ALPHABET_FILTER}
          onClick={() => onLetterClick(
            selectedLetter === OTHER_ALPHABET_FILTER ? '' : OTHER_ALPHABET_FILTER
          )}
          className={cn(
            'px-2 min-h-11 text-sm font-medium rounded transition-colors whitespace-nowrap focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600',
            selectedLetter === OTHER_ALPHABET_FILTER
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
          )}
        >
          A–Z 0–9 #
        </button>
      )}
      {selectedLetter && (
        <button
          type="button"
          onClick={() => onLetterClick('')}
          className="px-3 min-h-11 text-sm font-medium rounded bg-red-100 text-red-600 hover:bg-red-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
        >
          Сбросить
        </button>
      )}
    </div>
  );
}
