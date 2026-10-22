# Performance Optimizations

## Актуальные измерения и приёмка R11 (22.10.2026)

Локальная копия 16 коллекций / 31 571 документа: ограничены чтения соседних сезонов,
добавлены индексы ссылок команд и сортировки рекомендаций. Результаты API прежние.
Приёмка R11 завершена 22.10 по согласованному критерию: положительные дельты ниже A/A-разброса, воспроизводимое ухудшение не обнаружено. [Таблицы до/после и проверки](docs/ai/tasks/r11-performance-2026-10-21.md).

Исторические оценки ниже («~1M посещений», «40–60%», «10–50x») не подтверждены текущим
нагрузочным тестом. Текущий публичный поиск использует также regex; утверждение о переводе
всех путей на text search не следует считать текущим контрактом.

### Воспроизводимый локальный профиль API

1. Подготовить отдельную MongoDB той же версии, собственные сеть/тома, копию нужного контента
   и исходных индексов. Имя — `humorpedia_perf_<32 hex символа>`. Не использовать основную БД.
   Сохранить manifest counts/SHA256 до/после; не копировать users, секреты и редакционные очереди.
2. Создать пользователя с **единственной ролью `read` именно копии**. Передать его URI
   через `MONGO_URL` и необходимые приложению `JWT_SECRET`/настройки через окружение.
   CLI не выводит URI и не создаёт индексы/миграции; подготовка копии выполняется отдельно.
3. Подготовить JSON-план с существующими в копии slug/ID. Разрешены поиск, people/teams
   catalog/detail, kvn/by-path, канонические сезоны и recommendations. Только GET:

~~~json
[
  {"name":"search","path":"/api/content/search?q=Иван&limit=10"},
  {"name":"people","path":"/api/content/people?limit=20"},
  {"name":"person","path":"/api/content/people/garik-martirosyan"},
  {"name":"season","path":"/api/content/kvn/by-path/kvn/vl-kvn/vl-2025"},
  {"name":"recommendations","path":"/api/recommendations?content_type=person&content_id=garik-martirosyan"}
]
~~~

4. Из `backend` в установленном backend-окружении выполнить:

~~~sh
python scripts/profile_api.py --db-name humorpedia_perf_0123456789abcdef0123456789abcdef --plan /path/plan.json --samples 100 --without-rate-limit --timing-only --label before --output /path/before.json
~~~

`--without-rate-limit` нужен для частного in-process benchmark, превышающего обычный лимит
(поиск 60/min). По умолчанию limiter включён; флаг временно меняет singleton внутри CLI и
восстанавливает значение при выходе. Работающий стенд не меняется. CLI не является HTTP-сервером.

5. На той же копии применить проверяемый код и только его индексы отдельно от CLI; повторить
   с теми же планом, samples и датой/данными рекомендаций. Проверить content SHA256.
   Не запускать tests/backup параллельно timed серии. Сохранять все серии, не выбирать удачную. Обе версии запускать из одинаковой файловой системы и пути, с одинаковыми CPU affinity и Python hash seed.

Для приёмочного latency сравнения используется `--timing-only`: Mongo CommandListener
вообще не регистрируется, query metrics имеют `null` (не ноль), explain пуст. Клиентский
HTTPX INFO-журнал выключен на время CLI; исходный уровень восстанавливается при выходе.
Счётчики/explain собирать отдельным вызовом **без** `--timing-only` и не выдавать его latency
за приёмочную. Schema v2 сообщает `measurement_mode` и `query_metrics_collected`.
Каждый sample содержит `started_at_unix_ns` для сопоставления с отдельной диагностикой.

Порядок и число блоков фиксировать до измерения. Для итоговой серии R11: BA AB BA AB BA, пять блоков
на версию × 100 cold/warm на маршрут, fresh process на блок. Не отключать GC, не исключать
выбросы, сохранять все серии. p95 считать по объединённым равным samples каждого маршрута
и режима; p95 отдельных блоков/контрольный A/A разброс показывать дополнительно.

Критерий R11 согласован пользователем 22.10.2026: учитывать измеренный разброс одинакового
кода и принимать только при отсутствии воспроизводимого ухудшения с явными цифрами/границами.
Это не требование буквальных 0% изменения каждого наблюдаемого p95 и не production SLA.
Итог R11: все девять положительных Δ ниже A/A-разброса и имеют CI95 с нулём;
500 запросов на вариант/маршрут/режим, исходные таблицы и ограничения сохранены в отчёте.

Cold очищает кэш приложения перед каждым запросом, не OS/WiredTiger. Warm — один прогрев
и серия без очистки. ASGITransport вызывает настоящий `server.app` без lifespan, сокета/proxy
и flush просмотров; read-роль запрещает записи. Это backend/driver одного процесса,
не production/VPS нагрузка и не браузерное время.

Отчёт: p50/p95, payload, логические Mongo-команды и отдельно getMore, CPU, RSS, explain.
Explain выполняется после замера и относится к полному запросу без клиентского `to_list(n)`;
`aggregate_cursor` — вход pipeline. CPU — `process_time` профилировщика, не Mongo/хоста;
RSS — после обработки ответа, `ru_maxrss` — максимум за жизнь процесса, не пик запроса.
Raw response SHA и content SHA разделены: только корневой `/team_data_version` kvn/by-path
исключён из content SHA как динамический stamp; прочие поля и порядок массивов проверяются.
Ошибка роли/маршрута или не-200 завершает CLI без отчёта об успехе.

---

## Историческое описание оптимизаций (требует актуальной проверки)

