import { useCallback, useEffect, useState } from 'react';
import { Loader2, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { getErrorMessage, relatedNewsSettingsApi } from '../utils/api';

const DEFAULT_SETTINGS = {
  enabled: true,
  freshness_days: 183,
  max_items: 3,
  apply_to: {
    people: true,
    kvn_teams: true,
    show_teams: true,
    shows: true,
  },
};

const TARGETS = [
  ['people', 'Люди'],
  ['kvn_teams', 'Команды КВН'],
  ['show_teams', 'Команды шоу'],
  ['shows', 'Шоу'],
];

function normalizeSettings(value) {
  return {
    ...DEFAULT_SETTINGS,
    ...value,
    apply_to: { ...DEFAULT_SETTINGS.apply_to, ...(value?.apply_to || {}) },
  };
}

export default function RelatedNewsSettingsPage() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setMessage(null);
    try {
      const response = await relatedNewsSettingsApi.get();
      setSettings(normalizeSettings(response.data));
    } catch (error) {
      setMessage({
        type: 'error',
        text: getErrorMessage(error, 'Не удалось загрузить настройки свежих новостей'),
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

  const handleSubmit = async (event) => {
    event.preventDefault();
    setMessage(null);

    if (settings.freshness_days < 1 || settings.freshness_days > 3650) {
      setMessage({ type: 'error', text: 'Период свежести должен быть от 1 до 3650 дней.' });
      return;
    }
    if (settings.max_items < 1 || settings.max_items > 3) {
      setMessage({ type: 'error', text: 'Количество новостей должно быть от 1 до 3.' });
      return;
    }

    setSaving(true);
    try {
      const response = await relatedNewsSettingsApi.update(settings);
      setSettings(normalizeSettings(response.data || settings));
      setMessage({ type: 'success', text: 'Настройки свежих новостей сохранены.' });
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
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Свежие новости</h1>
        <p className="mt-1 text-muted-foreground">Настройка блока новостей на страницах людей, команд и шоу.</p>
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
            <CardTitle>Публикация блока</CardTitle>
            <CardDescription>Блок выводится только когда он включён и для страницы найдены свежие новости.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
              <div>
                <Label htmlFor="related-news-enabled">Показывать свежие новости</Label>
                <p className="mt-1 text-sm text-muted-foreground">Глобально включает блок на публичном сайте.</p>
              </div>
              <Switch
                id="related-news-enabled"
                checked={settings.enabled}
                onCheckedChange={(checked) => setSettings((current) => ({ ...current, enabled: checked }))}
              />
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="freshness-days">Период свежести, дней</Label>
                <Input
                  id="freshness-days"
                  type="number"
                  min="1"
                  max="3650"
                  value={settings.freshness_days}
                  onChange={(event) => setSettings((current) => ({ ...current, freshness_days: Number(event.target.value) }))}
                  required
                />
                <p className="text-xs text-muted-foreground">От 1 до 3650. По умолчанию — 183 дня.</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="max-items">Новостей в блоке</Label>
                <Input
                  id="max-items"
                  type="number"
                  min="1"
                  max="3"
                  value={settings.max_items}
                  onChange={(event) => setSettings((current) => ({ ...current, max_items: Number(event.target.value) }))}
                  required
                />
                <p className="text-xs text-muted-foreground">От 1 до 3. По умолчанию — 3 новости.</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Где показывать</CardTitle>
            <CardDescription>Команды КВН и команды шоу настраиваются независимо.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {TARGETS.map(([key, label]) => (
              <div key={key} className="flex items-center justify-between gap-4 rounded-lg border p-4">
                <Label htmlFor={`related-news-${key}`}>{label}</Label>
                <Switch
                  id={`related-news-${key}`}
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
