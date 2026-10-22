# R13a: контракт публичного HTML и метаданных

Дата: 22.10.2026 (МСК). Ветка `codex/local-page-builder`, HEAD до документационных изменений `893b57eb97c1858979b5de137f4d22cb2a622287`.
Worktree: `C:/Users/rdp6126443.gmail.com/.codex/worktrees/r5-zip-operations/humorpedia`.
Статус: исследование и исходная HTTP-проверка завершены; контракт ниже утверждён пользователем 22.10.2026; выбран следующий результат — план изолированного FastAPI HTML-пилота. Изменений приложения, API, БД, конфигурации стенда или VPS в R13a пока нет.

## Цель и границы

Согласовано пользователем 22.10: цель R13 — индексация публичных страниц в поиске и превью ссылок; сначала контракт и проверка, затем выбор способа выдачи HTML. Основной адрес для canonical — `https://humorpedia.ru`. Это проектная настройка будущего выпуска, не переключение DNS/старого сайта.
Сохранить primary checkout/стенд на main, не менять импорт 24СМИ, не выкладывать на VPS. Полный dev-sync остаётся после интеграции. Публикация R12c выполнена отдельно; R13a не включён в её коммит.

Предлагаемый первый охват будущего пилота: главная и detail-страницы человека, команды КВН, команды шоу, шоу, статьи, новости и сезона/иерархической страницы КВН. Каталоги/пагинация, search/tag/facet URLs получают явную отдельную политику перед расширением индексации. Имена/биографии/даты/права контента не переписываются; HTTP API остаётся совместимым.

## Проверенные факты

- `frontend/index.html` задаёт lang=en, общий title и пустой root. `utils/pageTitle.js` меняет только document.title после запуска React. Detail hooks используют title сущности, а `seo.meta_title` не становится единым источником title.
- `backend/models/base.py:SEOData` уже хранит meta_title/meta_description/keywords/og_image. Просмотренные формы редактируют title/description; наличие keywords/og_image в схеме/API не означает наличие полного UI для них. Публичная карточка человека может показывать meta_description как видимый текст, но это не meta-тег head.
- `App.jsx` содержит публичные иерархические маршруты и catch-all. `SectionDetailPage.jsx` вызывает lookup и navigate(replace) при неудачной загрузке; HTTP-redirect при этом не формируется.
- `services/content_visibility.py` исключает archived для анонимного чтения, но пропускает draft и документы без status. Для индексации нельзя автоматически приравнять «видим через текущий GET» к «публикуется в sitemap»: это отдельная политика, см. ниже.
- Путь команды уже централизован в `services/show_teams.py:team_url`: КВН — /kvn/teams/{slug}, команда шоу — /shows/{full_path}. Шоу/КВН используют свои full_path. Canonical нельзя вычислять только из последнего slug.
- В frontend public кроме config.js нет отдельной share-картинки. Наличие media в runtime не проверялось. Перед приёмкой OG понадобится доступный публичный fallback image, если у сущности нет изображения.
- В `scripts/vps-test/https-public.conf` уже настроены X-Robots-Tag noindex/nofollow и robots с Disallow: /. Их нельзя переносить в заключение «robots нигде нет» и нельзя снимать этим пакетом.

## Исходная HTTP-проверка

Запущен отдельный nginx из финального `humorpedia-r12c-frontend-cloud`: без host-портов, Mongo и запросов к основному сайту. Собственный Node24-контейнер делает только GET; JavaScript не выполняется. После проверки оба контейнера удалены.
11 адресов: /, синтетические /people/r13a-sample, /kvn/teams/r13a-sample, /shows/r13a-sample, /articles/r13a-sample, /kvn/r13a-league/r13a-season, /admin/login, /r13a-missing, /people/r13a-legacy.html, /robots.txt, /sitemap.xml.

