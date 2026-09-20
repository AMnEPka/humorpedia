import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { CheckCircle2, Loader2, PencilLine } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { publicApi } from '../utils/api';

const SECTIONS = [
  'Заголовок / название',
  'Фото / изображение',
  'Основная информация',
  'Биография / основной текст',
  'Личная жизнь',
  'Факты / таблица',
  'Состав / участники',
  'Турниры / проекты',
  'Ссылки',
  'Другое',
];

const emptyForm = {
  section: '',
  message: '',
  source: '',
  email: '',
  website: '',
};

export default function CorrectionSuggestionButton() {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [ticketId, setTicketId] = useState('');

  const reset = () => {
    setForm(emptyForm);
    setError('');
    setTicketId('');
    setSubmitting(false);
  };

  const handleOpenChange = (nextOpen) => {
    setOpen(nextOpen);
    if (!nextOpen) reset();
  };

  const setField = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    if (!form.section) {
      setError('Выберите раздел страницы');
      return;
    }
    if (form.message.trim().length < 3) {
      setError('Опишите исправление подробнее');
      return;
    }

    setSubmitting(true);
    try {
      const heading = document.querySelector('h1')?.textContent?.trim();
      const response = await publicApi.createCorrectionSuggestion({
        page_title: heading || document.title || location.pathname,
        page_path: `${location.pathname}${location.search}`,
        section: form.section,
        message: form.message.trim(),
        source: form.source.trim() || null,
        email: form.email.trim() || null,
        website: form.website,
      });
      setTicketId(response.data.id || '');
    } catch (requestError) {
      const detail = requestError.response?.data?.detail;
      setError(
        typeof detail === 'string'
          ? detail
          : 'Не удалось отправить предложение. Попробуйте ещё раз.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <Button
        type="button"
        className="fixed bottom-4 right-4 z-40 rounded-full shadow-lg sm:bottom-6 sm:right-6"
        onClick={() => setOpen(true)}
        aria-label="Предложить исправление"
      >
        <PencilLine className="mr-2 h-4 w-4" />
        Предложить исправление
      </Button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-xl">
          {ticketId ? (
            <div className="py-8 text-center" aria-live="polite">
              <CheckCircle2 className="mx-auto mb-4 h-12 w-12 text-green-600" />
              <DialogTitle className="text-xl">Предложение отправлено</DialogTitle>
              <DialogDescription className="mt-3">
                Редакция проверит информацию. Изменения не публикуются автоматически.
              </DialogDescription>
              <p className="mt-4 text-sm text-muted-foreground">
                Номер обращения: <span className="font-mono">{ticketId}</span>
              </p>
              <Button className="mt-6" onClick={() => handleOpenChange(false)}>Закрыть</Button>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-5">
              <DialogHeader>
                <DialogTitle>Предложить исправление</DialogTitle>
                <DialogDescription>
                  Укажите раздел и опишите, что нужно исправить. Предложение сначала проверит редакция.
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-2">
                <Label>Страница</Label>
                <div className="rounded-md bg-muted px-3 py-2 text-sm">
                  {document.querySelector('h1')?.textContent?.trim() || document.title || location.pathname}
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="correction-section">Раздел страницы</Label>
                <Select value={form.section} onValueChange={(value) => setField('section', value)}>
                  <SelectTrigger id="correction-section">
                    <SelectValue placeholder="Выберите раздел" />
                  </SelectTrigger>
                  <SelectContent>
                    {SECTIONS.map((section) => (
                      <SelectItem key={section} value={section}>{section}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="correction-message">Предлагаемое исправление</Label>
                <Textarea
                  id="correction-message"
                  value={form.message}
                  onChange={(event) => setField('message', event.target.value)}
                  rows={7}
                  maxLength={5000}
                  placeholder="Напишите, что сейчас указано неверно и как должно быть"
                  required
                />
                <p className="text-right text-xs text-muted-foreground">{form.message.length} / 5000</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="correction-source">Источник информации — необязательно</Label>
                <Input
                  id="correction-source"
                  value={form.source}
                  onChange={(event) => setField('source', event.target.value)}
                  maxLength={1000}
                  placeholder="Ссылка или краткое пояснение"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="correction-email">Email для ответа — необязательно</Label>
                <Input
                  id="correction-email"
                  type="email"
                  value={form.email}
                  onChange={(event) => setField('email', event.target.value)}
                  placeholder="name@example.com"
                />
                <p className="text-xs text-muted-foreground">
                  Используем только для ответа по этому обращению.
                </p>
              </div>

              <div className="hidden" aria-hidden="true">
                <Label htmlFor="correction-website">Сайт</Label>
                <Input
                  id="correction-website"
                  tabIndex={-1}
                  autoComplete="off"
                  value={form.website}
                  onChange={(event) => setField('website', event.target.value)}
                />
              </div>

              {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
                  Отмена
                </Button>
                <Button type="submit" disabled={submitting}>
                  {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Отправить предложение
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
