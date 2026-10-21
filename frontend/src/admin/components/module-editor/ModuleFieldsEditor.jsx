import { Alert, AlertDescription } from '@/components/ui/alert';

import ModuleDataFields from '../ModuleDataFields';
import PollModuleEditor from './PollModuleEditor';
import ParticipantsModuleEditor from './ParticipantsModuleEditor';
import TextModuleEditor from './TextModuleEditor';
import TimelineModuleEditor from './TimelineModuleEditor';
import HeroModuleEditor from './HeroModuleEditor';
import GalleryModuleEditor from './GalleryModuleEditor';
import VideoModuleEditor from './VideoModuleEditor';
import QuoteModuleEditor from './QuoteModuleEditor';
import TeamMembersModuleEditor from './TeamMembersModuleEditor';
import TableModuleEditor from './TableModuleEditor';

export default function ModuleFieldsEditor({ type, data, updateData }) {
  switch (type) {
    case 'participants': return <ParticipantsModuleEditor data={data} updateData={updateData} />;
    case 'poll':
      return <PollModuleEditor data={data} updateData={updateData} />;

    case 'text_block': return <TextModuleEditor data={data} updateData={updateData} />;
    case 'timeline': return <TimelineModuleEditor data={data} updateData={updateData} />;
    case 'hero_card': return <HeroModuleEditor data={data} updateData={updateData} />;
    case 'gallery': return <GalleryModuleEditor data={data} updateData={updateData} />;
    case 'video': return <VideoModuleEditor data={data} updateData={updateData} />;
    case 'quote': return <QuoteModuleEditor data={data} updateData={updateData} />;
    case 'team_members': return <TeamMembersModuleEditor data={data} updateData={updateData} />;
    case 'table_of_contents':
      return <Alert><AlertDescription>
        Маркер оглавления. Сейчас оглавление формируется шаблоном страницы там, где оно предусмотрено.
        Сохранённые настройки режима и позиции не управляли отображением и остаются в данных для совместимости.
      </AlertDescription></Alert>;
    case 'table': return <TableModuleEditor data={data} updateData={updateData} />;
    case 'poster_photo':
    case 'facts_table':
    case 'rating_widget':
    case 'tags_cloud':
    case 'social_links':
      return <Alert><AlertDescription>
        Системный блок использует основные поля страницы: фото, факты, рейтинг, теги или социальные ссылки.
        Редактируйте эти данные в соответствующих разделах карточки. Расположение и оформление задаёт шаблон страницы.
        Сохранённые дополнительные настройки остаются в данных для совместимости.
      </AlertDescription></Alert>;
    case 'first_league_champions':
      return (
        <div className="space-y-4">
          <Alert>
            <AlertDescription>
              Таблица чемпионов строится автоматически по данным дочерних сезонов Первой лиги.
              Порядок блока можно менять перетаскиванием в списке модулей. Заголовок блока можно задать ниже.
            </AlertDescription>
          </Alert>
        </div>
      );

    case 'vl_league_champions':
      return (
        <div className="space-y-4">
          <Alert>
            <AlertDescription>
              Таблица чемпионов строится автоматически по данным дочерних сезонов Высшей лиги.
              Порядок блока можно менять перетаскиванием в списке модулей. Заголовок блока можно задать ниже.
            </AlertDescription>
          </Alert>
        </div>
      );

    default:
      return <ModuleDataFields type={type} data={data} onChange={updateData} />;
  }
}
