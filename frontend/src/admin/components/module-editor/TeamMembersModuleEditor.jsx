import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Trash2, Plus } from 'lucide-react';


export default function TeamMembersModuleEditor({ data, updateData }) {
  const members = data.members || [];
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Заголовок</Label>
        <Input
          value={data.title || ''}
          onChange={(e) => updateData({ ...data, title: e.target.value })}
          placeholder="Состав команды"
        />
      </div>
      <div className="space-y-3">
        {members.map((member, index) => (
          <div key={index} className="border rounded-lg p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Участник {index + 1}</span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => updateData({ ...data, members: members.filter((_, i) => i !== index) })}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
            <Input
              value={member.name || ''}
              onChange={(e) => {
                const newMembers = [...members];
                newMembers[index] = { ...newMembers[index], name: e.target.value };
                updateData({ ...data, members: newMembers });
              }}
              placeholder="Имя"
            />
            <Input
              value={member.role || ''}
              onChange={(e) => {
                const newMembers = [...members];
                newMembers[index] = { ...newMembers[index], role: e.target.value };
                updateData({ ...data, members: newMembers });
              }}
              placeholder="Роль в команде"
            />
          </div>
        ))}
      </div>
      <Button
        type="button"
        variant="outline"
        onClick={() => updateData({
          ...data,
          members: [...members, { name: '', role: '' }]
        })}
        className="w-full"
      >
        <Plus className="mr-2 h-4 w-4" /> Добавить участника
      </Button>
    </div>
  );
}