| Наблюдение | Результат |
|---|---|
| HTTP | 11/11 — 200, Location отсутствует |
| HTML | 11/11 lang=en, один title Humorpedia \| humorpedia.ru, пустой root |
| Метаданные | description/canonical/OG/robots/X-Robots-Tag: 0/11 |
| robots.txt / sitemap.xml | Оба возвращают text/html с SPA shell; это не robots/sitemap |
| Границы | Синтетические URL не доказывают наличие/статус сущностей или фактическое SEO production/VPS |

Скрипт и машинный снимок: ignored `.cache/r13a/check-baseline.cjs` и `baseline.json`; результат `baseline.log`. Это наблюдение текущей выдачи, а не пройденная приёмка будущего контракта.

## Утверждённый контракт v1

Один нормализованный read model страницы нужен серверной выдаче и переходам React. Источник — уже разрешённый публичный документ и его канонический путь. HTML и клиент не должны независимо придумывать title/canonical.

| Поле | Предлагаемое правило |
|---|---|
| lang / locale | ru / ru_RU; lang также в исходном HTML |
| title | trim(seo.meta_title), иначе существующее название/вычисленный team title; суффикс humorpedia.ru один раз, как buildPageTitle |
| description | trim(seo.meta_description), иначе plain-text excerpt сущности; если его нет — нейтральное описание типа и названия. Без выдуманных фактов и автоматического пересохранения SEO |
| canonical_url | Подтверждённый origin + canonical path из доменной модели. Абсолютный HTTPS URL; без fragment/tracking. Для detail не копировать query из запроса. Семантические page/filter параметры каталогов требуют отдельного правила |
| og:title / description / url | Совпадают с теми же полями модели; url равен canonical. Не использовать current Host/проксированные headers как источник домена |
| og:type | article для статьи/новости, website для остальных пилотных страниц |
| og:image / alt | SEO image → публичная обложка/постер → настроенная общая share-картинка. Только публичный HTTP(S) URL, относительный путь разрешается от основного origin; изображения backend не скачивает |
| robots | Согласовано: index,follow только для явно published сущностей; draft/missing-status — noindex,follow, archived/unknown — 404. Текущая доступность GET сохраняется; распределение legacy status проверяется перед включением индексации |
| response | 200 для существующей публичной страницы; 404 для отсутствующей/archived; подтверждённый old URL → постоянный 301 на разрешённый canonical target; отказ БД/ошибка сервера — 5xx, не общий indexable shell |

Ручные SEO строки сохраняются как значения: trim/нормализация пробелов и HTML escaping при выдаче; не внедрять произвольный HTML/script, не обрезать сохранённое значение «до SEO-лимита». Длина сниппета в поиске не является гарантией контракта.
keywords остаётся совместимым полем API; обязательное новое использование/правки данных не вводятся. JSON-LD не генерируется до согласования типов и проверки фактов.
При SPA-переходе заменять весь набор принадлежащих странице head-тегов, удалять прежние; Back/Forward восстанавливают те же значения. Исходный HTML и состояние после JS совпадают по title/description/canonical/OG/robots.

Для published production-страницы не отдавать временный noindex с расчётом снять его только JavaScript. Production indexing включается отдельной настройкой выпуска; dev/test/VPS staging сохраняют noindex. Canonical origin — фиксированная настройка, а не указание разрешить индексацию тестового IP. Для admin/login/preview/search не публиковать данные и ссылки в sitemap. Изменение HTTP-статусов относится к будущей HTML-выдаче, не к существующему JSON API.

## Приёмочный набор будущей реализации

