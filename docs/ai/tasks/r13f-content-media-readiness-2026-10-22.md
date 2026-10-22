# R13f: готовность контента и материалов восстановления

Дата:22.10.2026. Ветка `codex/local-page-builder`, Базовый HEAD реализации R13f `a2eeb8803216db836fc3923ad8ea0ddd6fefa6bd`. Статус: согласованный вариант A выполнен изолированно; девять оригиналов подготовлены, общая карточка включена в frontend build, приёмка завершена. В основном хранилище изображения ещё отсутствуют; данные и production flags не менялись.

## Публикация R13e и CI

R13e с документацией опубликован отдельным [4e94eba](https://github.com/AMnEPka/humorpedia/commit/4e94eba69be3a9a4c90b4de85d6d9513eb1fa6c4). Первый CI39824229497 упал на старте тестовой Mongo gateway. Отдельный [CI-fix a2eeb88](https://github.com/AMnEPka/humorpedia/commit/a2eeb8803216db836fc3923ad8ea0ddd6fefa6bd) восстановил принятый seccomp-профиль, добавил readiness/diagnostics и отделил image pull от browser timeout; [диагностика](r13e-ci-gateway-startup-2026-10-22.md).

[GitHub Actions39826557657](https://github.com/AMnEPka/humorpedia/actions/runs/39826557657) на точном `a2eeb88` completed/success: backend, mongodb-integration, frontend, windows-tools, browser-smoke — все5jobs success. В browser job фактически выполнены старый smoke, HTML React pilot и native gateway. Remote ref подтверждён. Этот CI относится к опубликованному R13e/CI-fix; R13f опубликован отдельным [02c16ca](https://github.com/AMnEPka/humorpedia/commit/02c16ca3638a4fe601059e3c40f4e07e5aafe312); [GitHub39828202864](https://github.com/AMnEPka/humorpedia/actions/runs/39828202864) на точном SHA completed/success, все5jobs и все3 browser сценария success.

## Решение и источник

Пользователь выбрал восстановление оригиналов сначала: общая карточка для13 страниц без своего image;9 непустых битых ссылок закрывать исходными файлами или проверенной корректировкой пути. Индексация остаётся выключенной. Все9 точных оригиналов найдены, изменения ссылок не потребовались. Автоматический fallback для битого URL не реализуется; нейтральный description уже согласован R13a и не требует нового решения.

Исходный R13c snapshot от22.10.2026 10:47UTC:3911 projected документов/1105 published people+articles. SHA256 файла `d46cc85116ffeaf6de3237347d08d179b9c0cb43c3c1b477f0cc9ee9364c360f`. Нового экспорта/чтения основной Mongo не было; пользователи, очереди импорта и секреты в snapshot не входят. Собственные UUID DB содержали копию этих projected records, owner marker и synthetic admin.

Повторный read-only поиск по существующим локальным media/images томам и uploads подтвердил отсутствие9 точных путей. По basename без регистра/расширения найден один Farid .jpeg; он не использован после обнаружения точного оригинального .png. Это не полный поиск всех возможных транслитераций и не идентификация человека по фотографии.

## Материалы и приёмка

| Проверка | Результат |
| --- | --- |
| Оригиналы9 | Точные legacy URL200, image/jpeg или image/png, без redirect; size/SHA256/Pillow verify подтверждены |
| Общая карточка | frontend/public/share/humorpedia.png,1200×630; SVG-источник рядом. На основе существующих H/синего градиента/названия Header, без внешнего изображения |
| Строгая сборка | CI=true yarn build PASS; зависимости не изменены; release340fa99dc58ed63e53a92bd50009ba386b1ec5f9dcf80af25cccdddec5506a7b |
| Native HTML/JSON | 22 страницы: raw HTML200 + обычный API GET200; og:image = page_metadata.image_url; robots noindex; содержательный HTML fallback |
| Файлы через gateway | 10 уникальных URL: HTTP200/image MIME, byte SHA256 совпадает; Chromium image.decode PASS; common1200×630 |
| Изоляция и cleanup | Native FastAPI с одним lifespan, generated Nginx closed mode, internal network, Mongo tmpfs, без host ports/primary mounts. Writers остановлены, UUID DB удалена, containers/network/images очищены, error=null |
| Review | Независимая сверка9 восстановленных файлов, common asset, manifest и runtime evidence: блокирующих расхождений нет |

Raw HTML/JSON проверены настоящим приложением на копии данных; декодирование изображения — браузером. Полный React UI22 страниц не повторялся; UI parity R13e остаётся отдельным свидетельством. Локальная проверка не доказывает состояние VPS или публикацию файлов в основном storage.

Настройка isolated release: `PUBLIC_HTML_ENABLED=true`, `SEARCH_INDEXING_ENABLED=false`, `PUBLIC_HTML_DEFAULT_IMAGE_URL=/share/humorpedia.png`. Обычные Compose/env/flags не менялись.

[Manifest восстановления](r13f-media-recovery-manifest-2026-10-22.json) содержит9 исходных URL, target URL, размер, SHA256, формат, размеры и common asset. auto_apply=false. Для будущего применения: отдельное поручение; проверить staging hashes и containment; atomic placement только отсутствующих файлов, одинаковые существующие байты пропустить, отличающиеся — конфликт; Mongo не писать.

## Девять подготовленных оригиналов

| Страница | Исходный файл | Формат/размер |
| --- | --- | --- |
| [Фролова Анастасия](https://humorpedia.ru/people/anastasia-frolova) | [images/peoplekvn/anastasia-frolova.jpg](https://humorpedia.ru/images/peoplekvn/anastasia-frolova.jpg) | JPEG 1541×1703; 189261B |
| [Большакова Анна](https://humorpedia.ru/people/anna-bolshakova) | [images/peoplekvn/anna-bolshakova.jpg](https://humorpedia.ru/images/peoplekvn/anna-bolshakova.jpg) | JPEG 635×853; 109651B |
| [Ефанова Анна](https://humorpedia.ru/people/anna-efanova) | [images/peoplekvn/anna-efanova.jpg](https://humorpedia.ru/images/peoplekvn/anna-efanova.jpg) | JPEG 752×1003; 99249B |
| [Еремеевская Анна](https://humorpedia.ru/people/anna-eremeevskaya) | [images/peoplekvn/anna-eremeevskaya.jpg](https://humorpedia.ru/images/peoplekvn/anna-eremeevskaya.jpg) | JPEG 960×1280; 227701B |
| [Арефьев Дмитрий](https://humorpedia.ru/people/dmitry-arefiev) | [images/peoplekvn/dmitry-arefiev.jpg](https://humorpedia.ru/images/peoplekvn/dmitry-arefiev.jpg) | JPEG 853×1280; 150957B |
| [Гасанов Фарид](https://humorpedia.ru/people/farid-gasanov) | [images/people/om/farid-gasanov.png](https://humorpedia.ru/images/people/om/farid-gasanov.png) | PNG 853×1280; 1171176B |
| [Ерёмкин Максим](https://humorpedia.ru/people/maksim-eremkin) | [images/peoplekvn/maksim-eremkin.jpg](https://humorpedia.ru/images/peoplekvn/maksim-eremkin.jpg) | JPEG 854×1280; 83544B |
| [Давыдов Роман](https://humorpedia.ru/people/roman-davydov) | [images/people/roman-davydov.JPG](https://humorpedia.ru/images/people/roman-davydov.JPG) | JPEG 960×960; 146438B |
| [Светлана Приходько](https://humorpedia.ru/people/svetlana-prihodko) | [images/people/improv-teams/svetlana-prihodko.JPG](https://humorpedia.ru/images/people/improv-teams/svetlana-prihodko.JPG) | JPEG 800×1200; 96020B |

Path mapping `/media/imported/images/... → https://humorpedia.ru/images/...` совпадает с `legacy_url` в существующем restore_article_media_modx.py. Сам скрипт не запускался: его scan охватывает articles/news, а apply пишет в реальное media storage. Одноразовый probe сохраняет файлы исключительно в ignored `.cache/r13f/recovery` с exclusive create. Эти материалы — подготовка к восстановлению, не факт применения к основному стенду.

## Тринадцать страниц с общей карточкой

| Страница | Тип |
| --- | --- |
| [«А вы знали, что» №1](https://humorpedia.ru/articles/a-vy-znali-chto-1) | Статья |
| [«А вы знали, что» №2](https://humorpedia.ru/articles/a-vy-znali-chto-2) | Статья |
| [«А вы знали, что» №3](https://humorpedia.ru/articles/a-vy-znali-chto-3) | Статья |
| [«А вы знали, что» №4](https://humorpedia.ru/articles/a-vy-znali-chto-4) | Статья |
| [«А вы знали, что». Спецвыпуск](https://humorpedia.ru/articles/a-vy-znali-chto-spetsvypusk) | Статья |
| [Открытый блог: Битва каверов](https://humorpedia.ru/articles/bitva-kaverov) | Статья |
| [Humorpedia-2024: Глобальное обновление](https://humorpedia.ru/articles/humorpedia-2024-globalnoe-obnovlenie) | Статья |
| [Открытый блог: о переездах шоу на ТВ](https://humorpedia.ru/articles/openblog-pereezd-show) | Статья |
| [Встреча выпускников 2025: чем занимаются вчерашние квнщики](https://humorpedia.ru/articles/vstrecha-vypusknikov-2025) | Статья |
| [Открытый блог: «Взгляд на КВН через фигурное катание»](https://humorpedia.ru/articles/vzglyad-na-kvn-cherez-figurnoe-katanie) | Статья |
| [Иванченко Александр](https://humorpedia.ru/people/alexander-ivanchenko) | Человек |
| [Калугин Александр](https://humorpedia.ru/people/alexander-kalugin) | Человек |
| [Кравченко Виктор](https://humorpedia.ru/people/viktor-kravchenko) | Человек |

## Редакционная очередь

Для36 людей текущий согласованный fallback даёт `Человек: название.`. Это допустимый результат R13a; редакционные descriptions можно дополнить отдельным пакетом, без автоматического пересохранения SEO:

| Страница |
| --- |
| [Гараев Айдар](https://humorpedia.ru/people/ajdar-garaev) |
| [Пташенчук Александр](https://humorpedia.ru/people/alexander-ptashenchuk) |
| [Минатуллаев Амин](https://humorpedia.ru/people/amin-minatullaev) |
| [Волевачёв Артём](https://humorpedia.ru/people/artem-volevachev) |
| [Ильясов Артур](https://humorpedia.ru/people/artur-ilyasov) |
| [Рябцев Данила](https://humorpedia.ru/people/danila-ryabtsev) |
| [Спис Денис](https://humorpedia.ru/people/denis-spis) |
| [Дадаева Диана](https://humorpedia.ru/people/diana-dadaeva) |
| [Подлесный Дмитрий](https://humorpedia.ru/people/dmitry-podlesniy) |
| [Таратонов Эдуард](https://humorpedia.ru/people/eduard-taratonov) |
| [Олинчук Екатерина](https://humorpedia.ru/people/ekaterina-olinchuk) |
| [Семенычева Екатерина](https://humorpedia.ru/people/ekaterina-semenucheva) |
| [Юртайкина Екатерина](https://humorpedia.ru/people/ekaterina-yurtaikina) |
| [Червякова Елена](https://humorpedia.ru/people/elena-chervyakova) |
| [Стовбчатая Елизавета](https://humorpedia.ru/people/elizaveta-stovbchataya) |
| [Кененсаров Эрмек](https://humorpedia.ru/people/ermek-kenensarov) |
| [Цой Евгений](https://humorpedia.ru/people/evgenij-czoj) |
| [Тенишева Галина](https://humorpedia.ru/people/galina-tenisheva) |
| [Теруков Иван](https://humorpedia.ru/people/ivan-terukov) |
| [Фёдоров Константин](https://humorpedia.ru/people/konstantin-fedorov) |
| [Шпилёва Ксения](https://humorpedia.ru/people/kseniya-shpileva) |
| [Севастьянова Лея](https://humorpedia.ru/people/leya-sevastyanova) |
| [Туханин Максим](https://humorpedia.ru/people/maxim-tukhanin) |
| [Исаев Милан](https://humorpedia.ru/people/milan-isaev) |
| [Анисимова Анастасия](https://humorpedia.ru/people/nastya-anisimova) |
| [Касимова Наталья](https://humorpedia.ru/people/natalya-kasimova) |
| [Воинкова Наталья](https://humorpedia.ru/people/natalya-voinkova) |
| [Шергин Сергей](https://humorpedia.ru/people/sergej-shergin) |
| [Дуэт «Шастун и Макар»](https://humorpedia.ru/people/shastun-i-makar) |
| [Федянина Тая](https://humorpedia.ru/people/taya-fedyanina) |
| [Скок Валерия](https://humorpedia.ru/people/valeriya-skok) |
| [Рассказова Виктория](https://humorpedia.ru/people/viktoria-rasskazova) |
| [Карнович Виктория](https://humorpedia.ru/people/viktoriya-karnovich) |
| [Макаров Вячеслав](https://humorpedia.ru/people/vyacheslav-makarov) |
| [Краснопольская-Ледова Яна](https://humorpedia.ru/people/yana-krasnopolskaya-ledova) |
| [Журавлёва Злата](https://humorpedia.ru/people/zlata-zhuravlyova) |

Совпадения title/description не доказывают дубли сущностей и не разрешают слияние/смену slug:

| Поле | Страницы | Проверка |
| --- | --- | --- |
| title | /people/alexander-scheglov, /people/alexander-shcheglov | Различить метаданные после редакционной сверки |
| title | /people/alexander-maslyakov, /people/alexander-maslyakov-junior | Различить метаданные после редакционной сверки |
| title | /people/katya-ivanova, /people/ekaterina-ivanova | Различить метаданные после редакционной сверки |
| description | /people/dmitry-pustovalov, /people/kirill-shuklin | Обе descriptions называют Дмитрия Пустовалова: проверить копирование имени |
| description | /articles/za-kulisami-yumora-2, /articles/za-kulisamu-umora-1 | Общее описание серии интервью |

6 изображений с одной стороной меньше200px — очередь качества, новый блокирующий порог не вводится:

| Страница | Размер |
| --- | --- |
| [Юдин Александр](https://humorpedia.ru/people/alexander-yudin) | 170×204 |
| [Шарапова Анна](https://humorpedia.ru/people/anna-ssharapova) | 192×335 |
| [Кошевой Евгений](https://humorpedia.ru/people/evgeniy-koshevoi) | 300×168 |
| [Савин Михаил](https://humorpedia.ru/people/mikhail-savin) | 150×210 |
| [Шарипов Таймаз](https://humorpedia.ru/people/taimaz-sharipov) | 177×270 |
| [Саенко Тимофей](https://humorpedia.ru/people/timofey-saenko) | 272×185 |

## Evidence и остаток

- Ignored источники/команды: `.cache/r13c/content-snapshot.jsonl`, `.cache/r13f/{extract_gates.py,content-gates.json,scan_media.py,media-search.json,fetch-originals.cjs,legacy-probe.json,recovery/}`. Raw snapshot и восстановленные фотографии в Git не добавлены.
- Базовая media proxy проверка10 файлов и чистого metadata builder22: `.cache/r13f/{check-media.ps1,check-media.py,media-acceptance.json,media-cleanup.json}`.
- Итоговый native run `7b92c3f2817d4a54aa256488ee664e51`: `.cache/r13f/native-content/7b92c3f2817d4a54aa256488ee664e51/{closed/content-media.json,result.json,cleanup.json,commands.json}`. Одноразовый runner `.cache/r13f/run-content.cjs`, wrapper `harness/` и `check-content.cjs`; permanent repair/scheduler не добавлялся.
- Общая карточка создана SVG + Chromium render; редактируемый источник в frontend/public/share, одноразовый render.cjs и исходное превью в `.cache/r13f/share-preview/`.
- Основной checkout — чистый main ca46155; сервисы не перезапускались, HTTP3000 и8001/api/health200. Импорт24СМИ/VPS не менялись.

| Следующий шаг | Условие готовности | Модель |
| --- | --- | --- |
| R13f: отдельный commit/push выполнены,02c16ca; CI success | PNG/SVG + manifest + этот отчёт/указатели; raw данные и фотографии не включать | Sol/medium |
| Применить media пакет — только отдельное поручение | Backup/ownership целевого storage, проверенные SHA,9 безопасных placements, повтор22 HTTP/metadata; без изменения документов | Sol/high |
| Завершить общий аудит переноса | Демо-документы/ссылки/связность participants/дубли за пределами этого среза; findings до изменений данных | Sol/high |
| Интеграция и выпуск — отдельно | Main merge/dev-sync/полная приёмка, serving/indexing gates; VPS сейчас запрещён | Sol/high |

Исходная техническая программа R0–R12 реализована в ветке; main-интеграция/приёмка выпуска остаются. R13 — отдельный продуктовый инкремент исходного плана. Общий read-only отчёт продолжен и подготовлен в [R13g](r13g-migration-readiness-2026-10-22.md): полный срез связей, resolver, локальные медиа и конкретные очереди исправлений. Готовность контента к выпуску ещё не подтверждена; None resolver не означает HTTP404. Отдельные UX-функции сюда не включены.
