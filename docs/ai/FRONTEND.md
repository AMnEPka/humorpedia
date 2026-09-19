# Фронтенд Humorpedia (`frontend/`)

React 19, Create React App через **CRACO** (`craco start|build`), React Router 7, Tailwind 3 + shadcn/ui (`src/components/ui`, конфиг `components.json`), иконки lucide-react, тосты sonner.
Импорт через алиас `@/` = `src/`. Пакеты — **yarn** (`yarn.lock`). Тесты: `yarn test --watchAll=false --runInBand`
(Jest/React DOM, также job frontend в CI). Контракт модулей, форматы и специальные владельцы — [MODULE_CONTRACT.md](MODULE_CONTRACT.md).

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
  media.js                     URL медиа, personPhotoUrl/teamLogoUrl/contentImageUrl, стабильный выбор одной из 4 фирменных заглушек, orderedFacts
  search.js                    normalizeSearchText: единая нормализация локальных фильтров, включая эквивалентность е/ё
  (public/components/ContentTable.jsx — таблица модуля `table`: пояснение, сортировка по столбцам)
components/
  ui/*                         shadcn/ui (Radix) — генерированные, не трогать без нужды
  SystemModules.jsx            рендер системных модулей сайдбара: PosterPhoto, FactsTable (addAgeToDate — возраст по дате), TagsCloud, SocialLinks, RatingWidget; isSystemModule(), renderSystemModule()
  EmojiRating.jsx              виджет оценки эмодзи
public/                        ПУБЛИЧНЫЙ САЙТ
  utils/api.js                 publicApi — публичные запросы; ratings отправляет cookie, polls при наличии добавляет существующий admin_token
  hooks/useRating.js           загрузка и замена анонимной оценки страницы
  utils/sanitize.js            sanitizeHTML (DOMPurify), containsHTML
  utils/teamStorage.js         localStorage-хранилище данных команд (ключ humorpedia_teams, обновление раз в 24 ч)
  components/
    Layout.jsx                 Header + <Outlet/> + Footer
    Header.jsx                 меню из /sections (in_main_menu), автокомплит поиска
    Footer.jsx
    ListPageHeader.jsx         единая панель заголовка/поиска для общих списков
    AlphabetFilter.jsx         общий фильтр людей, команд, шоу и городов: показывает только буквы из `available_letters`; последний пункт `A–Z 0–9 #` объединяет латиницу, цифры и символы
    ForeignAgentNotice.jsx     динамическая звёздочка у имени и единое пояснение для людей, статей и новостей
    ModuleRenderer.jsx         рендер контентных модулей, включая poll (до/после голоса, доступная radio-group) и fallback неизвестного типа
    RatingCard.jsx             среднее, веха числа голосов и 10 кнопок-смайликов
    RelatedArticles.jsx        общий смешанный блок «Читайте также» для detail-страниц; URL и подпись типа приходят из API
    RelatedNews.jsx            компактный блок ≤3 свежих новостей после первого контентного блока
    StageSection.jsx, GameTable.jsx   стадии и таблицы игр сезона КВН (из season_data)
    LeagueSeasonsNav.jsx       навигация по сезонам лиги
    ShowAppearances.jsx        «Участие в других проектах»: индивидуальная ссылка на шоу, командная — на команду
    TeamProjects.jsx           единый блок проектов команды КВН: автоматические связи участников + ручной текстовый модуль
    ArticleCard.jsx, NewsCard.jsx, MultiSelectWithSearch.jsx
    competitions/              TeamParticipations (участие команды в турнирах), TeamRoster (состав), PersonCareer («Команды КВН» и роли человека), labels.js
  pages/
    HomePage.jsx               новости, популярные/случайная статья
    SectionDetailPage.jsx      CATCH-ALL `/*`: kvn/by-path → sections/path → redirects/lookup; при season_data отдаёт SeasonDetailPage; таблицы чемпионов лиг
    SeasonDetailPage.jsx       страница сезона КВН (стадии, игры, победители, жюри, prev/next)
    JuryStatsPage.jsx          статистика жюри Высшей лиги
    TeamDetailPage.jsx / TeamsListPage.jsx      команды КВН и команды шоу (TeamDetailPage: состав, вычисляемые проекты с ручным дополнением, «Участие в турнирах»; для команды шоу — showTeamPath, подпись «Команда шоу «…»»)
    PersonDetailPage.jsx / PeopleListPage.jsx
    ShowDetailPage.jsx / ShowsListPage.jsx      шоу до 4 уровней вложенности; проверенные ссылки встроены в существующие карточки участников
    ArticleDetailPage / ArticlesListPage, NewsDetailPage / NewsListPage, QuizDetailPage / QuizzesListPage
    CityDetailPage / CitiesListPage             география; люди и все команды города — карточки в основном потоке, у каждой команды указано КВН или название шоу
    SearchPage, TagSearchPage, ContactsPage, PolicyPage

admin/                         АДМИНКА
  hooks/useAuth.js             AuthProvider/useAuth: user из localStorage (admin_user), проверка /auth/me, тихий refresh каждые 6 ч; токен удаляется только при 401/403; STAFF_ROLES, isAdmin/isEditor/isModerator/isStaff
  utils/api.js                 axios `api` с Bearer из localStorage.admin_token и refresh-интерсептором (очередь запросов на время refresh);
                               группы: authApi, contentApi, statsApi, usersApi, tagsApi, commentsApi, mediaApi, templatesApi, sectionsApi; getErrorMessage()
  components/
    AdminLayout.jsx            сайдбар навигации (пункты «Пользователи», «База данных» и «Читайте также» — adminOnly)
    ModuleEditor.jsx           конструктор модулей страницы (dnd-kit), 1104 строки
    SeasonDataEditor.jsx       редактор season_data: стадии/игры/команды/баллы/конкурсы, копирование, dnd — 2665 строк, самый сложный компонент
  pages/RelatedContentSettingsPage.jsx  глобальные настройки «Читайте также»: включение, лимит, типы результатов и страницы показа
    RichTextEditor.jsx         TipTap (таблицы, цвета, выравнивание) + LinkInserter
    LinkInserter.jsx           поиск контента и вставка внутренней ссылки (/content/search-for-links)
    MediaSelector.jsx          выбор/загрузка медиа (uploads и volume-папки)
    TeamSelector.jsx, GameTeamSelector.jsx, PersonSelector.jsx, ContentRelationSelector.jsx, TagSelector.jsx, FactsEditor.jsx
    TeamMembershipsEditor.jsx  вкладка «Состав» в редактировании команды
  pages/                       *ListPage + *EditPage для: people, teams, shows, kvn, articles, news, quizzes, wiki, cities, sections, templates;
                               DashboardPage, LoginPage, MediaPage, TagsPage, CommentsPage, UsersPage, MongoAdminPage (сырой доступ к коллекциям),
                               ShowAppearancesPage (проверка участников шоу и точечное создание черновиков людей),
                               RelatedNewsSettingsPage (adminOnly: включение, свежесть, лимит и области применения)
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
| `/shows/{шоу}/teams/:slug` | ShowDetailPage → TeamDetailPage (адрес с предпоследним сегментом `teams` — команда шоу, `utils/teams.js`) |
| `/shows[/:parentSlug[/:childSlug[/:grandchildSlug[/:greatGrandchildSlug]]]]` | ShowsListPage / ShowDetailPage |
| `/quizzes`, `/quizzes/:slug` | QuizzesListPage, QuizDetailPage |
| `/city`, `/city/:slug` | CitiesListPage, CityDetailPage |
| `/contacts`, `/policy`, `/search`, `/tags/:tag` | статические / поиск |
| `/kvn/vl-kvn/vl-jury` | JuryStatsPage |
| `/*` | **SectionDetailPage** (КВН, разделы, редиректы старых URL) |

Админка (`ProtectedRoute` — пользователь залогинен И роль admin/editor/moderator; внутри `AdminLayout`):
`/admin/login`, `/admin`, `/admin/{people|teams|shows|kvn|articles|news|quizzes|wiki|cities|sections|templates}` и `/:id` (id = `new` для создания), `/admin/show-appearances`, `/admin/media`, `/admin/tags`, `/admin/comments`, `/admin/users`, `/admin/database`, `/admin/related-news` (adminOnly).

HomePage, SectionDetailPage и PublicLayout грузятся синхронно; остальное — `React.lazy`, админка — отдельным чанком.

## Как фронт находит бэкенд

`API_BASE` (в обоих api.js):
1. `REACT_APP_USE_API_PROXY=true` → `/api` (dev в Docker, прокси CRA → `http://backend:8001`);
2. иначе `window.__BACKEND_URL__` (ставит `public/config.js` для localhost) → `REACT_APP_BACKEND_URL` → `${protocol}//${hostname}:8001`.

Картинки: `/media/imported/...`, `/images/...`, `/uploads/...` — отдаёт бэкенд (в dev — через прокси CRA).
Если ожидаемого изображения нет или файл не загрузился, `FittedImage` и функции `utils/media.js` показывают один из
`/media/imported/images/pattern/{1..4}.jpg`; вариант стабильно выбирается по slug/id страницы.
`SectionDetailPage` делает `fetch(\`${BACKEND_URL}/api/redirects/lookup\`)` напрямую, минуя `API_BASE`.

### Рекомендации и опросы

- `RelatedArticles` используется статьями, новостями, людьми, командами, городами, шоу и KVN-страницами; ручные связи
  настраиваются `RelatedArticlesSelector` в редакторах статьи/новости.
- `RelatedNews` используется людьми, командами КВН, командами шоу и шоу. Он запрашивает только свежие новости по
  явным связям и не отображает loading/error/пустое состояние. В редакторе новости связи с командами и шоу задаёт
  `ContentRelationSelector`; глобальные настройки находятся на `/admin/related-news`.
- `poll` можно добавить в `ModuleEditor` статьи или новости. В диалоге создаётся/редактируется определение опроса,
  а модуль сохраняет только `poll_id`.
- Публичный модуль показывает результаты после голоса (либо заранее по настройке) и обрабатывает 401 сообщением о входе.
  Публичные страницы входа/регистрации не реализованы и остаются в бэклоге; обычный пользовательский путь голосования
  до этого недоступен, хотя backend-контракт полностью защищён и готов.

### Рейтинги

`RatingCard` встроен в страницы статьи, человека, команды и шоу независимо от старого системного модуля
`rating_widget`. Карточка показывает среднее с одним знаком после запятой и в скобках только веху числа голосов,
затем 10 кнопок-смайликов с доступными `aria-label` и `aria-pressed`. `useRating` получает и меняет оценку через
`publicApi` с `withCredentials: true`; после перезагрузки страницы сервер узнаёт посетителя по подписанной HttpOnly-cookie
и возвращает `my_score`. Новый выбор заменяет предыдущий.

## Конвенции

- Все тексты интерфейса на русском.
- Статус иностранного агента задаётся переключателем в `PersonEditPage`; звёздочку и поясняющий блок в HTML вручную не добавлять.
- HTML из БД выводить только через `sanitizeHTML` (DOMPurify).
- Заголовок вкладки — через `<WithTitle title="...">` в App.js или `usePageTitle`.
- В Docker (`DOCKER_ENV=true`) изменения `frontend/src` отслеживаются polling-наблюдателем раз в секунду; тяжёлые каталоги и медиа исключены, HMR/live reload включены. После смены ветки или зависимостей запускать корневой `scripts/dev-sync.ps1`.
- `plugins/health-check` подключается только при `ENABLE_HEALTH_CHECK=true`; старый неиспользуемый `plugins/visual-edits` удалён.
