# R9: публичный рендеринг

Обновлено: 2026-10-21. Ветка codex/local-page-builder, HEAD до изменений R9: b67aacb73da477863ea1a739068ef4308d41ad63. Статус: опубликовано отдельным коммитом df6e0191938a8b484579fb3b4aa92b1efe74fe9b. Итоговый CI после исправлений helper/browser smoke — [39655534921](https://github.com/AMnEPka/humorpedia/actions/runs/39655534921), все пять jobs прошли на 43d61dd. [Причины и исправления CI](ci-workflow-recovery-2026-10-21.md).

CI и R8 опубликованы раздельно: 5d369dd и b67aacb. [GitHub Actions на итоговом SHA](https://github.com/AMnEPka/humorpedia/actions/runs/39611516778) завершился успешно: backend, frontend, mongodb-integration, windows-tools, browser-smoke.

## Границы и решения

Основание — утверждённый [план R9](project-refactoring-plan-2026-10-21.md). Сохраняем поведение страниц и тот же renderer в preview конструктора. Основной checkout/стенд остаётся на main; импорт 24СМИ и VPS не затрагиваются.

Общий выбор модулей сохраняет stable order, visible, неизвестные блоки и исключения preview. Доменные исключения игр/состава/проектов команд остаются у TeamDetailPage. Извлекаем только повторяющиеся каркас текстового блока и загрузку; различающиеся хронологии остаются у страниц вместе с их якорями.

Backend JSON остаётся единственным редактируемым реестром. Добавочное rendering описывает owner, placement и preview. Существующие kind, owners, поля документов и API записи не меняются. season_data — владелец страницы SeasonDetailPage, отдельного типа модуля season нет; архивные modules не рендерятся.

## Шаги и проверка

1. Реестр и контрактные тесты — Luna/high, ограниченная независимая подзадача.
2. Общий selection, текстовый каркас, загрузка и интеграция страниц — Sol/high.
3. Приёмка — Sol/high: frontend contracts/unit и production build, backend registry/API, настоящий browser smoke публичных страниц и preview на 390/1120 px; season_data и quiz сохраняют отдельных владельцев.

## Состояние

Реализованы registry metadata, moduleSelection, TextModuleCard, PageLoading (пять detail-страниц), moduleNavigation и подключения в Person/Team/Show. SectionDetailPage сохраняет отдельный SeasonDetailPage; QuizDetailPage сохраняет gameplay и дополнительные модули. Конструктор использует прежние публичные страницы через портал, отдельной копии renderer нет.

Браузер воспроизвёл прежний дефект: TOC preview искал якорь в глобальном document админки, а не в документе iframe. Общий scrollToModule теперь использует ownerDocument кнопки. Публичный TOC, iframe TOC и уникальность целевых ID проверены после исправления.

В промежуточной реализации review обнаружил два регресса: modules:null и lookup неизвестных типов constructor/toString/__proto__. Они устранены до приёмки, закреплены тестами. Данные и якоря не мигрировались.

## Приёмка 21.10.2026

- RED: новые selection/TextModuleCard tests упали до реализации; отдельно воспроизведены null modules и prototype lookup. Затем frontend: 309 passed / 50 suites, production CI build — успешно. После исправления TOC повторены те же tests/build, результат прежний.
- Backend: pytest tests/test_module_contract.py — 55 passed, 4 прежних предупреждения. Проверены registry/enum, API metadata, создание/чтение/изменение модулей и совместимость дополнительных полей. Полный backend-набор 1058 passed / 15 skipped и hosted integration ранее пройдены на опубликованном R8; повтор всего набора после добавочного registry metadata не требовался.
- node scripts/sync-module-contract.cjs --check, node --check для smoke scripts, git diff --check — успешно.
- Настоящий Chrome через Playwright 1.62.1, production build, отдельная MongoDB 8.0.32 без подключения к основной БД: весь run.cjs — exit 0. Включены старые ZIP/search и R8 season сценарии, затем новый modules.cjs.
- На 390/1120: person/team/show публично и внутри реального iframe конструктора; порядок, visible, текст/заголовки без дублей, загруженная gallery, table, хронология/TOC, факты, участники и раскрываемый show text, отсутствие горизонтального переполнения. Draft содержит rating_widget: нет блока оценки и requests к ratings API.
- Video как безопасная внешняя ссылка проверен публично; общий video renderer (включая iframe), unknown и poll/random/quiz preview exclusions — unit/SSR. Конструктор по прежнему контракту не принимает video/poll/random/quiz; разрешённый набор не расширялся.
- Season_data выводится без архивного текста modules; quiz сохраняет порядок вступления, скрытые блоки, вопрос → правильный ответ → результат. Обе ширины. Необработанных browser errors нет.
- 16 скриншотов R9 и два прежних smoke screenshots сохранены в игнорируемой .cache/r9-acceptance-2026-10-21; выборочно просмотрены person mobile preview, team desktop preview и show desktop public. Это синтетические данные без рабочих медиа; site-wide placeholders могут возвращать 404 в изолированной среде.
- Main чистый, HEAD ca46155; ID, StartedAt и RestartCount трёх основных контейнеров совпадают с началом работы. localhost:3000 и localhost:8001/api/health — HTTP 200. Основной стек не перезапускался.
- Smoke сервер корректно остановлен; перед удалением своей Mongo подтверждено, что остались только admin/config/local. Свои Mongo, две anonymous volumes и сеть удалены. Артефакты приёмки сохранены отдельно от очищенного temp.

## Доставка и продолжение

CI и R8 ранее опубликованы отдельными коммитами. По поручению пользователя R9 с этой документацией публикуется следующим отдельным коммитом в codex/local-page-builder. Перед коммитом повторно проверены source fingerprints приёмки, sync-module-contract, синтаксис smoke scripts и diff; код после приёмки не менялся. Итоговый SHA и hosted CI фиксируются в задаче R10 после push. Импорт 24СМИ, основной main и VPS не менялись. Следующий пункт — R10 в том же worktree после проверки CI.
