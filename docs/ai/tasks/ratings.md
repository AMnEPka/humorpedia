# Восстановление рейтингов

Дата: 2026-09-18

Ветка: `codex/ratings`

Базовый HEAD: `1cf3ee93815e1252ea3b76df45f95cbadf15fb5b`

## Результат

- Статьи, люди, команды и шоу получают единый публичный рейтинг от 1 до 10 со смайликами.
- Среднее — обычное арифметическое, отображается с одним знаком после запятой.
- Вместо точного числа голосов API и UI показывают только вехи: менее 50, 50+, 100+, 250+, 500+, 1000+.
- Авторизация не требуется. Подписанная HttpOnly-cookie определяет анонимного посетителя; повторная оценка этой страницы заменяет прежнюю и не увеличивает число голосов.
- Исторические агрегаты сохранены как неизменяемая взвешенная база, новые голоса хранятся отдельно.

## Основные файлы

- Backend: `models/rating.py`, `routes/ratings.py`, `services/ratings.py`, `scripts/migrate_ratings.py`.
- Frontend: `public/components/RatingCard.jsx`, `public/hooks/useRating.js`, методы ratings в `public/utils/api.js` и четыре detail-страницы.
- Проверки: `tests/test_ratings.py`, публичный write-маршрут явно зарегистрирован в `tests/test_auth_guards.py`.

## Миграция локальной БД

`python scripts/migrate_ratings.py --apply` создал 2650 baseline-документов: статьи — 66, люди — 1039,
команды — 1288, шоу — 257. Повторный dry-run: `created=0`, `existing=2650`.

## Проверка готовности

- Targeted backend: `tests/test_ratings.py tests/test_auth_guards.py` — 131 passed.
- Live API: backend healthy; рейтинг существующего человека 200, `private, no-store`, `Vary: Cookie`, подписанная HttpOnly-cookie; frontend после перезапуска отвечает 200.
- Полный backend suite: `pytest tests -q` — 306 passed, 4 внешних deprecation warnings.
- Frontend production build: успешно; остались 5 ранее существовавших ESLint warnings в других компонентах.

## Ограничение механизма

Cookie-защита достаточно проста для обычной перезагрузки, повторной отправки и случайного дубля, но намеренно не является
строгой идентификацией человека: очистка cookie, другой браузер или приватное окно создадут нового анонимного посетителя.
Усиление через fingerprint/IP не добавлялось из-за ложных совпадений, персональных данных и сложности эксплуатации.
