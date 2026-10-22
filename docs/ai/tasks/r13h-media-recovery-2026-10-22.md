# R13h — восстановление медиа и точные замены URL на копии

Дата:22.10.2026. Worktree:`r5-zip-operations/humorpedia`; ветка `codex/local-page-builder`. HEAD до незакоммиченных изменений:`467c7a6c892bc6cc47565d37c7cf9e8995d20305`.

## Результат

Пользователь выбрал точные замены URL на изолированной копии. Применены 78 mappings —104 поля в 79 документах.81 затронутая размещением файлов или заменами страница прошла HTTP/React-проверку; все 150 восстановленных изображений — HTTP200/image MIME/SHA256/Chromium decode. Исправлен MIME WebP через `/media`. Исходные snapshots, основная БД и media storage не изменялись. 22.10.2026 пользователь поручил отдельный commit/push R13h с документацией и проверку CI на новом SHA.

R13g уже опубликован отдельным `467c7a6`. [GitHub CI39832700995](https://github.com/AMnEPka/humorpedia/actions/runs/39832700995) completed/success на точном SHA, все 5 jobs и три browser-сценария success. Этот CI относится к R13g; локальная приёмка R13h завершена. Результат CI нового коммита фиксируется отдельно после публикации.

## Согласованное изменение данных

[Манифест 150 файлов](r13h-media-recovery-manifest-2026-10-22.json) фиксирует источник, исходный/целевой URL, поля документов, SHA256, размер, формат и staging path. Выбран вариант точных замен на копии, без новых Nginx aliases. Изначальный вопрос содержал 77 mappings; найденный затем 78-й оригинал с подтверждённым источником обработан по той же объявленной схеме. Это исправление пути, без подмены фотографий.

| Группа | Файлов | Выполнено на копии |
| --- | ---: | --- |
| `/media/imported/assets/*` | 72 | Файлы под прежними URL; записи не изменялись |
| `/assets/*` | 71 | Точные замены на `/media/imported/assets/*` |
| `https://humorpedia.ru/images/*` | 7 | Замены на уже существующие идентичные `/media/imported/images/*` |

Файлы сохранены в ignored `.cache/r13h/recovery`.150 originals:148 JPEG,1 PNG,1 WebP;3 758 438 bytes.177 source locations на 81 странице; из них 104 поля изменены,73 ссылки уже имели целевые пути.7 абсолютных URL на старом origin доступны; их локальные файлы совпадают по SHA, изображения не менялись.

Копия объединяет R13g content/media projections по collection/_id, проверяя равенство общих полей. В ней 25 620 записей; изменены только 104 объявленных строковых поля в 79 документах. После возврата этих полей полное структурное сравнение совпадает с baseline; хеши обоих исходных snapshots неизменны. Прямые URL заменены только при точном равенстве, HTML — только точный src/poster в media tag, не произвольное совпадение текста или href.

**Это объединённые проекции, не полный release archive.** В основной Mongo ничего не применено; будущий перенос требует отдельно подготовленного полного пакета и согласованной demo-policy из R13g.

Evidence: `.cache/r13h/copy/{baseline.jsonl,patched.jsonl,acceptance.json,pages.json}`.
- baseline SHA256:`5cf7d1c17a9ae7f3ab01900746cf30b429c3f587b32c06e3cb70a8af4b57ffbf`.
- patched SHA256:`3b81abc86dd255443950b37dbb2e3ff1c06171d2e319f185a31636471fa59d0b`.
- `prepare-copy.py`/`test-prepare-copy.py`:6 tests PASS — exact equality, HTML preservation, prefix/anchor exclusion, duplicate refusal, field-path validation. Скрипт не подключает БД; записывает только собственный каталог с exclusive create. Для повтора нужен новый пустой output, исходные файлы не перезаписывать.
- Независимое review сопоставило все 104 tuples(page,field,old,new) с manifest:0 лишних/пропущенных.

## Происхождение последнего WebP

Первый проход 150 старых URL дал 149 HTTP200 и 1 HTTP404. [Историческая страница Юлии Архипенко](https://humorpedia.ru/people/yuliya-arkhipenko.html) содержит точный `https://dev.humorpedia.ru/assets/cache_image/images/igra/womanteam_0x0_6fe.webP`. Этот оригинал вернул HTTP200/image-webp; SHA/Pillow verify+load подтверждены. На основном старом origin asset404; другой фотографией он не подменялся.

Evidence:`assets-probe.json`,`absolute-probe.json`,`missing-asset-legacy-source.json`,`provenance-asset-probe.json`,`verified-all.json`,`absolute-local-comparison.json`. Fetch scripts ограничивают concurrency≤3,timeout15s,15MiB cap,redirect=manual,containment и exclusive write. Основные media volumes читались только read-only.

## Исправление MIME

В freshly-built `Dockerfile.public-html --target backend-release` воспроизведён неправильный `Content-Type: text/plain` для WebP: Python3.11-slim не имеет записи MIME для этого расширения. Регистр `.webP` не был единственной причиной: lowercase тоже не определялся.

`backend/services/static_media.py` добавляет узкий `MediaStaticFiles`: после штатного file_response корректирует Content-Type только для WebP без учёта регистра. `backend/server.py` использует его для `/media`. Тела файлов не меняются, глобальная MIME-таблица и прочие mounts не изменены.

`backend/tests/test_static_media.py` проверяет .webp/.webP, bytes, JPEG/PNG,404, HEAD/Content-Length/ETag и conditional GET304. RED подтверждён на целевом release image до исправления; GREEN — на вновь собранном release image. Первоначальные failure/diagnostic evidence сохранены и не выдаются за окончательную приёмку.

## Приёмка

Native run:`358c7ed0ff8a4dcbaf3a4187024bfaae`, evidence `.cache/r13h/native-pages/358c7ed0ff8a4dcbaf3a4187024bfaae/`.

- Полный backend suite: **1193 passed,16 skipped**,24.81s;1 известный PendingDeprecationWarning python_multipart. Suite запускался в dev-image с изолированной Mongo; отдельная MIME-регрессия — в целевом release image.
- Настоящий backend с native lifespan, Nginx, Mongo8.0.32 на собственном UUID network/database; serving включён только в пилоте, indexing=false. Никаких host ports.
- HTTP/React **81/81**:71 people,8 kvn,1 show,1 team. JSON содержит целевые URL и не содержит прежних точных ссылок; HTTP200/noindex; React h1 и реальные изображения отрисованы. Для people проверен исходный HTML fallback.
- **150/150** media:HTTP200, корректный image MIME (включая WebP), исходный SHA, ожидаемые размеры и Chromium decode. В DOM найден 151 экземпляр 150 уникальных целевых URL; неотрисованных целевых URL0; pageerrors0.
- Сохранён неизменённый frontend build R13f release `340fa99dc58ed63e53a92bd50009ba386b1ec5f9dcf80af25cccdddec5506a7b`: frontend source в R13g/R13h не менялся. Новая frontend-сборка/Jest не повторялись.
- Скриншоты для people/kvn/show/team сохранены; визуально выборочно просмотрены people и kvn. Это не полный ручной UX-аудит.
- Временные writers штатно остановлены; owned DB удалена с проверкой marker, containers/network/images удалены. `cleanup.json`:containers=[],error=null. Отдельный RED diagnostic image удалён по проверенному ownership label. Первичный storage был read-only.

Повтор native acceptance: `BROWSER_BUILD_DIR=.cache/r13f/frontend-build node .cache/r13h/run-pages.cjs` (переменную задать по синтаксису оболочки). Нужны сохранённая projection copy/staging, browser-tools и локальные образы. Скрипт создаёт новые UUID-ресурсы и удаляет только их. Основной dev-sync из worktree не запускать.

Финальный контроль основного стенда: чистый main ca46155a9640d4723c07b9fd1762a6e639563414; backend/frontend/Mongo container IDs и StartedAt прежние, restarts=0, Mongo healthy, HTTP3000 и8001/api/health200. Импорт24СМИ и VPS не изменялись. Итоговая сверка файлов: source hashes и104 exact edits совпали;44 локальные ссылки документации валидны; git diff --check без ошибок.

## Что остаётся

-8 оригинальных season posters из R13g пока не найдены. Git-история, сохранённые snapshots и просмотренные R11 ZIP новых оригиналов не дали. Фото команд не подставлялись.
-111 внешних/embed URL широкого R13g-аудита сюда не входили. Все 150 файлов текущего пакета и 81 страница проверены, но весь контент сайта этим не сертифицирован.
- Правки конфликтов old_id/person_id и review неразрешённых ссылок — следующие независимые пакеты; модель Sol/high.
- Для применения в full release copy и интеграции нужны отдельная проверка полного пакета, demo-policy, финальная приёмка. Main/dev-sync, включение indexing и VPS — отдельное поручение.
