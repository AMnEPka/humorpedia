import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Clapperboard } from 'lucide-react';
import { publicApi } from '../utils/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function ShowAppearances({ personId }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    let active = true;
    setItems([]);
    if (!personId) return undefined;
    const request = publicApi.getPersonShows(personId);
    request.then(({ data }) => { if (active) setItems(data.items || []); }).catch(() => {});
    return () => { active = false; };
  }, [personId]);
  if (!items.length) return null;
  return <ShowAppearancesCard items={items} />;
}

export function ShowAppearancesCard({ items }) {
  return (
    <Card id="section-shows" className="scroll-mt-20">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clapperboard className="h-5 w-5 text-blue-600" /> Участие в других проектах
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {items.map(item => (
            <li key={item.id}>
              <Link to={item.link_url || item.show_url} className="text-blue-700 hover:underline">{item.caption}</Link>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
