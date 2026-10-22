# R13e: исправление запуска gateway в CI

Дата: 22.10.2026. Базовый HEAD 4e94eba69be3a9a4c90b4de85d6d9513eb1fa6c4, ветка codex/local-page-builder. Дополнительное исправление CI входит в поручение проверить опубликованный R13e; R13f-документы/материалы в этот коммит не включаются.

[Run39824229497](https://github.com/AMnEPka/humorpedia/actions/runs/39824229497) проверил точный R13e SHA: backend, mongodb-integration, frontend, windows-tools success; оба старых browser steps success, native gateway failure.

Из CI artifacts: собственная Mongo8.0.32 завершилась с ExitCode1/OOMKilled=false через172мс после старта, до запуска backend. Backend затем не мог разрешить/достичь mongo:27017. Первопричина выхода Mongo не доказана: harness не сохранял её журнал до удаления. Связывать ошибку только с медленным стартом или утверждать доказанный rseq crash нельзя.

Подтверждённые пробелы и минимальная коррекция:
- Новый запуск пропустил существующий seccomp-профиль, используемый рабочим scripts/ci/start-mongodb.sh на том же GitHub runner. Применён тот же профиль без изменения Mongo8.0.32, томов/портов или изоляции.
- После detached start не было ожидания готовности. Добавлено ограниченное ожидание ping, проверка Running и журнал при раннем выходе; mongosh работает как mongodb с HOME=/tmp, не создаёт конфигурацию внутри db tmpfs.
- Первая загрузка Playwright image происходила внутри300s browser timeout. Теперь отсутствующий pinned image загружается до создания тестовой сети/запуска сервисов с отдельным600s лимитом. Сам browser timeout остаётся300s.

RED: два новых теста readiness падали из-за отсутствующей функции. GREEN: все4 Node gateway-tools tests; прежние UUID/timeout/signal проверки сохранены. Реальный локальный gateway smoke PASS во всех трёх режимах (UUID a57c6acf7e074131b77f0676fc332859); result.json passed, cleanup.json error=null/containers=[], сеть и образы удалены. Hosted run нового SHA проверяется после отдельного commit/push.

Существующие GitHub artifact patterns включили gateway evidence; изменение upload settings не потребовалось. Изменения продукта, основного стенда, импорта24СМИ, VPS и настроек production не выполнялись. При ошибке startup следующий run выдаст сам журнал Mongo до запуска browser, а не вторичную DNS/UUID ошибку.
