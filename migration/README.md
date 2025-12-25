# Миграция Humorpedia (актуальный процесс)

## Что это
В папке `/migration` лежат утилиты и основной скрипт импорта контента типа **people** из дампа MODX:
- источник: **`/app/humorbd.sql`**
- приёмник: MongoDB (по переменным `MONGO_URL`, `DB_NAME`)

Цели импорта:
- корректный HTML в текстовых блоках (без `\\n`, `\\"`, `\\/` и т.п.)
- 2 текстовых блока перед хронологией, если они есть в источнике:
  - **Биография**
  - **Личная жизнь**
- корректная хронология (timeline) для редактирования в админке
- корректные фото в формате URL: **`/media/imported/...`**
- корректный рейтинг: `average` (0..10) и `count` (кол-во голосов)

---

## Основные файлы

```
/migration/
├── README.md                  # этот файл
├── people_list.json           # мастер-список people для импорта (status=pending/imported/ignored)
├── image_mapping.json         # маппинг исходных путей images/... -> /media/imported/...
├── import_people_from_sql.py  # ✅ основной быстрый импорт people из humorbd.sql
├── utils.py                   # общие утилиты и сборка схемы person
└── ... (вспомогательные/старые скрипты)
```

**Важно:** старые скрипты `import_people.py` / `extract_from_sql.py` больше не являются основным путём. Используйте `import_people_from_sql.py`.

---

## Модель данных (важные поля)

### Person (people)
Ключевые поля:
- `content_type: "person"`
- `slug`
- `title`, `full_name`
- `image` — URL картинки (должен быть **`/media/imported/...`**)
- `modules[]` — модульный контент
- `rating: { average, count }`

### modules
Важное:
- `module.title` — показывается в админке в списке модулей
- `module.data.title` — заголовок внутри текстового блока

Типичный набор модулей для people:
1) `text_block` (Биография)
2) `text_block` (Личная жизнь) — если есть
3) `timeline` (Хронология)

---

## Подготовка

1) Убедитесь, что дамп лежит здесь:
- `/app/humorbd.sql`

2) Убедитесь, что картинки лежат здесь:
- `frontend/public/media/imported/...`

3) Проверьте наличие `image_mapping.json`:
- `/migration/image_mapping.json`

---

## Как импортировать

### Вариант A — импорт из people_list.json (рекомендуется)
Скрипт берёт первые `pending` записи из `people_list.json`.

```bash
cd /app/migration
python3 import_people_from_sql.py --from-list --limit 10 --apply
```

После этого обычно нужно пометить их как `imported` в `people_list.json`.
(В нашей сборке это делалось отдельным шагом, чтобы можно было контролировать процесс.)

### Вариант B — импорт конкретных id
```bash
cd /app/migration
python3 import_people_from_sql.py --ids 115 116 117 --apply
```

### Обновление уже импортированных записей
Полная перезапись документа (replace) используется для того, чтобы «подтянуть» улучшения парсинга (хронология, 2 текстовых блока, фото URL, рейтинг/votes).

```bash
cd /app/migration
python3 import_people_from_sql.py --ids 115 116 117 --apply --update
```

**Важно:** `--update` не должен затирать фото — скрипт умеет сохранять старое `image`, если новое не найдено.

---

## Игнорирование «не-людей» в people_list.json
Иногда в `people_list.json` могут попасть страницы-разделы/лендинги, которые не являются персоной.
В таком случае:
- удалите такую запись из MongoDB (коллекция `people`)
- поставьте ей `status: "ignored"` в `people_list.json`, чтобы она не попадала в следующие пачки.

---

## Docker (DEV)
Если запускаете проект через docker compose (dev):

- Frontend: http://localhost:3000
- Backend:  http://localhost:8001

Импорт можно запускать:

### С хоста
```bash
python3 migration/import_people_from_sql.py --from-list --limit 10 --apply
```

### Внутри контейнера backend
```bash
docker compose exec backend python3 /app/migration/import_people_from_sql.py --from-list --limit 10 --apply
```

---

## Быстрые проверки после импорта

1) Открыть публичную страницу:
- `http://localhost:3000/people/<slug>`

2) Проверить админку:
- `http://localhost:3000/admin/people/<_id>` → вкладка «Модули»

3) Проверить, что картинка имеет вид:
- `/media/imported/...`

4) Проверить рейтинг:
- `rating.average` в диапазоне 0..10
- `rating.count` — число голосов
