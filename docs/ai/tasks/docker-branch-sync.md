# Локальный Docker следует текущей ветке

Дата проверки: 2026-10-03. Ветка реализации: `codex/docker-branch-sync`, основа — `73a7d7902ed8cc02bdbc8855e172f5fb7a08073d` (`origin/main` после PR #55).

## Результат

- Repo-local hooks установлены в `.git/humorpedia-dev-hooks`; синхронизируют только основной checkout после branch checkout и локального merge. Установленная копия скрипта работает и на ветках без новых файлов.
- После удалённого merge Codex вызывает `dev-finish.ps1 -PullRequest <номер>`: проверка PR/HEAD, fetched main, fast-forward и sync. Для локального Git merge — проверка ancestor без номера PR.
- Хеши входных файлов, эффективной Compose-конфигурации и образы позволяют пропустить лишнюю сборку; только хеш конфигурации хранится, её содержимое не записывается.
- Статус проверяет mounts, images, Mongo health и HTTP availability. Изменённый экран/API всё ещё требует отдельной проверки.
- MongoDB и медиа не сбрасываются, миграции не запускаются. Автоматическая смена образа существующего MongoDB запрещена до build/stop/up. Dirty/diverged/unmerged состояния останавливают возврат без автоматического stash/reset/clean.

Команды и ограничения: [DOCKER_DEV.md](../../../DOCKER_DEV.md). Правила завершения merge: [AGENTS.md](../../../AGENTS.md).

## Проверки

- 35 assertions в изолированном Git fixture: PowerShell 5.1 и PowerShell 7. Покрыты hooks, scope worktree, sync failure, lock, общие PS5/PS7 хеши, зависимости и LF/CRLF, чужой image tag/mount, Compose env override, запрет автоматической смены MongoDB image, dirty/unmerged guards, удалённый merge и squash.
- Backend: 428 passed; frontend: 196 passed / 34 suites; module contract и diff-check прошли.
- Настоящий Docker: полный sync и повторный `-Auto`, обе HTTP-проверки, compose ps, mounts и status прошли.
- Ручной UI в браузере не проверялся: пользовательские страницы этой задачей не изменялись.

## Сохранённое исходное состояние

Перед переводом старого checkout на актуальную основу сохранены все 47 незакоммиченных файлов в stash `7d8d6c37159eedef89b16be2124dbb911118ff97` с описанием `Safety snapshot before Docker branch automation 2026-10-03`. Это резервная копия прежнего состояния на `codex/kvn-season-import`; основной код этих изменений уже включён в PR #55. Stash не удалялся и автоматически не применяется.