### 1. Frontend Code Splitting ✅
**Цель**: Уменьшение размера начального бандла JavaScript

**Реализация**:
- Критические компоненты (HomePage, SectionDetailPage, PublicLayout) загружаются синхронно
- Публичные страницы (новости, статьи, команды и т.д.) загружаются lazy с помощью `React.lazy`
- Вся админка вынесена в отдельный lazy chunk
- Используется `Suspense` с fallback спиннером для плавной загрузки

**Результат**: 
- Начальный bundle сокращён на ~40-60%
- Пользователи публичного сайта не загружают код админки
- Faster Time to Interactive (TTI)

**Файл**: `/app/frontend/src/App.js`

---

### 2. MongoDB Text Indexes ✅
**Цель**: Масштабируемый полнотекстовый поиск вместо медленного `$regex`

**Реализация**:
- Созданы text индексы для всех коллекций:
  - `people`: title, full_name
  - `teams`: name, title
  - `shows`: name, title
  - `articles`: title
  - `news`: title
  - `wiki`: title
  - `kvn`: name, title
  - `sections`: title, description
  
- Все поисковые эндпоинты переведены на `$text` search:
  - `/api/content/search-for-links` (для редактора)
  - `/api/content/search` (публичный)
  - `/api/content/search/autocomplete`

**Результат**:
- Поиск работает в 10-50x быстрее на больших объёмах
- `$regex` сканировал всю коллекцию, text index — только индекс
- Поддержка морфологии и стоп-слов (MongoDB)

**Файлы**: 
- `/app/backend/server.py` (создание индексов)
- `/app/backend/routes/content_search.py` (использование)

---

### 3. MongoDB Connection Pooling ✅
**Цель**: Эффективное использование соединений под нагрузкой

**Конфигурация**:
```python
AsyncIOMotorClient(
    mongo_url,
    maxPoolSize=50,          # До 50 одновременных соединений
    minPoolSize=10,          # Всегда поддерживать 10 соединений
    maxIdleTimeMS=45000,     # Закрывать idle соединения через 45s
    serverSelectionTimeoutMS=5000,  # 5s таймаут выбора сервера
)
```

**Результат**:
- Переиспользование соединений вместо создания новых
- Минимизация overhead на подключение к MongoDB
- Защита от исчерпания соединений при пиковых нагрузках

**Файл**: `/app/backend/utils/database.py`

---

### 4. API Rate Limiting ✅
**Цель**: Защита от DDoS атак и злоупотреблений

**Реализация**:
- Библиотека: `slowapi` (FastAPI-compatible)
- Глобальный лимит: 1000 запросов/минуту с одного IP
- Специальные лимиты для публичных эндпоинтов:
  - Публичный поиск: 60/минуту
  - Autocomplete: 120/минуту (для быстрого набора)
  - Root endpoint: 100/минуту

**Результат**:
- Защита от DDoS и bot-атак
- Честное распределение ресурсов между пользователями
- Автоматический HTTP 429 ответ при превышении лимитов

**Файлы**:
- `/app/backend/server.py` (глобальная настройка)
- `/app/backend/routes/content_search.py` (применение к эндпоинтам)

---

## Ранее реализованные оптимизации (предыдущий агент)

### 5. TTL In-Memory Caching
- `cachetools` для кеширования API ответов
- TTL: 60s для большинства эндпоинтов
- Cache-Control: `max-age=60, stale-while-revalidate=30`

**Файл**: `/app/backend/services/cache.py`

### 6. Batched Views Counter
- Счётчики просмотров обновляются батчами каждые 30s
- Вместо N записей в БД → 1 bulk update
- Фоновая задача с graceful shutdown

**Файл**: `/app/backend/services/views_counter.py`

### 7. Remove Write-on-Read Anti-Pattern
- Убрали инкремент `views` при каждом чтении команды
- Добавлены отдельные `/refresh` эндпоинты для автор-обновления
- Чтение команды теперь чистое без side-effects

**Файл**: `/app/backend/routes/content_teams.py`

### 8. Batched LinkResolver
- HTML-ссылки резолвятся батчами вместо N+1 запросов
- Один запрос в БД для всех ссылок в тексте

**Файл**: `/app/backend/services/link_resolver.py`

### 9. MongoDB Compound Indexes
- Compound индексы для частых запросов:
  - `(status, name)` для команд
  - `(parent_id, status)` для КВН
  - `(season_data.league_slug, season_data.year)` для лиг

**Файл**: `/app/backend/server.py`

---

## Метрики производительности

### До оптимизации:
- Поиск по 1000 команд: ~300-500ms (`$regex`)
- Initial JS bundle: ~800KB
- Каждое чтение команды → запись в БД
- Соединений с MongoDB: 1-5 (создаются по требованию)

### После оптимизации:
- Поиск по 1000 команд: ~20-50ms (text index)
- Initial JS bundle: ~300KB (критический путь)
- Чтение команды → чистое чтение, батчинг views
- MongoDB connection pool: 10-50 (переиспользуются)
- Rate limiting: защита от перегрузок

---

## Рекомендации для дальнейшей оптимизации

1. **CDN для статики** - изображения, CSS, JS бандлы
2. **Redis/Memcached** - для distributed кеширования (если несколько инстансов)
3. **Nginx reverse proxy** - для статики и балансировки нагрузки
4. **Database read replicas** - для распределения read нагрузки
5. **Load testing** - симуляция 1M посещений/месяц для bottleneck анализа
6. **Monitoring** - Prometheus + Grafana для метрик в реальном времени
