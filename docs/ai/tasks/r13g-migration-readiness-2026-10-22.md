# R13g — read-only аудит перед переносом

22.10.2026. Ветка `codex/local-page-builder`; HEAD `02c16ca3638a4fe601059e3c40f4e07e5aafe312`, прежний worktree `r5-zip-operations/humorpedia`.

**R13f опубликован** отдельным [коммитом02c16ca](https://github.com/AMnEPka/humorpedia/commit/02c16ca3638a4fe601059e3c40f4e07e5aafe312). [GitHub CI39828202864](https://github.com/AMnEPka/humorpedia/actions/runs/39828202864) на точном SHA: completed/success, все5 jobs success, включая browser smoke, HTML+React pilot и native gateway. Долгая установка browser tooling завершилась успешно; дополнительного CI-fix не потребовалось.

R13g продолжает открытый пункт исходного плана: демоданные, ссылки, медиа, связность и дубли. Продуктовый код и исходные данные не менялись. Подготовлены review-очереди и шесть дополнительных оригиналов только в ignored staging. **Готовность всего контента к выпуску не подтверждена.**

## Источники и безопасность чтения

- Проекция **25 620 документов /15 коллекций**, 18:06:48–18:06:50 UTC: people1041, articles66, teams1310, shows257, news1018, kvn152, quizzes11, cities56, wiki0, sections0, memberships4838, show_appearances7468, seasons122, tournaments5, participations9276.
- 30 find +18 getMore, без команд записи. SHA256 `b49c0cec6cd7619c350962ce5184d8023e0934e8ec700bae4270171eb65dcbb7`,90 819 853 bytes.
- Отдельная media-проекция3911 документов/10 контентных коллекций,18:14:22–18:14:23 UTC:20 find +10 getMore; SHA256 `53fbf0814b0e851ab1c1af53a7f09dae72c691e9b677cb33f2bbf536ad74d65b`,66 099 256 bytes.
- Обе проекции прочитаны дважды: хеши выбранных полей совпали. Это последовательные чтения, не транзакционный snapshot всей БД. Вне полей/временных окон отсутствие изменений не утверждается.
- Только allowlist контента/связей; users, настройки, секреты и очереди импорта не читались. Standalone MongoClient без application lifespan; анализ — в одноразовых контейнерах без сети, файловые хранилища только read-only.
- Источник — основной локальный main; чистые функции — из ветки рефакторинга. Выводы не описывают VPS или старую production-БД.

## Контент и адреса

| Проверка | Результат |
| --- | --- |
| Canonical URL восьми типов | 0 коллизий среди nonarchived и отдельно published; одинаковый leaf slug иерархических страниц не считается дублем |
| old_urls | 0 конфликтов хранимых значений между nonarchived документами; это не HTTP-проверка всех старых адресов |
| old_id | **2540** у двух разных страниц: `/kvn/vl-kvn/vl-2008` и `/kvn/vl-kvn/vl-2009`; нужен первоисточник до исправления |
| Демо-новости | **10 published**: точные ID/slug `demo-related-news-01`…`demo-related-news-10`; заголовки и структура соответствуют `backend/scripts/seed_related_news_demo.py` |
| Одинаковые заголовки people | 3 группы review: Щеглов Александр; Масляков Александр; Иванова Екатерина |
| Дополнительная name_key группа «дуэт» | Ложный кандидат из-за снятия текста в кавычках; три разных дуэта не объединять |

Совпадение заголовков не доказывает дубль человека: Масляков старший/младший — явный пример. Щеглов/Иванова требуют доказательств идентичности, переноса связей и redirect-плана. Демо-новости не удалены/не архивированы; пользователь22.10.2026 выбрал исключение десяти точных ID из будущего пакета переноса с сохранением локально. [Policy manifest](r13g-content-transfer-policy-2026-10-22.json) применяется только к collection=news и точному string _id, без matching по title/slug/prefix.

## Внутренние ссылки

Проверены хранимые HTML-поля реальным `services.link_resolver.resolve_targets` с in-memory read-only адаптером запросов.

- 30 842 occurrences /**2577 ключей**;2233 разрешены, из них10 переписываются на текущие адреса.
- **344 ключа** получили None;342 встречаются в видимых resolver-полях published страниц (1171 страница). Все unresolved occurrences с legacy/hidden полями:2494, страниц1187.
- По контракту None превращает ссылку в текст: это потеря перехода, **не утверждение о344 HTTP404**. Все URLs через HTTP/UI не обходились.
- Кандидаты R13c подтверждены:13 people/articles страниц,14 people-ключей с None после проверки old_urls и pattern rules.
- Review-очередь по последнему slug: **194** с одним кандидатом, **21** с несколькими, **129** без точного кандидата. Один кандидат не разрешает автоматический rewrite; нужны тип страницы и исходный текст.
- Примеры: `armavir` → возможный `/city/armavir`; `anton-baryilik` → `/people/anton-baryilik`; `Improv/gromkiy-vopros` → `/shows/medium-quality/improkom/gromkiy-vopros`. Новых resolver rules нет.

## Составы, появления и соревнования

| Область | Результат |
| --- | --- |
| memberships4838 | confirmed1441;candidate1;rejected22;roster_text без привязки3372;прочие без привязки2 |
| show_appearances7468 | 3289 с существующим person_id;4179 local_content без привязки |
| Проверенные непустые указатели | 0 отсутствующих целей team/person/candidate/season/show/source-page/tournament |
| seasons122 → participations9276 | Реальные build_participations + PersonLookup: game5248 +season2414 +role1614; **все9276 совпали**, missing/stale/changed/duplicate IDs=0, все поля builder покрыты проекцией |
| Дубли appearances | 0 одинаковых проверенных variants;0 cross-source overlaps |
| Составы | Один конфликт идентификации для review, ниже |

Unlinked/candidate/rejected — разные допустимые состояния, не автоматические ошибки. Game/season/role строки не схлопываются по паре person+season.

`/kvn/teams/sbornaya-vladivostoka` содержит два вручную confirmed имени с одним person_id `59458e72-a706-4d13-8a3e-e4f97368ed7f`:
- `4050fe35-5a2e-5151-9749-8a90933a44d2` — «Абдул-Кадыров Михаил»;
- `93f24933-757f-5fbb-9500-1aaaf347695c` — «Александр Мадич».

Это конфликт для проверки, не готовая операция удаления дубля. Явно rejected «Антон Воронин» со старым slug Вадима отделён от confirmed Вадима; отменять rejection нельзя.

## Медиа

**2428 уникальных URL /7438 occurrences** из сохранённых photo/logo/poster/cover/header/image/seo, модулей и HTML src/poster/srcset nonarchived документов. Включены legacy/скрытые поля; это не перечень выбранных UI изображений.

| Категория | URL | Покрытие |
| --- | ---: | --- |
| Файлы присутствуют | 2143 | Локальный файл + успешный Pillow.verify |
| Отсутствуют относительные /media/imported/images | 23 | 9 R13f ещё не применены;14 дополнительных |
| Отсутствуют /media/imported/assets | 72 | Фактический каталог backend проверен read-only; очередь восстановления MODX cache |
| Старые /assets/* | 71 | Вне проверенных mounts; HTTP/маршрутизация не проверялись |
| Абсолютные humorpedia.ru/images/* | 7 | Нет соответствующих локальных /images файлов; старый origin не проверялся, это не подтверждённые remote404 |
| Внешние media/embed URL | 111 | Не загружались |
| pattern-1.jpeg | 1 | Известный legacy placeholder: public team helper выбирает существующий pattern;1390 raw occurrences не равны1390 сломанным UI. Админский список читает logo напрямую и требует отдельной проверки |

По принятому подходу «восстановление сначала» для14 новых /media/imported/images проверены точные старые пути. **6 оригиналов**: HTTP200 без redirect, image/jpeg, SHA/bytes/Pillow.verify; сохранены только в `.cache/r13g/recovery`. **8 постеров сезонов** вернули404 по точному пути; замены не выбраны. [Manifest с хешами и нерешёнными адресами](r13g-media-recovery-manifest-2026-10-22.json).

Новые проверенные оригиналы: `igra/improvizatory-zvezdy копия.jpg`, `igra/zvezdy3.jpg`, `kvn-team/negoden2.jpg`, `peoplekvn/anna-eremeevskaya2.jpg`, `shows/pnr.jpg`, `shows/teoria.jpg`.

| Сезон / missing poster в kvn-season | Существующий кандидат фото команды в kvn-team |
| --- | --- |
| vl-2010 /skk-2010.jpg | skk.jpg |
| vl-2011 /sok-2011.webp | sok.jpg |
| vl-2012 /triod-2012.jpg | triodidiod.jpg |
| vl-2013 /gorod-pyatigorsk-2013.jpg | gorod-pyatigorsk.jpg |
| vl-2014 /soyuz-2014.webp | soyuz.png; не одноимённая команда шоу |
| vl-2016 /asia-mix-2016.jpg | asia-mix.jpg |
| vl-2017 /sparta-2017.jpg | sparta.jpg |
| vl-2018 /vyatka-2018.webp | vyatka.jpg; страница draft |

Кандидаты связаны с участниками сезонов в snapshot, файлы существуют. Это **не подтверждённые замены постеров**: SeasonDetailPage выводит season.poster напрямую, team fallback к нему не применяется. Пользователь22.10.2026 выбрал продолжение поиска оригиналов без подстановки фото команд. Дополнительный поиск точных имён без учёта регистра по imported/images/uploads дал0 совпадений; это не поиск всех возможных альтернативных названий. Поиск продолжен также в сохранённых R11/R13c/R13g материалах: у восьми сезонов нет old_id/old_urls, в R11 уже записаны те же missing пути. Точный поиск имён на старом сайте не дал результатов; доступный web-просмотрщик не смог получить страницы сезонов (Cache miss). Это ограничение поиска, не доказательство отсутствия оригиналов вообще. Evidence: `poster-local-search.json` и `poster-snapshot-search.json`; для продолжения нужны подтверждённые исходные файлы/резервная копия или доступный первоисточник.

Шесть новых оригиналов ещё не проходили native gateway/React приёмку; результаты R13f22 страниц/10 изображений на них не распространяются.

## Проверки и evidence

- **16 synthetic tests PASS**:3 content links,10 relations,3 media. Проверены archived/missing/legacy links, иерархия slug/hidden modules, candidate/rejected/неоднозначные имена, game/season/role, dangling pointers/field coverage, path containment/повреждённый файл/external URLs.
- Независимое review подтвердило content counts и ограничения media-проверки. Ложные кандидаты «дуэт» и rejected Воронин отделены от findings. Ни ensure_index/repair/sync, ни application lifespan не запускались.
- Ignored evidence: `.cache/r13g/{manifest.json,media-manifest.json,content-snapshot.jsonl,media-snapshot.jsonl,content-audit.json,relations-audit.json,link-review-queue.json,media-audit.json,media-review.json,legacy-probe.json,verified-originals.json,recovery/}`.
- Одноразовые анализаторы и тесты рядом: `audit_content.py`, `audit_relations.py`, `audit_media.py`, `test_audit_*.py`. Export scripts фиксируют allowlist полей и сравнение двух чтений. Raw snapshots, фотографии и полные логи в Git не добавлять.
- Согласованная политика demo проверена на отдельном offline preview:25620→25610 records,news1018→1008;удалены ровно10 ID,остальные строки byte-identical, SHA источника не изменился.4 проверки exact-match/другая collection/похожий ID/title-slug PASS. Evidence `transfer-preview-acceptance.json`. Это projected preview, не полный Mongo release archive; существующий `export-local.mjs` не запускался и пока не применяет policy автоматически. Будущий transfer обязан применить её на отдельной release-копии и повторно проверить результат.
- CI evidence предыдущего R13f: `.cache/r13g/r13f-ci-jobs-final.json`; результат публикации самого R13g приведён ниже.

## Следующие пакеты

| Работа | Условие готовности / решение | Модель |
| --- | --- | --- |
| Политика10 demo ID при переносе | Выбор принят: exclude manifest; offline copy PASS. Перед настоящим transfer применить к полной отдельной release-копии, не к main | Sol/high |
| Media recovery | Сохранить9+6 готовых оригиналов; проверить72 cache files/71 legacy asset URL, оригиналы8 постеров, без замены team photo по выбору пользователя; применение отдельно | Sol/high |
| Конфликты old_id/person_id | Первичные доказательства для2540 и состава Владивостока; конкретный before/after пакет до согласования изменений | Sol/high |
| Внутренние ссылки | Проверить194 кандидата и21 неоднозначный; fixtures+HTTP/React на копии; не угадывать глобально по slug | Sol/high |
| Интеграция и выпуск | Отдельное поручение: merge/main/dev-sync, повтор приёмки, serving/indexing gates. VPS сейчас запрещён | Sol/high |

Read-only отчёт исходного пункта плана подготовлен с явным покрытием; он не закрывает очереди исправления/внешних проверок. R0–R12 реализованы в ветке; оставшиеся действия — данные, интеграция и выпуск. Основной checkout проверен: чистый main ca46155, прежние container IDs/StartedAt и0 restarts, Mongo healthy; HTTP3000 и8001/api/health200. Импорт24СМИ и VPS не изменялись. 22.10.2026 пользователь поручил отдельный commit/push R13g вместе с документацией и проверку CI на новом SHA; следующий этап — продолжить изолированные пакеты из этого плана.

## Публикация R13g и продолжение

22.10.2026 R13g с документацией опубликован отдельным коммитом `467c7a6c892bc6cc47565d37c7cf9e8995d20305` в `origin/codex/local-page-builder`. [GitHub CI39832700995](https://github.com/AMnEPka/humorpedia/actions/runs/39832700995) completed/success на точном SHA; все5 jobs и три browser-сценария success. Evidence: `.cache/r13h/r13g-ci-{run,jobs}-final.json`. Следующий пакет [R13h](r13h-media-recovery-2026-10-22.md) подготовил150 originals и применил согласованные78 URL mappings только к копии; WebP MIME исправлен, native HTTP/React81 и media150 PASS;8 posters не подменялись. R13h опубликован7678c4b, GitHub39844032265 completed/success (все5 jobs и три browser-сценария). [R13i](r13i-identity-corrections-2026-10-22.md) применил обе согласованные правки только на копии: native API/React4/media150,25 tests PASS; findings0,9276 participations без изменений. Full release acceptance отдельно; Публикация R13i разрешена пользователем. Main/24СМИ/VPS не изменялись.
