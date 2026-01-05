# Универсальный модульный импортер

## Обзор

Универсальный импортер позволяет создавать скрипты импорта для любого типа контента,
просто указывая последовательность модулей на странице.

## Источники данных из БД

Парсер извлекает данные из следующих таблиц MySQL/MODX:

### Основные таблицы

- **`modx_site_content`** - основная таблица ресурсов:
  - `id` - ID ресурса
  - `pagetitle` - заголовок страницы
  - `longtitle` - расширенный заголовок
  - `description` - описание/HTML контент
  - `alias` - алиас (slug)
  - `parent` (индекс 12) - ID родительского ресурса (для иерархии)
  - `rating` - рейтинг (число от 0 до 10)
  - `votes` - количество голосов
  - `createdon`, `editedon`, `publishedon` - временные метки

- **`modx_site_tmplvar_contentvalues`** - значения TV переменных:
  - `contentid` - ID ресурса
  - `tmplvarid` - ID TV переменной
  - `value` - значение TV переменной

- **`modx_site_tmplvars`** - маппинг TV переменных:
  - `id` - ID TV переменной
  - `name` - название TV переменной (используется для конвертации ID → имя)

### Маппинги (JSON файлы)

- **`tag_mapping.json`** - маппинг `tag_id → tag_name` (для конвертации ID тегов в названия)
- **`image_mapping.json`** - маппинг `image_id/path → url` (для нормализации путей к изображениям)
- **`tv_map.json`** - маппинг `tv_id → tv_name` (для конвертации TV ID в имена полей)

### Источники данных для модулей

| Модуль | Источник данных |
|--------|----------------|
| `poster_photo` | TV поле `image` (или fallback: `photo`, `poster`, `img`), или первое изображение из HTML (`modx_site_content.description`) |
| `facts_table` | TV поле `config` → MIGX секция `info` → поле `table`, или HTML таблица из `description` |
| `rating_widget` | `modx_site_content.rating` и `modx_site_content.votes` |
| `tags_cloud` | TV поле `tags` (разделитель `||`), конвертация через `tag_mapping.json` |
| `social_links` | TV поле `config` → MIGX секция `info` → поле `list_social`, или ссылки из HTML |
| `text_block` | TV поле `config` → MIGX секции (`info.subtitle`, `text.content`, и т.д.), или HTML из `description` |
| `timeline` | TV поле `config` → MIGX секция `timeline` |
| `team_members` | TV поле с данными о составе команды |
| `image_gallery` | TV поле с массивом изображений |

**Примечание:** MIGX данные хранятся в TV поле `config` в формате JSON массива объектов с полями `MIGX_formname` (тип секции), `MIGX_id`, и различными полями в зависимости от типа секции (`subtitle`, `content`, `table`, `list_social`, и т.д.).

## Доступные модули

| Тип модуля | Описание | Основные параметры |
|------------|----------|-------------------|
| `poster_photo` | Фото/постер | `tv_field`, `size`, `shape` |
| `facts_table` | Таблица фактов | `tv_field`, `migx_section`, `style` |
| `rating_widget` | Рейтинг | `style` ('smileys', 'stars', 'numeric') |
| `tags_cloud` | Теги | `tv_field`, `delimiter`, `max_items`, `style` |
| `social_links` | Соцсети | `tv_field`, `style` |
| `text_block` | Текстовый блок | `tv_field`, `migx_section`, `migx_field`, `title` |
| `timeline` | Хронология | `tv_field`, `migx_section`, `title` |
| `team_members` | Состав команды | `tv_field`, `title` |
| `image_gallery` | Галерея | `tv_field`, `max_items`, `title` |

## Примеры использования

### Создание импортера для нового типа контента

```python
from universal_importer import UniversalImporter, ModuleConfig

# Импортер для статей
article_importer = UniversalImporter(
    content_type='article',
    collection='articles',
    modules=[
        ModuleConfig('poster_photo'),
        ModuleConfig('tags_cloud'),
        ModuleConfig('text_block', title='', all_sections=True),
        ModuleConfig('image_gallery', title='Фотографии'),
    ]
)

# Импорт одной статьи
doc = article_importer.import_resource(resource_id=5678, apply=True)
```

