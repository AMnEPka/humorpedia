import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { moduleNames } from '@/moduleContract';

export default function SeasonModulesArchive({ modules = [] }) {
  return <Card>
    <CardHeader><CardTitle>Архивные модули сезона</CardTitle></CardHeader>
    <CardContent className="space-y-4">
      <Alert><AlertDescription>
        Страница сезона строится только из данных вкладки «Сезон». Старые модули сохранены для истории,
        публично не отображаются и здесь не редактируются, чтобы не дублировать результаты и описания.
      </AlertDescription></Alert>
      {modules.length > 0 ? <ul className="space-y-2">
        {modules.map((module, index) => <li key={module.id || index} className="rounded border px-3 py-2 text-sm">
          {module.title || module.data?.title || moduleNames[module.type] || module.type}
          <span className="ml-2 text-muted-foreground">({module.type})</span>
        </li>)}
      </ul> : <p className="text-sm text-muted-foreground">Архивных модулей нет.</p>}
    </CardContent>
  </Card>;
}
