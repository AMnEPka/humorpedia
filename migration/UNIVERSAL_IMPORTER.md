# Универсальный модульный импортер

## Обзор

Универсальный импортер позволяет создавать скрипты импорта для любого типа контента,
просто указывая последовательность модулей на странице.

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