### Использование из командной строки

```bash
# Dry-run для шоу
python universal_importer.py --type show --ids 1629 --verbose

# Импорт человека
python universal_importer.py --type person --ids 350 --apply

# Импорт нескольких команд
python universal_importer.py --type team --ids 100,101,102 --apply

# Импорт всех новостей (parent=14) пакетами по 25 штук
python universal_importer.py --type news --parent-id 14 --batch-size 25 --apply

# Импорт всех статей (parent=29) пакетами по 10 штук
python universal_importer.py --type article --parent-id 29 --batch-size 10 --apply

# Импорт всех квизов (parent=31) пакетами по 25 штук (по умолчанию)
python universal_importer.py --type quiz --parent-id 31 --apply
```

### Иерархический импорт (дочерние страницы)

Для импорта дочернего контента (например, сезона шоу) используйте параметры
`--parent-slug` или `--parent-old-id`:

```bash
# Импорт сезона шоу по slug родителя
python universal_importer.py --type show --ids 1702 --parent-slug comedy-battle --apply

# Импорт сезона по старому ID родителя из MODX
python universal_importer.py --type show --ids 1702 --parent-old-id 1629 --apply
```

При иерархическом импорте автоматически устанавливаются:
- `parent_id` - ссылка на родительский документ
- `full_path` - полный путь (например: `comedy-battle/season9`)
- `level` - уровень вложенности (родитель + 1)

## Параметры ModuleConfig

### Общие параметры

- `type` - тип модуля (обязательный)
- `title` - заголовок модуля
- `visible` - видимость (по умолчанию True)

### Источники данных

- `tv_field` - название TV поля в MODX
- `migx_section` - название секции в MIGX JSON (например 'info', 'biography')
- `migx_field` - поле внутри секции MIGX (например 'subtitle', 'content')
- `html_selector` - регулярка для поиска в HTML контенте

### Специфичные параметры

- `style` - стиль отображения ('card', 'list', 'badges', 'icons', etc.)
- `delimiter` - разделитель для тегов (по умолчанию '||')
- `max_items` - лимит для тегов/изображений
- `strip_first_heading` - удалять первый заголовок если совпадает с названием
- `all_sections` - брать все секции MIGX кроме 'info'
- `exclude_keys` - ключи для исключения из таблицы фактов
- `fallback_tv_fields` - запасные TV поля для фото

## Создание кастомного импортера

Если вам нужен импортер для нового типа контента:

```python
from universal_importer import UniversalImporter, ModuleConfig

def create_quiz_importer():
    """Импортер для викторин."""
    return UniversalImporter(
        content_type='quiz',
        collection='quizzes',
        modules=[
            ModuleConfig('poster_photo', tv_field='quiz_image'),
            ModuleConfig('tags_cloud'),
            ModuleConfig('text_block', title='Описание', migx_section='intro'),
            # Добавьте свои модули
        ]
    )

# Использование
importer = create_quiz_importer()
doc = importer.import_resource(1234, apply=True)
```

## Расширение парсеров

Чтобы добавить новый тип модуля:

1. Создайте файл в `parsers/` с новым парсером
2. Унаследуйте от `BaseParser`
3. Реализуйте метод `parse(ctx) -> dict`
4. Добавьте в `__init__.py` и `PARSER_MAP` в `universal_importer.py`

Пример:

```python
# parsers/video.py
from .base import BaseParser, ParseContext

class VideoParser(BaseParser):
    module_type = "video_embed"
    default_title = "Видео"
    
    def parse(self, ctx: ParseContext) -> dict:
        # Ваша логика парсинга
        video_url = ctx.tv_data.get('video_url', '')
        return {
            'url': video_url,
            'title': self.config.get('title', self.default_title)
        }
```

## Типичный workflow

