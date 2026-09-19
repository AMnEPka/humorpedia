import { useCallback, useEffect, useState } from 'react';
import { Loader2, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { getErrorMessage, recommendationSettingsApi } from '../utils/api';

export const RESULT_TYPES = [
  ['article', 'Статьи'],
  ['person', 'Люди'],
  ['kvn_team', 'Команды КВН'],
  ['show_team', 'Команды шоу'],
  ['show', 'Шоу'],
  ['city', 'Города'],
  ['kvn', 'Страницы КВН'],
  ['quiz', 'Квизы'],
  ['news', 'Новости'],
];

export const TARGETS = [
  ['articles', 'Статьи'],
  ['news', 'Новости'],
  ['people', 'Люди'],
  ['kvn_teams', 'Команды КВН'],
  ['show_teams', 'Команды шоу'],
  ['shows', 'Шоу'],
  ['cities', 'Города'],
  ['kvn', 'Страницы КВН'],
];

export const DEFAULT_SETTINGS = {
  enabled: true,
  max_items: 3,
  result_types: RESULT_TYPES.filter(([key]) => key !== 'news').map(([key]) => key),
  apply_to: Object.fromEntries(TARGETS.map(([key]) => [key, true])),
};

export function normalizeSettings(value) {
  return {
    ...DEFAULT_SETTINGS,
    ...value,
    result_types: Array.isArray(value?.result_types) ? value.result_types : DEFAULT_SETTINGS.result_types,
    apply_to: { ...DEFAULT_SETTINGS.apply_to, ...(value?.apply_to || {}) },
  };
}

export default function RelatedContentSettingsPage() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setMessage(null);
    try {
      const response = await recommendationSettingsApi.get();
      setSettings(normalizeSettings(response.data));
    } catch (error) {
      setMessage({
        type: 'error',
        text: getErrorMessage(error, 'Не удалось загрузить настройки блока «Читайте также»'),
        retryLoad: true,
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const updateTarget = (key, checked) => {
    setSettings((current) => ({
      ...current,
      apply_to: { ...current.apply_to, [key]: checked },
    }));
  };

  const updateResultType = (key, checked) => {
    setSettings((current) => ({
      ...current,
      result_types: checked
        ? [...current.result_types, key]
        : current.result_types.filter((item) => item !== key),
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setMessage(null);
    if (settings.max_items < 1 || settings.max_items > 12) {
      setMessage({ type: 'error', text: 'Количество карточек должно быть от 1 до 12.' });
      return;
    }
    if (settings.result_types.length === 0) {
      setMessage({ type: 'error', text: 'Выберите хотя бы один тип рекомендуемых страниц.' });
      return;
    }

    setSaving(true);
    try {
      const response = await recommendationSettingsApi.update(settings);
      setSettings(normalizeSettings(response.data || settings));
      setMessage({ type: 'success', text: 'Настройки блока «Читайте также» сохранены.' });
    } catch (error) {
      setMessage({ type: 'error', text: getErrorMessage(error, 'Не удалось сохранить настройки') });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center" aria-label="Загрузка настроек">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Читайте также</h1>
        <p className="mt-1 text-muted-foreground">
          Общие правила автоматических рекомендаций на публичных страницах сайта.
        </p>
      </div>

      {message && (
        <div
          role={message.type === 'error' ? 'alert' : 'status'}
          className={`rounded-md border px-4 py-3 text-sm ${message.type === 'error'
            ? 'border-red-200 bg-red-50 text-red-800'
            : 'border-green-200 bg-green-50 text-green-800'}`}
        >
          {message.text}
          {message.retryLoad && (
            <Button type="button" variant="link" className="ml-2 h-auto p-0" onClick={loadSettings}>
              Повторить
            </Button>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Общие настройки</CardTitle>
            <CardDescription>
              Если тип «Статьи» включён, ручные связанные статьи сохраняют свой порядок. Затем добавляются связанные страницы,
              которых ещё нет на странице, и одна случайная находка; автоматическая часть меняется раз в сутки.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
              <div>
                <Label htmlFor="recommendations-enabled">Показывать блок «Читайте также»</Label>
                <p className="mt-1 text-sm text-muted-foreground">Глобально включает или скрывает блок на сайте.</p>
              </div>
              <Switch
                id="recommendations-enabled"
                checked={settings.enabled}
                onCheckedChange={(enabled) => setSettings((current) => ({ ...current, enabled }))}
              />
            </div>

            <div className="max-w-xs space-y-2">
              <Label htmlFor="recommendations-max-items">Карточек в блоке</Label>
              <Input
                id="recommendations-max-items"
                type="number"
                min="1"
                max="12"
                value={settings.max_items}
                onChange={(event) => setSettings((current) => ({ ...current, max_items: Number(event.target.value) }))}
                required
              />
              <p className="text-xs text-muted-foreground">От 1 до 12. По умолчанию — 3 карточки.</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Что рекомендовать</CardTitle>
            <CardDescription>
              Выбранные типы участвуют в автоматическом подборе. Новости выключены по умолчанию, поскольку для них есть отдельный блок.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {RESULT_TYPES.map(([key, label]) => (
              <div key={key} className="flex items-center justify-between gap-4 rounded-lg border p-4">
                <Label htmlFor={`recommendations-result-${key}`}>{label}</Label>
                <Switch
                  id={`recommendations-result-${key}`}
                  checked={settings.result_types.includes(key)}
                  onCheckedChange={(checked) => updateResultType(key, checked)}
                />
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Где показывать</CardTitle>
            <CardDescription>Команды КВН и команды шоу настраиваются независимо.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {TARGETS.map(([key, label]) => (
              <div key={key} className="flex items-center justify-between gap-4 rounded-lg border p-4">
                <Label htmlFor={`recommendations-target-${key}`}>{label}</Label>
                <Switch
                  id={`recommendations-target-${key}`}
                  checked={settings.apply_to[key]}
                  onCheckedChange={(checked) => updateTarget(key, checked)}
                />
              </div>
            ))}
          </CardContent>
        </Card>

        <Button type="submit" disabled={saving}>
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          {saving ? 'Сохранение…' : 'Сохранить настройки'}
        </Button>
      </form>
    </div>
  );
}
