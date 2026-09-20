import { Link } from 'react-router-dom';
import { Users } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { personHref, yearsLabel } from './labels';

// Структурированный состав команды (memberships). Заменяет текстовый блок, если тот разобран полностью.
export default function TeamRoster({ members, title = 'Состав команды', anchorId }) {
  const current = members?.current || [];
  const former = members?.former || [];
  if (current.length === 0 && former.length === 0) return null;

  return (
    <Card id={anchorId} className="scroll-mt-20">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="h-5 w-5 text-blue-600" /> {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {current.length > 0 && <MemberList members={current} />}
        {former.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-500 mb-2">Бывшие участники</h3>
            <MemberList members={former} muted />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MemberList({ members, muted = false }) {
  return (
    <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-1.5">
      {members.map((member) => {
        const href = personHref(member.person);
        const years = yearsLabel(member);
        const details = [member.roles?.join(', '), years].filter(Boolean).join(' · ');
        return (
          <li key={member._id} className="text-sm leading-snug">
            {href ? (
              <Link to={href} className="text-blue-700 hover:underline">
                {member.person?.name || member.person_name}
              </Link>
            ) : (
              <span className={muted ? 'text-gray-600' : 'text-gray-900'}>{member.person_name}</span>
            )}
            {details && <span className="text-gray-500"> — {details}</span>}
          </li>
        );
      })}
    </ul>
  );
}