1. **Анализ страницы на humorpedia.ru** - определите какие блоки есть на странице
2. **Определите последовательность модулей** - порядок важен!
3. **Создайте конфигурацию** - укажите источники данных (TV поля, MIGX секции)
4. **Тестируйте с --verbose** - проверьте что парсится корректно
5. **Применяйте с --apply** - записывайте в MongoDB

## Пример запроса для создания нового импортера

> "Создай импортер для новостей. На странице: фото, дата публикации в таблице фактов, 
> теги, основной текст новости, галерея фото в конце"

```python
news_importer = UniversalImporter(
    content_type='news',
    collection='news',
    modules=[
        ModuleConfig('poster_photo'),
        ModuleConfig('facts_table', title=''),  # дата публикации
        ModuleConfig('tags_cloud'),
        ModuleConfig('text_block', title='', all_sections=True),
        ModuleConfig('image_gallery', title='Фотографии'),
    ]
)
```

## Готовые импортеры

### Новости (parent=14)

Импортер для новостей объединяет все секции (текст, таблицы, цитаты) в один текстовый блок.
Опциональное фото и теги.

```bash
# Импорт одной новости
python universal_importer.py --type news --ids 1234 --apply

# Импорт всех новостей (parent=14) пакетами
python universal_importer.py --type news --parent-id 14 --batch-size 25 --apply
```

### Статьи (parent=29)

Импортер для статей создаёт отдельные текстовые блоки для каждой секции, что позволяет
автоматически создать оглавление. Обязательное фото "шапки" и теги.

```bash
# Импорт одной статьи
python universal_importer.py --type article --ids 5678 --apply

# Импорт всех статей (parent=29) пакетами
python universal_importer.py --type article --parent-id 29 --batch-size 10 --apply
```

### Квизы (parent=31)

Импортер для квизов включает вопросы с вариантами ответов, результаты, изображение
страницы запуска и теги.

```bash
# Импорт одного квиза
python universal_importer.py --type quiz --ids 9012 --apply

# Импорт всех квизов (parent=31) пакетами
python universal_importer.py --type quiz --parent-id 31 --apply
```

### КВН (parent=32)

Импортер для страниц КВН поддерживает иерархическую структуру до 4 уровней вложенности.

#### Структура иерархии

КВН страницы имеют иерархическую структуру:
- **Уровень 0**: Корневая страница (например, "КВН", `parent=0` в MODX)
- **Уровень 1**: Лиги, сезоны (например, "Высшая лига", `parent=32`)
- **Уровень 2**: Конкретные сезоны (например, "Сезон 2024")
- **Уровень 3**: Игры, этапы
- **Уровень 4**: Конкретные игры

Иерархия определяется полем `parent` в таблице `modx_site_content` (индекс 12). При импорте автоматически устанавливаются:
- `parent_id` - MongoDB ID родительского документа (если указан `--parent-slug` или `--parent-old-id`)
- `full_path` - полный путь (например: `kvn/vysshaya-liga/season-2024`)
- `level` - уровень вложенности (0 для корневой страницы, +1 для каждого уровня)

#### Извлекаемые данные

Импортер извлекает следующие модули:

1. **`poster_photo`** - Постер/фото:
   - Источник: TV поле `image` (или fallback: `photo`, `poster`, `img`)
   - Альтернатива: первое изображение из HTML (`modx_site_content.description`)
   - Результат: преобразуется в формат `MediaFile` с полями `url`, `alt`, `caption`, `thumbnail`

2. **`facts_table`** - Таблица фактов (заголовок "Информация", стиль "card"):
   - Источник: TV поле `config` → MIGX секция `info` → поле `table`
   - Альтернатива: HTML таблица из `description`
   - Результат: словарь ключ-значение (например: "Год", "Лига", и т.д.)

3. **`rating_widget`** - Виджет рейтинга (заголовок "Оценка", стиль "smileys"):
   - Источник: `modx_site_content.rating` и `modx_site_content.votes`
   - Результат: объект `{average: float, count: int}`

4. **`tags_cloud`** - Облако тегов (стиль "badges"):
   - Источник: TV поле `tags` (разделитель `||`)
   - Конвертация: ID тегов → названия через `tag_mapping.json`
   - Результат: массив строк с названиями тегов

