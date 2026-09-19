import { Link } from 'react-router-dom';
import { Clapperboard } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export const TEAM_PROJECTS_TITLE = 'Участие членов команды в других проектах';

const LEGACY_PROJECT_TITLES = [
  'сторонние проекты команды после/во время игры в квн',
  'сторонние проекты команды после или во время игры в квн',
  TEAM_PROJECTS_TITLE.toLowerCase(),
];

export function isTeamProjectsModule(module) {
  if (module?.type !== 'text_block') return false;
  const title = String(module.data?.title || '').trim().toLowerCase().replace(/\s+/g, ' ');
  return LEGACY_PROJECT_TITLES.includes(title);
}

export function hasManualTeamProjects(modules = []) {
  return modules.some((module) => String(module.data?.content || '').trim());
}

export function isProjectTeamUrl(project, member) {
  return Boolean(
    member.appearance_url
    && member.appearance_url.startsWith(`${project.show_url.replace(/\/$/, '')}/teams/`)
  );
}

export function projectMemberCaption(member) {
  const value = String(member.caption || '');
  const match = /^(Участник|Финалист|Победитель) проекта «[^»]+»(.*)$/.exec(value);
  return match ? `${match[1].toLowerCase()}${match[2]}` : value;
}

export default function TeamProjects({ items = [], manualModules = [] }) {
  const manual = manualModules.filter((module) => String(module.data?.content || '').trim());
  if (!items.length && !manual.length) return null;

  return (
    <Card id="section-team-projects" className="scroll-mt-20">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clapperboard className="h-5 w-5 text-blue-600" /> {TEAM_PROJECTS_TITLE}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {items.length > 0 && (
          <div>
            {manual.length > 0 && (
              <h3 className="mb-3 text-sm font-semibold text-gray-500">По составу команды</h3>
            )}
            <ul className="space-y-4">
              {items.map((project) => (
                <li key={project.show_id}>
                  <Link to={project.show_url} className="font-semibold text-blue-700 hover:underline">
                    {project.show_title}
                  </Link>
                  <ul className="mt-1.5 space-y-1 pl-4 text-sm text-gray-700">
                    {project.members.map((member) => (
                      <li key={member.person_id}>
                        <Link to={member.person_url} className="text-blue-700 hover:underline">
                          {member.person_name}
                        </Link>
                        {member.caption && <span> — {projectMemberCaption(member)}</span>}
                        {isProjectTeamUrl(project, member) && (
                          <>
                            {' '}
                            <Link to={member.appearance_url} className="whitespace-nowrap text-blue-700 hover:underline">
                              к составу проекта
                            </Link>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </div>
        )}

        {manual.length > 0 && (
          <div className={items.length > 0 ? 'border-t pt-4' : ''}>
            {items.length > 0 && (
              <h3 className="mb-3 text-sm font-semibold text-gray-500">Дополнительная информация</h3>
            )}
            <div className="space-y-4">
              {manual.map((module) => (
                <div
                  key={module.id}
                  className="prose prose-blue max-w-none overflow-x-auto break-words"
                  dangerouslySetInnerHTML={{ __html: module.data?.content || '' }}
                />
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
