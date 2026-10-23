# R13m — остаток внутренних ссылок и две контекстные правки

Дата:23.10.2026. Статус: **две замены согласованы и приняты на изолированной копии; опубликованbb3221d, GitHub CI success**.

Ветка `codex/local-page-builder`, тот же worktree `r5-zip-operations/humorpedia`, HEAD до незакоммиченных изменений `1e80a34213652ad66244bfde9785b6c53534df10`. R13l опубликован этим SHA; [GitHub CI39945508291](https://github.com/AMnEPka/humorpedia/actions/runs/39945508291) completed/success, все5jobs и3browser-сценария success. Основной стенд остаётся на main, импорт24СМИ/VPS не затрагиваются.

## Результат

Проверены все **74 оставшихся keys:636 буквальных href в456 документах** принятой projection R13l. Счётчик старого content-audit —609 пар «поле,key»: collect_keys дедуплицирует повторения одного key внутри поля. Это разные единицы;636 не означает прирост ссылок после R13l.

Для двух ссылок подтверждены существующие published UUID и точные контексты. Подготовлен [машиночитаемый пакет](r13m-residual-link-proposal-2026-10-23.json), включающий обе исходные field SHA/Unicode offsets, selectors, исключение и полную классификацию74keys. Этот раздел фиксирует исходный review; согласованное выполнение и новая копия описаны ниже.

Source `.cache/r13l/copy/patched.jsonl`,25,620records, SHA256 `9d2fcb72a5a893bcb0f0aa4d7a12e88b0575956fd150bbe66508046ed6da2209`. Span-plan `.cache/r13m/exact-href-plan.json`, SHA256 `420118c913837ad2e88b1ad176437eaaf55f163f54586e1a295550c8160d9158`;2rules/2keys/2href/2fields/2docs,hidden0,unsupported0. Source status обеих страниц published.

## Две предлагаемые замены

| Исходная страница и поле | Старая ссылка / точная подпись | Цель и доказательство |
|---|---|---|
| `/shows/ne-spat/season3`, `modules[5].data.content` | `/shastun`, «Антон Шастун» | `/people/anton-shastun`, UUID `f61f7b37-d726-4e23-a495-0a6b996c98dd`, old_id116, SQL published1/deleted0. Совпадает собственный full_name человека; совпадение facts у дуэта «Шастун и Макар» не определяет сущность ссылки. |
| `/shows/ubojnaya-liga`, `modules[9].data.content` | `/chekhovikukota`, «Чехов и Кукота» в кавычках `«»` | `/people/chekhov-i-kukota`, UUID `df2371ba-1c12-43a2-aeb0-5e04ada904ae`, old_id131, SQL published1/deleted0; собственное имя записи — дуэт. |

Ссылка `/chekhovikukota` с подписью `Партизаны»` на `/shows/smeh-bez-pravil/season5`, UUID `f2728cdb-7aa4-41c5-9cca-622a93d9e23c`, `modules[5].data.content`, явно исключена. Историческое имя дуэта упоминается в биографии, но командная карточка «Партизаны» draft без old_id/old_urls, а контекст страницы нельзя молча превратить в ссылку на дуэт. Глобальный alias для chekhovikukota не предлагается.

Ожидаемый результат после отдельной реализации — **74→73 unresolved keys**, а не72: изменённая ссылка на дуэт перестанет быть старой, но key chekhovikukota останется из-за исключённых «Партизан». Это прогноз, не новый runtime-замер.

## Почему остальные ссылки не заменяются

| Группа | Keys | Буквальные href | Решение сейчас |
|---|---:|---:|---|
| Точные legacy ресурсы отсутствуют по old_id в projection |47|566|38 опубликованных SQL ресурсов,9 коротких league aliases разделяют те же цели. Нужен отдельный проект восстановления страниц; не заменять новостями/родителями. |
| Только draft-кандидаты: Мифы Древней Греции / Roast Battle |3|6|Не публиковать и не включать как published targets. |
| Нет точного текущего/legacy target по рассмотренным идентификаторам |5|14|Во все тяжкие, text10, Блиц крик, История на ночь, Я себя знаю: дальнейшее исследование, без догадки по slug. |
| Относительные VK resource URLs |2|4|podcasts-109800058 и video-63032186_456239420: нужна отдельная внешняя проверка и выбор назначения; внутреннего target не придумывать. |
| Остальные people/* |13|19|Нет точного собственного fullname/fact-name кандидата в projection; новые карточки не создавались. |
| Profile-preview |1|4|userid44 отсутствует в projection; одинаковое отображаемое имя не доказывает identity user→person. |
| Tag URLs |1|20|8 query-id groups, коллекции tags/taxonomy нет в projection; не заменять tag query на карточку человека. |
| Частичный кандидат chekhovikukota |1|2|Один href предложен к замене, другой явно исключён. |
| Подтверждённый shastun |1|1|Один href предложен к замене. |

Отсутствие в этой projection **не доказывает отсутствие в полной основной БД**. Read-only поиск выполнен по всем25,620 records, включая draft/archived; для38 SQL ID не найдено текущих записей с этими old_id. Поиск названий/URI и точные source labels сохранены в JSON; никакого импорта и переключения published не было.

## Отдельная очередь восстановления38 SQL ресурсов

Это инвентарь, не согласованный import-план. До реализации нужны scoped dry-run существующего MODX-контура, проверка payload/родителей/модулей/media, конфликтов UUID/old_id/slug и отдельных правил seasons. Полный Mongo export/release archive не запускается: существующий export-local намеренно останавливает основной стенд и противоречит текущей границе main.

| old_id | Старый URI | Название |
|---:|---|---|
|1541| `kvn/vysshaya-liga/referee/2022.html` | Члены жюри Высшей лиги 2022 года |
|1585| `kvn/league/krasnodarskaya-liga.html` | Центральная Краснодарская лига КВН |
|1586| `kvn/league/lampa/` | Центральная Лига Москвы и Подмосковья |
|1587| `kvn/league/start.html` | Центральная Лига Старт |
|1588| `kvn/league/tikhookeanskaya.html` | Центральная Тихоокеанская лига КВН |
|1589| `kvn/league/povolzhye.html` | Центральная Лига Поволжье |
|1590| `kvn/league/asia.html` | Центральная Лига «Азия» |
|1591| `kvn/league/southwest.html` | Центральная Юго-Западная Лига КВН |
|1592| `kvn/league/ural.html` | Центральная Уральская Лига КВН |
|1593| `kvn/league/2021.html` | Лиги МС КВН 2021 года |
|1594| `kvn/league/neva.html` | Центральная лига МС КВН «НЕВА» |
|1595| `kvn/league/2022.html` | Лиги МС КВН 2022 года |
|1596| `kvn/league/2023.html` | Лиги МС КВН 2023 года |
|1597| `kvn/golosyashiy-kivin/1995.html` | Голосящий КиВиН 1995 |
|1598| `kvn/golosyashiy-kivin/2021.html` | Голосящий КиВиН 2021 |
|1599| `kvn/golosyashiy-kivin/2022.html` | Голосящий КиВиН 2022 |
|1600| `kvn/golosyashiy-kivin/2023.html` | Голосящий КиВиН 2023 |
|1601| `kvn/specproekt/sp-2021.html` | Спецпроект КВН 2021 года |
|1602| `kvn/specproekt/sp-2022.html` | Кубок Мэра Москвы 2022 года |
|1603| `kvn/lampa/finals.html` | Финалы Центральной Лиги Москвы и Подмосковья |
|1604| `kvn/kivin/kivin-2022.html` | КиВиН-2022 |
|1605| `kvn/kivin/kivin-2023.html` | КиВиН-2023 |
|1606| `kvn/kivin/kivin-2015.html` | КиВиН-2015 |
|1607| `kvn/kivin/kivin-2016.html` | КиВиН-2016 |
|1608| `kvn/kivin/kivin-2017.html` | КиВиН-2017 |
|1609| `kvn/kivin/kivin-2018.html` | КиВиН-2018 |
|1610| `kvn/kivin/kivin-2019.html` | КиВиН-2019 |
|1611| `kvn/kivin/kivin-1991.html` | КиВиН-1991 |
|1612| `kvn/kivin/kivin-1990.html` | КиВиН-1990 |
|1613| `kvn/kivin/kivin-1993.html` | КиВиН-1993 |
|1614| `kvn/kivin/kivin-2024.html` | КиВиН-2024 |
|2333| `kvn/league/trempel.html` | Центральная лига МС КВН «Тремпель» |
|2396| `kvn/golosyashiy-kivin/2024.html` | Голосящий КиВиН 2024 |
|2537| `kvn/league/msl/2024.html` | Лига "Молодёжь Москвы" (МСЛ) 2024 |
|3072| `kvn/league/2024.html` | Лиги МС КВН 2024 года |
|3630| `kvn/dalnevostochnaya-liga/2025.html` | Сезон 2025 Дальневосточной лиги |
|3647| `kvn/golosyashiy-kivin/2025.html` | Голосящий КиВиН 2025 |
|3681| `kvn/league/2025.html` | Лиги МС КВН 2025 года |

Рекомендуемая модель для dry-run исследования: Sol/high; независимая проверка scope/идентичности — Luna/high. Восстановление этих страниц требует отдельного согласования данных и не включается в две href-правки.

## Согласованный план двух href

| Шаг | Критерий готовности | Модель |
|---|---|---|
|1. Guarded copy | Проверить source/plan/field SHA; применить ровно2spans в новой копии, старую не переписывать; исключение Партизаны unchanged | Sol/high |
|2. Независимая сверка |25,620records, только2href/2docs, все прочие поля/typed IDs/media/R13i/122seasons/9276participations равны | Luna/high |
|3. Resolver и API/HTML | Измеренный остаток73, без новых unresolved;2sources+2published targets API/HTML200/noindex | Sol/high |
|4. React и cleanup | Два видимых точных authored link click, целевые headings; excluded href сохранён в данных, API оставляет прежний text-only результат, before/after25620 вне views;UUID DB/internal network/noports/sourceRO;owned resourcesremoved/main unchanged | Sol/high |
|5. Документация | Новые реальные результаты и ограничения; commit/push отдельным поручением | Sol/high |

Новые full backend/build прогоны без изменения приложения не требуются; текущая data-приёмка должна быть отдельной. R13l CI не подменяет будущий R13m runtime. До согласования application code/new copy не менялись. Доступные варианты: принять эти2точных изменения на копии; либо оставить обе ссылки до более широкого content recovery. Рекомендация — небольшой точный пакет, чтобы не смешивать identities и восстановление38 отсутствующих страниц.

## Проверки предложения

Свежий offline extractor:74keys/636href/456docs; networknone/read-only source, приложение и Mongo не запускались. Mapping plan:2href/2fields/2docs, одно точное исключение,unsupported0. Независимый people/profile/tag review:17keys/46literal href; sourceSHA совпал. Финальная независимая сверка span-plan **PASS**, blockers0: оба field preimages/Unicode offsets/exact spans, label selectors, excluded sourceID/path/href и2target UUID/old_id/old_urls/SQLpublished подтверждены. Evidence `.cache/r13m/proposal-review.json`, SHA256 `73bc67f7f06def42fc9fe26901423312064ea01b2f7ebe2d0508a7ccfd7836b0`. Это pre-implementation review; новая runtime-приёмка описана ниже. Main/24СМИ/VPS/indexing не изменялись.

Финальная read-only проверка main23.10: чистый `ca46155a9640d4723c07b9fd1762a6e639563414`, прежние IDs/StartedAt контейнеров, restarts0, Mongo healthy, HTTP3000 и8001/api/health200; evidence `.cache/r13m/main-final.json`. В worktree остаются только незакоммиченные R13m и обновления статуса опубликованного R13l; backend/frontend/scripts/migrations diff пуст. Пользователь подтвердил обе точные замены на изолированной копии; ссылка «Партизаны» остаётся без изменений.

## Выполнение23.10.2026

HEAD до незакоммиченных изменений `1e80a34213652ad66244bfde9785b6c53534df10`. Пользователь согласовал2href/2docs, исключение Партизаны и прежние границы main/24СМИ/VPS. Commit/push R13m не выполнялись.

-5 copier guard tests PASS. Только pins/counts R13l copier обновлены, алгоритм сохранён. Новая `.cache/r13m/copy/patched.jsonl`, SHA256 `9c63bb45d3a18d66b0798bd81db27308546322db3996cb0cdc12673c379cc308`;25,620records,2fields/2href/2docs,hidden0,insert/delete0.
- Независимый copy audit PASS:25,618 unchanged raw lines byte-identical, в двух документах только2approved spans; excludedПартизаны field равен исходному; typed IDs/остальные поля/media/R13i/seasons/participations неизменны. Evidence `.cache/r13m/independent-copy-audit.{py,json}`.
- Реальный resolver **74→73**:2342keys/30,816 field-key occurrences,2269resolved; остаток равен предыдущему минусshastun,chekhovikukota остаётся. Relationfindings0,122seasons и9276participations совпали без missing/stale/changed/duplicates. Evidence `.cache/r13m/audits/{summary,content-audit,relations-audit}.json`.
- Первый native run `ab739155b7d64635a5b676aedc1d0963` остановлен assertion checker доbrowser: тест неверно требовал href для excluded unresolved anchor в API. По существующему `LinkResolver.replace_links` (`backend/services/link_resolver.py:96`) отсутствующая цель превращается в inner text; это штатное поведение, а исходный stored href остаётся прежним. Исправлен только ignored checker: offline/full snapshot equality для stored field, API сохраняет подпись без unresolved href. Cleanup первого run containers=[],network/imagesremoved,error=null.
- Retry `6699ba4c527c4e48bc2512d1652700d1` **PASS**: обе source pages и обе published target cards API/HTML200/noindex; excluded source также API/HTML200/noindex. В API исключённого поля сохранён текст «Партизаны» без unresolved anchor по штатному resolver; stored field точь-в-точь равен источнику. Два видимых authored links внутри prose реально нажаты в React; headings «Шастун Антон» и «Дуэт «Чехов и Кукота»» совпали точно. Pageerrors0, external blocked origins0; screenshots обеих карточек просмотрены.
- Before/after25,620record comparisons PASS вне штатных views; bounded streaming harness/sourceRO/UUID DB/internal network/nohostports/indexingfalse, настоящий app lifespan. Cleanup containers=[],network/imagesremoved,error=null; label-owned ресурсов не осталось. Product/source/output неизменны.

## Итоговая приёмка

Независимый full-copy audit и финальный static/artifact review **PASS**, blockers0. Final review `.cache/r13m/final-scope-review.json`, SHA256 `89dd2ff428191319f0814542eec51877255190f2fb1ff9c3e1215ba32276179f`; итог `.cache/r13m/acceptance-final.json`. Native evidence `native-pages/6699ba4c527c4e48bc2512d1652700d1/{result,cleanup}.json` и `closed/{links-http,links-browser}.json`. Source/plan SHA повторно проверены; новая copy SHA `9c63bb45d3a18d66b0798bd81db27308546322db3996cb0cdc12673c379cc308`.

Основной checkout: чистый main `ca46155a9640d4723c07b9fd1762a6e639563414`; прежние container IDs/StartedAt, restarts0, Mongo healthy, HTTP3000/8001/api/health200. Evidence `.cache/r13m/main-after-acceptance.json`. Импорт24СМИ, VPS, индексация и38 отсутствующих legacy resources не затрагивались.

Граница: это принятая projection25,620records, а не полноценный Mongo release archive. В native fixture остаётся прежнее предупреждение: unique `kvn.id` не создан из-за duplicate null; startup и проверяемые endpoints завершились. Исключённая сломанная цель не открывалась в браузере; сохранность исходного stored field подтверждена полным equality, публичный text-only результат — API. Новые full backend/build/CI не запускались без изменения продукта; сохранён R13l CI39945508291 на1e80a34,5jobs/3browser-сценария success.

Пользователь разрешил отдельный commit/push R13m с документацией и проверкой CI; на момент этой контрольной точки публикация ещё не выполнена. Следующий объём —73 неподтверждённых keys и отдельный scoped dry-run восстановления38 SQL resources; импорт этих страниц не согласован. Основной стенд и VPS не переключать.

## Публикация и продолжение23.10.2026

R13m с документацией опубликован отдельным `bb3221dee5810871a00e117473167ad4f47e6273` в `origin/codex/local-page-builder`. [GitHub CI39966829017](https://github.com/AMnEPka/humorpedia/actions/runs/39966829017) completed/success,attempt1 на точном SHA:5jobs и3browser-сценария success. Evidence `.cache/r13n/r13m-ci-{run,jobs}-final.json`.

Продолжение — [R13n](r13n-legacy-content-pilot-plan-2026-10-23.md): read-only восстановление исходного payload38SQLresources и проверка родителей/контрактов. Данные не импортированы; предложен отдельный пилот одной league-страницы Лампы с точным scope для согласования.