5. **`social_links`** - Социальные ссылки (заголовок "Ссылки", стиль "list"):
   - Источник: TV поле `config` → MIGX секция `info` → поле `list_social`
   - Формат: JSON массив объектов `[{"name": "vk", "link": "https://..."}, ...]` или словарь
   - Результат: словарь `{vk: url, youtube: url, ...}`

6. **`text_block`** (первый) - Основной текст из секции info:
   - Источник: TV поле `config` → MIGX секция `info` → поле `subtitle`
   - Параметры: `strip_first_heading=True` (удаляет первый заголовок, если совпадает с названием страницы)
   - Результат: HTML контент с нормализованными путями к изображениям

7. **`text_block`** (второй) - Все текстовые секции:
   - Источник: TV поле `config` → все MIGX секции с `MIGX_formname='text'`
   - Параметры: `all_text_sections=True`
   - Результат: отдельные модули для каждой `text` секции (с заголовками, если есть)

#### Специфичные поля для КВН

В документ MongoDB добавляются дополнительные поля:
- `name` - название (из `longtitle` или `pagetitle`)
- `child_kvn_ids` - массив ID дочерних страниц КВН (пустой при импорте, заполняется отдельно)
- `person_ids` - массив ID связанных людей (пустой при импорте)
- `team_ids` - массив ID связанных команд (пустой при импорте)
- `related_kvn_ids` - массив ID связанных страниц КВН (пустой при импорте)
- `poster` - преобразуется в формат `MediaFile` (если был строкой)

#### Использование

```bash
# Импорт корневой страницы КВН (id=32)
python universal_importer.py --type kvn --ids 32 --apply

# Импорт всех страниц КВН первого уровня (parent=32) пакетами
python universal_importer.py --type kvn --parent-id 32 --batch-size 25 --apply

# Импорт дочерней страницы с указанием родителя по slug
python universal_importer.py --type kvn --ids 1234 --parent-slug vysshaya-liga --apply

# Импорт дочерней страницы с указанием родителя по old_id из MODX
python universal_importer.py --type kvn --ids 1234 --parent-old-id 5678 --apply
```

#### Порядок импорта

1. **Сначала импортируйте корневую страницу** (если её нет в MongoDB):
   ```bash
   python universal_importer.py --type kvn --ids 32 --apply
   ```

2. **Затем импортируйте страницы по уровням** (сначала уровень 1, потом 2, и т.д.):
   ```bash
   # Уровень 1 (прямые дочерние корневой страницы)
   python universal_importer.py --type kvn --parent-id 32 --apply
   
   # Уровень 2 (дочерние страниц уровня 1) - для каждой родительской страницы
   python universal_importer.py --type kvn --ids 1234 --parent-slug vysshaya-liga --apply
   ```

3. **Или используйте пакетный импорт** для всех страниц с определённым `parent_id`:
   ```bash
   python universal_importer.py --type kvn --parent-id 32 --batch-size 25 --apply
   ```

**Важно:** При импорте дочерних страниц убедитесь, что родительская страница уже существует в MongoDB, иначе `parent_id` не будет установлен корректно.

## Импорт по parent_id

Вместо указания конкретных ID можно импортировать все ресурсы с определённым `parent_id`:

```bash
# Импорт всех новостей (parent=14) пакетами по 25 штук
python universal_importer.py --type news --parent-id 14 --batch-size 25 --apply

# Импорт всех статей (parent=29) пакетами по 10 штук
python universal_importer.py --type article --parent-id 29 --batch-size 10 --apply
```

**Параметры:**
- `--parent-id` - ID родительского ресурса в MODX (например, 14 для новостей, 29 для статей, 31 для квизов)
- `--batch-size` - размер пакета для обработки (по умолчанию: 25)

**Преимущества пакетной обработки:**
- Можно обработать все ресурсы одной командой
- Прогресс отображается по пакетам
- Можно контролировать размер пакета для оптимизации производительности
- При ошибке в одном ресурсе остальные продолжают обрабатываться