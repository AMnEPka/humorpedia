import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { useState, useCallback } from 'react';
import { moduleNames } from '@/moduleContract';
import { createModuleDraft, updateModuleData } from './operations';
import ModuleFieldsEditor from './ModuleFieldsEditor';
export default function ModuleEditDialog({ module, open, onClose, onSave }) {
  const [localModule, setLocalModule] = useState(() => createModuleDraft(module));

  const handleSave = useCallback(() => {
    if (localModule) {
      onSave(localModule);
    }
    onClose();
  }, [localModule, onSave, onClose]);

  const updateLocalModule = useCallback((updates) => {
    setLocalModule(prev => prev ? { ...prev, ...updates } : null);
  }, []);

  const updateData = useCallback((newData) => {
    setLocalModule(prev => updateModuleData(prev, newData));
  }, []);

  if (!localModule) return null;

  const data = localModule.data || {};


  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleSave()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            Редактирование: {moduleNames[localModule.type]}
          </DialogTitle>
        </DialogHeader>
        <div className="py-4">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Название блока (опционально)</Label>
              <Input
                value={localModule.title || ''}
                onChange={(e) => updateLocalModule({ title: e.target.value })}
                placeholder={moduleNames[localModule.type]}
              />
            </div>
            <div className="flex items-center gap-2">
              <Switch id="module-visible" checked={localModule.visible !== false}
                onCheckedChange={visible => updateLocalModule({ visible })} />
              <Label htmlFor="module-visible">Показывать модуль</Label>
            </div>
            <ModuleFieldsEditor type={localModule.type} data={data} updateData={updateData} />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={handleSave}>Сохранить</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
