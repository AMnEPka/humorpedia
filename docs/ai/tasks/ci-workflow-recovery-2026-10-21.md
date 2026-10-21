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

До коммита: actionlint, bash -n, реальный helper на изолированной Mongo и random loopback порту. Результаты hosted CI будут записаны после push; локальный запуск не доказывает работу на ядре hosted runner.

Проверка перед публикацией: actionlint с ShellCheck, bash -n и реальный helper прошли. Дополнительно разделены присваивание SMOKE_RUN_ID и export (SC2155), чтобы ошибка генератора не маскировалась export. Mongo ответила на ping на отдельном random loopback порту; основной стек не перезапускался.
