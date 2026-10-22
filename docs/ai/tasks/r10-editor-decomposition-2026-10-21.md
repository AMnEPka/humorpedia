# R10: декомпозиция редакторов

Обновлено: 2026-10-21. Ветка codex/local-page-builder, HEAD до незакоммиченных изменений R10: 43d61dd8e3feaeeb8a50ac56bde26837ef1e0bfa. R10 опубликован отдельным коммитом `7ad05779b81e347d6f22ffd4dd2e3612c717c4fa`; ветка отправлена в origin. [GitHub CI 39662453665](https://github.com/AMnEPka/humorpedia/actions/runs/39662453665): все пять jobs success. Свежий frontend перед публикацией — 56 suites / 331 tests; backend identity — 14 passed. По ответу пользователя удаления сохранены как сейчас; новые подтверждения вынесены в отдельный бэклог.

## Доставка R9 и CI

R9 с документацией опубликован отдельным коммитом df6e0191938a8b484579fb3b4aa92b1efe74fe9b. CI выявил стартовую гонку Mongo chown/mongosh и зависание RAF polling в sandboxed iframe; исправления опубликованы отдельно как 2e0a050 и 43d61dd. [Диагностика](ci-workflow-recovery-2026-10-21.md).

[Итоговый GitHub Actions run 39655534921](https://github.com/AMnEPka/humorpedia/actions/runs/39655534921) на 43d61dd: completed/success, все пять jobs — backend, frontend, mongodb-integration, windows-tools, browser-smoke. Это проверка опубликованного R9/CI; R10 ниже проверен локально.

## Результат и границы

Основание — согласованный [R10 общего плана](project-refactoring-plan-2026-10-21.md). SeasonDataEditor и ModuleEditor разделены по операциям, props и формат JSON сохранены. Основной checkout и Docker остаются на main ca46155; импорт 24СМИ и VPS не затронуты.

- SeasonDataEditor — координатор состояния и callbacks (545 строк вместо 2760). В season-editor выделены StageEditor, GameEditor, TeamResultEditor и чистые операции стадий, игр, результатов и конкурсов. Четыре прежних identity exports сохранены для совместимости.
- ModuleEditor — список, добавление и DnD (232 строки вместо 1077). В module-editor выделены диалог с локальным draft, диспетчер форм и конкретные редакторы. ModuleDataFields остаётся существующим fallback; API опросов перенесён без изменения.
- KVNEditPage остаётся координатором загрузки и CAS-сохранения канонического сезона. TipTap, form framework, зависимости, реестр модулей, формат API и документов не менялись. В backend/services/season_editor.py исправлено только сопоставление identity при появлении новых копий.
- Операции reorder/move больше не меняют вложенные объекты исходного сезона; дополнительные поля winners сохраняются. Замороженные JSON-fixtures проверяют ID, custom fields, ссылки team/person, scores/total, additional_teams и конкурсы.
- Копия игры удаляет и _canonical_id, и legacy id. Иначе копия перед оригиналом могла занять его canonical identity и вызвать 422. Содержимое, метаданные и ссылки участников копируются; оригинальная игра сохраняет ID.
- Backend заранее резервирует canonical IDs, явно указанные во всём editor_data, отдельно для стадий и игр. Legacy/name fallback не занимает ID существующей одноимённой копии, даже если новая копия поставлена раньше неё. Foreign/duplicate markers дают 422; запросы без sidecars сохраняют прежний fallback. Unit-тест сначала воспроизвёл 422, затем прошёл с исправлением.
- ModuleEditor безопасно обрабатывает отмену DnD без over. Таблица инициализирует прежние defaults в локальном draft без setState родителя во время render. Закрытие диалога через Escape по-прежнему сохраняет draft; ручная редакторская правка проходит через прежний onChange.
- Добавлены доступные имена кнопок перемещения/раскрытия и полей баллов, использованные в настоящей браузерной приёмке.

## Проверки

- Полный frontend: CI=true yarn test --watchAll=false --runInBand — 56 suites / 330 tests passed. После этого добавлен один тест Escape: ModuleEditor.test.jsx — 7/7 passed; После полного прогона frontend изменены только тест Escape и хвостовые пробелы новых файлов; для очистки пробелов проверено полное совпадение результата Babel до/после.
- Backend: SEASON_WRITE_INTEGRATION=1 python -m pytest -p no:cacheprovider -q tests — 1034 passed / 41 skipped; Mongo-проверки записи сезонов включены на отдельной тестовой Mongo. Затем добавлены проверки новой одноимённой стадии, foreign/non-string markers и повторного game ID: tests/test_season_editor.py — 14 passed. Код после полного прогона менялся только комментарием.
- Production: CI=true REACT_APP_USE_API_PROXY=true yarn build — Compiled successfully.
- node scripts/sync-module-contract.cjs --check, node --check для browser-smoke/run.cjs и editors.cjs; git diff --check.
- Linux Playwright 1.62.1 noble / Chromium, настоящий backend и production frontend, собственная UUID-база на отдельной Mongo 8.0.32: полный browser smoke — exit 0. Существующие R8/R9 сценарии, публичные страницы и preview на 390/1120 сохраняются.
- Новый editors.cjs: галерея → изменить одну подпись → сохранить → открыть снова → сравнить весь modules JSON; клавиатурное DnD модуля с проверкой порядка и payload.
- Сезон: отмена существующего подтверждения замены шаблоном; изменить одну оценку → сохранить canonical API → открыть снова; весь editor_data равен исходному, кроме оценки и total. Затем клавиатурное DnD свёрнутых стадий и копирование игры из поздней стадии в раннюю: сохранение 200, разные canonical IDs, одинаковые данные и ссылки участников. Дополнительно повторная копия с тем же именем клавиатурой поставлена перед уже сохранённой копией до сохранения: 200, прежние IDs сохранены, новая копия получила отдельный ID.
- Для DnD smoke ждёт реальное сообщение dnd-kit о цели вместо короткой задержки. Перетаскивание огромной раскрытой стадии не включено в критерий: auto-scroll/изменение размеров делают такой сценарий нестабильным.
- Независимое read-only review обеих декомпозиций и заключительное отдельное review backend-reservations не выявили подтверждённых Critical/Important регрессий. Unit DOM использует mocks rich-text/selectors; browser smoke использует настоящие компоненты и API.

Локальные логи и скриншоты: .cache/r10-jest.log, r10-dialog-jest.log, r10-backend-pytest.log, r10-build.log и r10-acceptance/r10-*-editor.png (ignored). Это служебные артефакты, не часть коммита.

## Решение об удалении и ограничения

Согласовано пользователем 2026-10-21: сохранить текущее поведение удаления, новые подтверждения вынести в отдельную задачу. Модули, стадии, игры и команды удаляются сразу; существующее подтверждение замены большого сезона шаблоном сохранено. Копирование есть у игры, команды дублирования модуля в исходном UI нет. [Отдельный продуктовый бэклог](../KNOWN_ISSUES.md).

Раскрытие стадий/игр по-прежнему привязано к индексам: после перестановки раскрытой может оказаться другая позиция. Это прежнее UI-поведение, данные и callbacks адресуются правильно. Полный real-browser flow создания/редактирования poll отдельно не запускался; перенос проверен review и сборкой. Все виды форм не выдаются за вручную проверенные.

## Завершение

Тестовые UUID-базы очищены; оба набора одноразовых backend/Mongo-контейнеров, их анонимные тома и тестовая сеть удалены. Основной стек не перезапускался, main чистый, localhost:3000 и :8001/api/health возвращают 200.

Публикация: отдельный коммит R10 с документацией и push codex/local-page-builder по поручению пользователя 2026-10-21. Перед commit повторно проверены frontend 56 suites / 331 tests, backend identity 14/14, контракт и синтаксис smoke. Итоговый SHA и hosted CI фиксируются в протоколе следующего R11. Основной checkout остаётся на main; импорт 24СМИ и VPS не затрагиваются.