1. Опубликованные fixture-документы всех типов пилота: raw GET без JS возвращает ru, уникальные непустые title/description, ровно один canonical и полный согласованный OG-набор. canonical/og:url совпадают, общий fallback image доступен как изображение.
2. В исходном HTML есть содержательный H1/основной текст и обычные ссылки на связанные публичные страницы, соответствующие разрешённым данным. Только head над пустым root покрывает требования к метаданным, но не считается завершённой реализацией выбранной цели.
3. КВН и одноимённая команда шоу имеют разные адреса; многоуровневые full_path не схлопываются. Encoded paths/fragment/tracking и недоверенный Host не создают другой canonical origin.
4. Пустое SEO, HTML/кавычки в названиях, кириллица и уже добавленный suffix проверяются fixtures; escaping не теряет текст и не создаёт новые элементы/script.
5. Draft и legacy missing-status не попадают в индексируемый набор по умолчанию; archived/unknown дают 404. Editor cookie/token/preview никогда не расширяют публичный HTML-кеш или sitemap.
6. Для существующего legacy URL — 301 с Location на разрешённую цель; неизвестный URL — 404. Приватная/архивная цель не раскрывается через redirect. JSON lookup сохраняет прежний контракт.
7. JS-off HTTP и настоящий browser: после перехода/Back/Forward/прямого refresh нет дублей и оставшихся тегов предыдущей страницы; интерактивные модули и существующий browser smoke работают.
8. Sitemap XML использует тот же published resolver/канонические URL; robots — text/plain, staging disallow/noindex сохраняется. Эти endpoints входят в завершённый R13, но не являются реализованными в R13a.
9. Измерить cold/warm p95, память, invalidation после изменения/архивации/slug и restart на изолированных данных. Численный бюджет определить по измерениям перед выбором способа выдачи HTML; старые R11 цифры не выдаются за проверку SSR.

## Следующий выбор: способ выдачи HTML

| Вариант | Плюс | Цена/проверка перед выбором |
|---|---|---|
| Публичный HTML в FastAPI, React продолжает интерактивный UI | Без дополнительного Node-сервиса; прямой доступ к существующим readers/visibility | Второй renderer требует явного общего read model и проверки соответствия текста/модулей; не переписывать все renderer сразу |
| React SSR с передачей серверных данных | Можно использовать React-компоненты для начального документа | Нужны server-safe компоненты/загрузка данных и Node runtime; текущие страницы получают данные в useEffect, одного renderToString недостаточно |
| Prerender опубликованных URL | Дешёвая статическая выдача | Нужны snapshot/invalidation/delete после архивирования/slug; очередной источник устаревших проекций без протокола восстановления неприемлем |

Рекомендация для следующего решения: ограниченный изолированный пилот FastAPI HTML на человеке и статье с общим read model; сравнить с React SSR по точности, p95/памяти и объёму дублирования. Пользователь утвердил контракт и поручил подготовить [план изолированного пилота FastAPI HTML](r13b-fastapi-html-pilot-plan-2026-10-22.md); production способ выдачи выбирается по результатам пилота. Перенос данных, включение индексации, SSR-служба и новая выкладка не выполняются автоматически.

Основания: Google исполняет JS, но рекомендует server/pre-render и указывает, что не все боты исполняют JS; HTTP-статусы и исходный canonical должны быть осмысленными. Это подтверждает необходимость двух проверок (raw HTML и browser), а не утверждение «Google не видит SPA». [Google JavaScript SEO](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics).
Canonical и sitemap должны указывать согласованные URL; canonical не является гарантией индексации. [Google canonical](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls).
Полный базовый OG-набор включает title/type/image/url; locale и description дополняют его. [Open Graph protocol](https://ogp.me/).

## Публикация предыдущего этапа

R12c с документацией опубликован отдельным коммитом `893b57eb97c1858979b5de137f4d22cb2a622287` в origin/codex/local-page-builder; remote ref совпадает. [GitHub CI39751492738](https://github.com/AMnEPka/humorpedia/actions/runs/39751492738) на точном SHA: completed/success, все пять jobs success, включая новый test:tooling и полный browser smoke. Перед commit повторно прошли 5 tooling и 331 Jest, staged diff проверен; три JSX-переименования R100.
