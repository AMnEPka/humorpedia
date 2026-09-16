# Фронтенд Humorpedia (`frontend/`)

React 19, Create React App через **CRACO** (`craco start|build`), React Router 7, Tailwind 3 + shadcn/ui (`src/components/ui`, конфиг `components.json`), иконки lucide-react, тосты sonner.
Импорт через алиас `@/` = `src/`. Пакеты — **yarn** (`yarn.lock`). Тестов нет.

## Структура `src/`

```
index.js / index.css / App.css
App.js                         BrowserRouter → AuthProvider → ScrollRestoration → AppRoutes (все маршруты)
lib/utils.js                   cn() (clsx + tailwind-merge)
hooks/use-toast.js             shadcn toast
utils/
  pageTitle.js                 usePageTitle / buildPageTitle (обёртка <WithTitle> в App.js)
  number.js                    formatDecimalTrim, roundTo (баллы КВН)
  team.js                      cleanTeamName
components/
  ui/*                         shadcn/ui (Radix) — генерированные, не трогать без нужды
  SystemModules.jsx            рендер системных модулей сайдбара: PosterPhoto, FactsTable (addAgeToDate — возраст по дате), TagsCloud, SocialLinks, RatingWidget; isSystemModule(), renderSystemModule()
  EmojiRating.jsx              виджет оценки эмодзи
public/                        ПУБЛИЧНЫЙ САЙТ
  utils/api.js                 publicApi — axios без авторизации (news, articles, people, teams, shows, quizzes, sections, kvn, cities, search, stats)
  utils/sanitize.js            sanitizeHTML (DOMPurify), containsHTML
  utils/teamStorage.js         localStorage-хранилище данных команд (ключ humorpedia_teams, обновление раз в 24 ч)
  components/
    Layout.jsx                 Header + <Outlet/> + Footer
    Header.jsx                 меню из /sections (in_main_menu), автокомплит поиска
    Footer.jsx
    ModuleRenderer.jsx         рендер контентных модулей (text_block, image, image_gallery, video_embed, quote, timeline, person_card, related_links, table_of_contents, table, html, divider, humor_chronicles)
    StageSection.jsx, GameTable.jsx   стадии и таблицы игр сезона КВН (из season_data)
    LeagueSeasonsNav.jsx       навигация по сезонам лиги
    ArticleCard.jsx, NewsCard.jsx, MultiSelectWithSearch.jsx
  pages/
    HomePage.jsx               новости, популярные/случайная статья
    SectionDetailPage.jsx      CATCH-ALL `/*`: kvn/by-path → sections/path → redirects/lookup; при season_data отдаёт SeasonDetailPage; таблицы чемпионов лиг
    SeasonDetailPage.jsx       страница сезона КВН (стадии, игры, победители, жюри, prev/next)
    JuryStatsPage.jsx          статистика жюри Высшей лиги
    TeamDetailPage.jsx / TeamsListPage.jsx      команды КВН
    PersonDetailPage.jsx / PeopleListPage.jsx
    ShowDetailPage.jsx / ShowsListPage.jsx      шоу до 4 уровней вложенности
    ArticleDetailPage / ArticlesListPage, NewsDetailPage / NewsListPage, QuizDetailPage / QuizzesListPage
    CityDetailPage / CitiesListPage             география
    SearchPage, TagSearchPage, ContactsPage, PolicyPage
    RedirectHandler.jsx        НЕ используется (нигде не импортируется)
admin/                         АДМИНКА
  hooks/useAuth.js             AuthProvider/useAuth: user из localStorage (admin_user), проверка /auth/me, тихий refresh каждые 6 ч; токен удаляется только при 401/403
  utils/api.js                 axios `api` с Bearer из localStorage.admin_token и refresh-интерсептором (очередь запросов на время refresh);
                               группы: authApi, contentApi, statsApi, usersApi, tagsApi, commentsApi, mediaApi, templatesApi, sectionsApi; getErrorMessage()
  components/
    AdminLayout.jsx            сайдбар навигации (пункты «Пользователи» и «База данных» — adminOnly)
    ModuleEditor.jsx           конструктор модулей страницы (dnd-kit), 1104 строки
    SeasonDataEditor.jsx       редактор season_data: стадии/игры/команды/баллы/конкурсы, копирование, dnd — 2665 строк, самый сложный компонент
    RichTextEditor.jsx         TipTap (таблицы, цвета, выравнивание) + LinkInserter
    LinkInserter.jsx           поиск контента и вставка внутренней ссылки (/content/search-for-links)
    MediaSelector.jsx          выбор/загрузка медиа (uploads и volume-папки)
    TeamSelector.jsx, GameTeamSelector.jsx, PersonSelector.jsx, TagSelector.jsx, FactsEditor.jsx
  pages/                       *ListPage + *EditPage для: people, teams, shows, kvn, articles, news, quizzes, wiki, cities, sections, templates;
                               DashboardPage, LoginPage, MediaPage, TagsPage, CommentsPage, UsersPage, MongoAdminPage (сырой доступ к коллекциям)
```

## Маршруты (App.js)

Публичные (внутри `PublicLayout`):
| Путь | Страница |
|---|---|
| `/` | HomePage |
| `/news`, `/news/:slug` | NewsListPage, NewsDetailPage |
| `/articles`, `/articles/:slug` | ArticlesListPage, ArticleDetailPage |
| `/people`, `/people/:slug` | PeopleListPage, PersonDetailPage |
| `/teams`, `/teams/:category` | редирект на `/kvn/teams` |
| `/kvn/teams`, `/kvn/teams/:slug` | TeamsListPage, TeamDetailPage |
| `/shows[/:parentSlug[/:childSlug[/:grandchildSlug[/:greatGrandchildSlug]]]]` | ShowsListPage / ShowDetailPage |
| `/quizzes`, `/quizzes/:slug` | QuizzesListPage, QuizDetailPage |
| `/city`, `/city/:slug` | CitiesListPage, CityDetailPage |
| `/contacts`, `/policy`, `/search`, `/tags/:tag` | статические / поиск |
| `/kvn/vl-kvn/vl-jury` | JuryStatsPage |
| `/*` | **SectionDetailPage** (КВН, разделы, редиректы старых URL) |

Админка (`ProtectedRoute` — проверяет только, что пользователь залогинен, роль не проверяет; внутри `AdminLayout`):
`/admin/login`, `/admin`, `/admin/{people|teams|shows|kvn|articles|news|quizzes|wiki|cities|sections|templates}` и `/:id` (id = `new` для создания), `/admin/media`, `/admin/tags`, `/admin/comments`, `/admin/users`, `/admin/database`.

HomePage, SectionDetailPage и PublicLayout грузятся синхронно; остальное — `React.lazy`, админка — отдельным чанком.

## Как фронт находит бэкенд

`API_BASE` (в обоих api.js):
1. `REACT_APP_USE_API_PROXY=true` → `/api` (dev в Docker, прокси CRA → `http://backend:8001`);
2. иначе `window.__BACKEND_URL__` (ставит `public/config.js` для localhost) → `REACT_APP_BACKEND_URL` → `${protocol}//${hostname}:8001`.

Картинки: `/media/imported/...`, `/images/...`, `/uploads/...` — отдаёт бэкенд (в dev — через прокси CRA).
`SectionDetailPage` делает `fetch(\`${BACKEND_URL}/api/redirects/lookup\`)` напрямую, минуя `API_BASE`.

## Конвенции

- Все тексты интерфейса на русском.
- HTML из БД выводить только через `sanitizeHTML` (DOMPurify).
- Заголовок вкладки — через `<WithTitle title="...">` в App.js или `usePageTitle`.
- В Docker hot reload отключён (`DOCKER_ENV=true`) — после правок обновлять страницу вручную; для HMR запускать фронт локально (`yarn start` в `frontend/`, бэкенд на :8001).
- `plugins/visual-edits` и `plugins/health-check` — наследие Emergent; health-check включается `ENABLE_HEALTH_CHECK=true`.
