# CI: восстановление запуска workflow

Дата: 21.10.2026. Ветка codex/local-page-builder, исходный HEAD 85ba090.
Основной checkout остаётся на main ca46155; VPS и импорт источников не меняются.

## Причины

- [Main run 39571996187](https://github.com/AMnEPka/humorpedia/actions/runs/39571996187): backend падает в Initialize containers до pytest. MongoDB 8.0.32 отказывается стартовать на новом ядре runner (Linux 6.19+). Причина tcmalloc/rseq описана в [SERVER-121912](https://jira.mongodb.org/browse/SERVER-121912); [исходник r8.0.32](https://github.com/mongodb/mongo/blob/r8.0.32/src/mongo/db/startup_check_rseq.cpp) проверяет активность per-CPU cache перед отказом.
- [R7 run 39600411894](https://github.com/AMnEPka/humorpedia/actions/runs/39600411894): jobs отсутствуют, gh сообщает workflow file issue. Actionlint воспроизводит недопустимые job.services.mongodb.id и runner.temp в job-level env.

## Исправление

MongoDB запускается после checkout через scripts/ci/start-mongodb.sh с существующим seccomp-профилем, запрещающим rseq. Версия Mongo остаётся 8.0.32. Readiness ограничен 60 секундами; helper экспортирует loopback MONGO_URL и точный ID. Cleanup always удаляет только свой контейнер и anonymous volumes. runner.temp перенесён на уровень шага. Для shell helper закреплены LF.

У ветки нет PR, а прежний push trigger допускал только main. Для проверки этой публикации добавлен push trigger ровно для codex/local-page-builder. Основной checkout не переключается; выкладки нет.

## Проверки и публикация

До коммита: actionlint, bash -n, реальный helper на изолированной Mongo и random loopback порту. После push проверен [run 39611516778](https://github.com/AMnEPka/humorpedia/actions/runs/39611516778) на b67aacb: completed/success. Все пять jobs прошли; MongoDB стартовала на hosted runner и интеграция/browser smoke дошли до тестов. Исправление CI опубликовано отдельным коммитом 5d369dd.

Проверка перед публикацией: actionlint с ShellCheck, bash -n и реальный helper прошли. Дополнительно разделены присваивание SMOKE_RUN_ID и export (SC2155), чтобы ошибка генератора не маскировалась export. Mongo ответила на ping на отдельном random loopback порту; основной стек не перезапускался.

## Проверка публикации R9: 21.10.2026

R9 опубликован отдельным коммитом df6e019. В [run 39653188277](https://github.com/AMnEPka/humorpedia/actions/runs/39653188277) backend/frontend/windows-tools прошли, найдены два отдельных дефекта CI:

- Mongo readiness запускал mongosh от root с HOME=/data/db из официального образа. Во время стартового find/chown исчез lock-файл .mongodb/mongosh/am-unknown.json.lock; entrypoint завершился до тестов. Локальный запуск прежнего helper подтвердил запись shell-state в каталог данных. Проба теперь запускается пользователем mongodb с HOME=/tmp, вне каталогов chown; версия Mongo и seccomp не меняются.
- Browser smoke успешно прокручивал iframe, но зависал на waitForFunction. Проверка по видимости цели вместо точной верхней позиции сама по себе проблему не решила: [run 39654112457](https://github.com/AMnEPka/humorpedia/actions/runs/39654112457) подтвердил Mongo/backend/frontend/windows, browser остался красным. Первичная гипотеза о пиксельном условии не подтвердилась.

Исправления опубликованы отдельными CI-коммитами 2e0a050 (Mongo readiness и первая проверка геометрии) и 43d61dd (Node polling вместо frame-local RAF). R9 не переписывался. [Итоговый run 39655534921](https://github.com/AMnEPka/humorpedia/actions/runs/39655534921) на 43d61dd завершился completed/success: backend, frontend, mongodb-integration, windows-tools и browser-smoke прошли.

Локальное воспроизведение в официальном Playwright 1.62.1 noble/Chromium на том же production artifact дало после timeout: top=154, bottom=242, viewport=650 — предикат истинен; отдельный requestAnimationFrame probe остался 0. Причина — frame-local RAF polling в preview с запрещёнными скриптами. Теперь Node опрашивает геометрию через evaluate и собственный таймер; browser sandbox не ослабляется. Тест сохраняет сброс прокрутки перед кликом и проверку полной видимости якоря. Ошибочный поиск якоря в глобальном document по-прежнему не проходит мобильный сценарий.

Проверка исправления: полный browser smoke в Linux Playwright 1.62.1 noble на том же frontend artifact — exit 0, все R8/R9 сценарии, 390/1120 и sandboxed preview. bash -n, ShellCheck и actionlint прошли; реальный helper сохраняет mongosh state только в /tmp. Основной стек не перезапускался.

## Проверка публикации R11: 22.10.2026

R11 опубликован отдельным коммитом `857508f`. В [run 39732001689](https://github.com/AMnEPka/humorpedia/actions/runs/39732001689) backend, frontend, windows-tools и mongodb-integration прошли. Browser smoke прошёл R8/R9 и модульный редактор, но не дождался перемещения `game-0-2` над `game-0-1`.

Полный исходный smoke на точном frontend artifact этого запуска локально прошёл. Контроль с замедлением CPU Chromium ×8: 8/8 непосредственных перемещений и 8/8 перемещений с ожиданием готовности прошли. Точная причина единственного сбоя hosted runner не воспроизведена; дефект продукта не подтверждён.

При этом исходник установленного dnd-kit 6.3.1 подтверждает недостаток синхронизации проверки: KeyboardSensor подключает keydown через setTimeout, а координаты областей вычисляются после активации. Теперь все три keyboard DnD сценария ждут начальную коллизию с собственной областью, затем целевую коллизию и drop. Ожидание начальной коллизии, в отличие от одного picked-up, также подтверждает готовность геометрии. Фиксированные паузы в сценарии модулей удалены; стрелка отправляется один раз, без повторов. Сравнения порядка, идентичностей и полного JSON после сохранения сохранены. Продуктовый код не меняется.
Проверка изменения: node --check и полный Linux browser smoke на точном CI frontend artifact, с новой UUID-базой — exit 0, все сценарии R8/R9/R10 и сравнения JSON прошли. Основной стек не перезапускался. Проверка GitHub будет зафиксирована после публикации отдельного CI-коммита.

Итог публикации: отдельный CI-коммит `8aa370d9583f4796bd53a98a711a6c7eb955b759` запушен в `codex/local-page-builder`. [Run 39733689132](https://github.com/AMnEPka/humorpedia/actions/runs/39733689132): completed/success, backend, frontend, windows-tools, mongodb-integration и browser-smoke — success.
