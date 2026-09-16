import { useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

/**
 * Свёрнутый по умолчанию блок («под катом»).
 * - содержимое монтируется при первом раскрытии (в блоке могут быть сотни таблиц);
 * - у раскрытого блока заголовок прилипает под шапкой сайта, а внизу есть кнопка «Свернуть» —
 *   чтобы длинный блок можно было закрыть, не пролистывая его обратно к началу.
 */
export default function CollapsibleCard({ title, children }) {
  const detailsRef = useRef(null);
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);

  const handleToggle = (e) => {
    const isOpen = e.currentTarget.open;
    setOpen(isOpen);
    if (isOpen) setMounted(true);
  };

  const collapse = (e) => {
    e?.preventDefault();
    const details = detailsRef.current;
    if (!details) return;
    const wasBelowTop = details.getBoundingClientRect().top < 0;
    details.open = false;
    // если начало блока ушло за верх экрана — вернуть читателя к заголовку свернутого блока
    if (wasBelowTop) details.scrollIntoView({ block: 'start' });
  };

  return (
    <Card>
      <details ref={detailsRef} onToggle={handleToggle} className="scroll-mt-20">
        <summary
          className={`flex items-center justify-between gap-3 cursor-pointer select-none px-6 py-4 text-lg font-semibold hover:text-blue-600 list-none [&::-webkit-details-marker]:hidden ${
            open ? 'sticky top-16 z-10 bg-white border-b rounded-t-xl' : ''
          }`}
        >
          <span className="min-w-0">{title || 'Подробнее'}</span>
          <span className="flex items-center gap-1 text-sm font-normal text-gray-500 flex-shrink-0">
            {open ? 'Свернуть' : 'Развернуть'}
            <ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
          </span>
        </summary>
        {mounted && (
          <CardContent className="pt-4">
            {children}
            <div className="mt-4 flex justify-center">
              <button
                type="button"
                onClick={collapse}
                className="inline-flex items-center gap-1 text-sm text-gray-600 hover:text-blue-600 border rounded-md px-3 py-1.5"
              >
                Свернуть «{title || 'блок'}»
                <ChevronDown className="h-4 w-4 rotate-180" />
              </button>
            </div>
          </CardContent>
        )}
      </details>
    </Card>
  );
}
